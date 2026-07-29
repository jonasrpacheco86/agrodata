# SecDevOps e FinOps na orquestração do AgroData

> Documento de referência da **Fase 5**. Descreve os controles que existem de fato neste
> repositório — cada afirmação aponta o arquivo onde o controle vive. O que não foi implementado
> está na tabela final, como ausência justificada, não como pendência disfarçada.
>
> Decisões correspondentes: [ADR-009](adr/ADR-009-secdevops-do-deploy.md) (segurança da entrega) e
> [ADR-010](adr/ADR-010-finops-free-tier.md) (custo como restrição de arquitetura).

## Por que este documento existe

Até a `v1.0.0` o AgroData rodava inteiro em `docker compose` na máquina do desenvolvedor. Segurança
ali é, em boa medida, uma propriedade do ambiente: não há porta na internet, não há terceiro
hospedando dado, não há nada que se atualize sozinho.

A Fase 5 quebrou as três premissas de uma vez. Passou a existir **uma superfície pública** (o
servidor MCP no Render), **um banco gerenciado de terceiro** (Neon) e **uma esteira que promove
código para produção**. Os ADR-001 a ADR-005 continuam válidos, mas foram escritos para o mundo
local — não respondem "quem pode publicar", "o que roda dentro do container publicado" nem "o que
acontece se alguém apontar um script na URL".

O recorte honesto a declarar de saída: **todas as fontes são dados públicos abertos**, então não há
dado pessoal em escopo e o pior caso de vazamento é alguém ler um dado que o IBGE já publica. O que
está de fato em risco é **disponibilidade** e **cota** — e é por isso que, neste projeto, segurança
e FinOps são frequentemente o mesmo controle. Um limite de taxa não está lá para impedir roubo de
dado: está lá para que ninguém consiga gastar a cota mensal de compute numa tarde.

O formato de cada pilar é fixo: **risco → controle → pronto quando → custo/atrito**.

---

## 1. Identidade e menor privilégio

**Risco.** Uma credencial única e onipotente transforma qualquer falha em falha total. Em ambiente
gerenciado piora: a credencial do dono da Neon cria e apaga bancos.

**Controle.** Três papéis com escopos disjuntos, herdados do [ADR-002](adr/ADR-002-menor-privilegio-no-banco.md)
e reproduzidos na nuvem por `deploy/neon_roles.sql`:

| Papel | Quem usa | Pode |
|---|---|---|
| dono (Neon) | só o operador humano, no bootstrap | DDL |
| `airflow_rw` | DAGs, rodando **local** | escrever em `raw` e `mart` |
| `mcp_ro` | servidor MCP **público** | `SELECT` nas views expostas, e só |

O `mcp_ro` ganhou ainda `CONNECTION LIMIT 20`. O número é teto de **dano**, não de vazão: como o
`_query()` abre uma conexão por consulta e o FastMCP executa as tools em threadpool, um limite
apertado demais (5, na primeira versão) recusaria uso legítimo antes de conter qualquer abuso —
conter abuso é trabalho do rate limit da borda. A única credencial que existe na internet é a do
papel que menos pode fazer. Do lado da aplicação, o acesso é um **bearer token único**
(`MCP_AUTH_TOKEN`) comparado com `hmac.compare_digest` em `mcp_server/server.py` — comparação em
tempo constante, para não vazar o token byte a byte por diferença de latência. É um detalhe
pequeno, mas é exatamente o tipo de coisa que um `!=` deixa passar.

**Rotação.** Sem procedimento escrito, rotação não acontece. O runbook está em
[`deploy/README.md`](../deploy/README.md#rotação-de-segredos): trocar `MCP_AUTH_TOKEN` é atualizar a
variável no Render e redeployar; trocar a senha de `mcp_ro` é um `ALTER ROLE` na Neon seguido da
atualização de `MCP_DB_URL`. Ambos levam minutos e não têm janela de manutenção — é justamente o que
torna a rotação viável.

**Pronto quando.** Nenhum serviço conecta como superusuário; o token some do painel e volta
diferente sem editar código.

**Custo.** Dois `ALTER ROLE` a mais no bootstrap. O `CONNECTION LIMIT` pode virar erro sob carga —
que é o comportamento desejado, e por isso está documentado.

---

## 2. Cadeia de suprimentos

**Risco.** O código que roda em produção é minoritariamente nosso. Uma GitHub Action referenciada
por tag móvel (`@v4`) é código de terceiro com permissão de executar dentro do pipeline e que pode
**mudar sozinho** entre dois builds — foi assim que campanhas reais de comprometimento de CI
funcionaram.

**Controle.** Três verificações baratas já vinham do [ADR-003](adr/ADR-003-ci-supply-chain.md)
(gitleaks no histórico, `ruff`, `pip-audit`). A Fase 5 acrescenta:

- **Actions pinadas por SHA de commit** em `.github/workflows/ci.yml`, com a versão legível no
  comentário ao lado. Tag é ponteiro; SHA é conteúdo.
- **Dependências transitivas de runtime declaradas.** `starlette` e `uvicorn` são importados
  diretamente pelo `server.py`, mas vinham "de graça" pelo `mcp[cli]`. Agora estão pinadas em
  `mcp_server/requirements.txt` — o que também as coloca sob o olhar do `pip-audit`.
- **Build e varredura da imagem publicada** (job `imagem-mcp`), com `trivy` em `CRITICAL,HIGH` e
  `ignore-unfixed: true`. Falhar por CVE sem correção disponível não é sinal, é ruído que ensina o
  time a ignorar o CI.
- **Testes da borda pública** (job `testes-borda`, `mcp_server/test_borda.py`). A revisão desta
  fase encontrou os defeitos exatamente aqui — tetos que se realimentavam com o próprio `429`,
  contador global colidindo com chave de IP, dicionário sem limite, bearer que virava `500` diante
  de header não-ASCII. Cada um virou um teste: o controle de segurança que ninguém verifica é
  indistinguível de comentário. Os testes usam stubs no lugar de `psycopg`/`mcp`, então custam
  segundos e rodam em todo push, ao contrário do build de imagem.
- **Dependabot mensal** (`.github/dependabot.yml`). Este é o contrapeso indispensável do pin: pin
  sem atualização programada é só um jeito organizado de envelhecer com CVE. Atualizar vira PR
  revisado, não uma mudança silenciosa.

**Pronto quando.** Nenhum `uses:` aponta para tag móvel; o CI falha num commit com segredo plantado;
a imagem que vai ao ar é a mesma que passou pelo scanner.

**Custo.** Diffs de atualização ficam ilegíveis (SHA vs SHA) — mitigado pelo comentário de versão.
E o job de imagem consome minutos de CI, o que nos leva direto ao pilar 8.

---

## 3. Baseline do runtime publicado

**Risco.** Container rodando como root: qualquer execução de código arbitrária começa com o máximo
de privilégio dentro do container, e o kernel é o único obstáculo restante.

**Controle.** O `docker-compose.yml` local já respeitava o baseline do
[ADR-001](adr/ADR-001-gestao-de-segredos-e-baseline-de-container.md) — tags fixadas e
`user: "50000:0"` no Airflow. O `mcp_server/Dockerfile`, escrito depois, **não**: rodava como root.
Ou seja, o serviço mais exposto do projeto tinha o baseline mais fraco. Corrigido: usuário `10001`
sem shell, e o CI **prova** o invariante (`test "$uid" -ne 0`) em vez de confiar na leitura do
Dockerfile.

Detalhe que vale registrar porque é a armadilha clássica: o modelo de embeddings é baixado no build.
Se o `USER` entrar depois do download, o modelo fica de root e o processo não consegue lê-lo — o
container sobe normalmente e só falha (ou rebaixa o cold start para minutos) no primeiro
`busca_metadados`. A ordem correta é criar o usuário e o cache (`FASTEMBED_CACHE_PATH`), dar posse,
**e só então** baixar. O código da aplicação, por outro lado, continua de root e somente-leitura
para o processo: a aplicação não precisa poder reescrever a si mesma.

**Pronto quando.** `docker run --rm agrodata-mcp:ci id -u` devolve diferente de zero, e o job
`imagem-mcp` quebra se alguém regredir isso.

**Custo.** Cinco linhas no Dockerfile e a disciplina de ordem das camadas.

---

## 4. Superfície pública e borda

**Risco.** Um endpoint na internet recebe tráfego não solicitado desde o primeiro minuto. Sem
limite, uma enxurrada — hostil ou um agente de IA em laço — consome cota e derruba o demo.

**Controle.** A borda vive no middleware `BordaPublica` (`mcp_server/server.py`). Os dois tetos
ficam em **lados opostos da autenticação**, e essa é a decisão que importa:

1. `/healthz` passa livre (o host precisa dele) e responde estático.
2. **Antes da auth, teto por IP** (30 req/min, janela deslizante de 60 s em memória, sem
   dependência nova): faz uma enxurrada **sem token** custar quase nada. É dissuasivo, não uma
   garantia — o IP vem de `X-Forwarded-For`, que o cliente falsifica à vontade.
3. **Depois da auth, teto global** (120 req/min na instância): é o que protege a cota de compute,
   porque só quem passou no bearer chega ao banco. Colocá-lo antes da auth seria um autogol —
   qualquer scanner anônimo esgotaria o orçamento e o `429` cairia justamente sobre quem tem o
   token. Excedeu, `429` com `Retry-After`.

Duas propriedades que o limitador precisa ter, e que a primeira versão não tinha: requisição já
recusada **não** é contabilizada (contar o próprio `429` realimenta a janela e uma enxurrada
sustentada manteria o teto estourado para sempre), e o dicionário de IPs tem **teto duro** de
2.000 chaves com despejo do mais antigo (senão um `X-Forwarded-For` variável cria uma chave por
requisição e a instância free morre por OOM antes de qualquer teto disparar).

O bearer é comparado em **bytes**, não em `str`: `hmac.compare_digest` sobre `str` levanta
`TypeError` diante de qualquer caractere não-ASCII, e o header é do cliente — em `str` isso seria
um `500` acionável sem token, no lugar do `401`.

Atrás disso permanece tudo do [ADR-004](adr/ADR-004-superficie-mcp.md), que a exposição pública não
enfraqueceu: sem text-to-SQL, consulta parametrizada fixa por ferramenta, `LIMIT 500`, conexão
somente-leitura. Somou-se `statement_timeout = 15 s` — uma consulta travada é compute faturado sem
ninguém esperando a resposta. Ele é aplicado **duas vezes, de forma independente**: `SET LOCAL` na
transação de cada consulta (`_query()`) e `ALTER ROLE mcp_ro SET statement_timeout` no servidor.
Não é redundância decorativa: como parâmetro de startup (`options=-c ...`, a primeira versão) o
teto seria descartado ou recusado por um pooler em modo transaction.

**Pronto quando.** `/healthz` responde 200 sem token; `/mcp` responde 401 sem token, com token
errado e com header não-ASCII (401, nunca 500); uma rajada anônima acima de 30/min termina em 429
**sem** consumir o teto de quem está autenticado; o modo `stdio` local segue intacto.

**Custo.** Rate limit em memória **não sobrevive a restart nem se soma entre instâncias**. No free
tier há uma instância só, então é correto hoje e vira insuficiente no dia em que houver duas —
limitação registrada de propósito, não descoberta depois.

---

## 5. Pipeline de entrega

**Risco.** O padrão do Render é `autoDeploy: true`: todo push no `main` vai para produção. Isso faz
do `git push` a operação mais poderosa do projeto, sem revisão, sem CI verde obrigatório e sem
decisão humana.

**Controle.** `autoDeploy: false` em `deploy/render.yaml`. Promover é ato deliberado no painel,
depois do CI verde. A separação vale porque **as duas metades do sistema têm cadências diferentes**:
a ingestão roda local e escreve na Neon (dado novo não exige deploy), o MCP só é publicado quando o
código muda. **Rollback** é redeploy do commit anterior — barato justamente porque o serviço é
sem estado; o estado está todo na Neon.

**Pronto quando.** Um push no `main` não altera o que está no ar; publicar exige uma ação nomeada.

**Custo.** Um clique manual a cada release. Para um demo de portfólio, o clique é o ponto.

---

## 6. Observabilidade e detecção

**Risco.** Sem registro, um abuso é indistinguível de uso; e log demais em ambiente gerenciado vira
o próprio vazamento.

**Controle.** O servidor loga **em `stderr`** (o `stdout` é o transporte do protocolo MCP — logar
ali corrompe a sessão) cada chamada de ferramenta com seus argumentos, conforme o ADR-004, e agora
também `401` e `429` com o IP. Esses dois códigos são o sinal barato de varredura: `401` em série
significa que alguém achou a URL; `429` em série, que alguém insistiu. O que **não** entra no log:
token, string de conexão e linhas de resultado.

Não há SIEM nem agregação. São três containers e zero usuários reais: correlacionar logs aqui seria
teatro de segurança. O log do Render, lido quando há motivo, é proporcional ao porte — e essa
proporcionalidade é a decisão, não a preguiça.

**Pronto quando.** Uma chamada de ferramenta e uma tentativa sem token aparecem no log do Render,
sem nenhum segredo junto.

**Custo.** Detecção é manual e retroativa. Aceito para um demo; seria inaceitável com usuário real.

---

## 7. Resiliência e recuperação

**Risco.** Free tier não promete durabilidade. Projeto pausado, apagado por inatividade ou conta
encerrada são cenários realistas — e a resposta usual (backup gerenciado, PITR) custa dinheiro.

**Controle.** Aqui o projeto tem uma propriedade que a maioria dos sistemas não tem: **o dado é
público e a ingestão é idempotente**. As três DAGs podem ser re-executadas a qualquer momento e
reconstroem `raw` e `mart` do zero, a partir de IBGE, Open-Meteo e IPEADATA. O procedimento de
recuperação é, literalmente, repetir o passo 2 do `deploy/README.md`. Logo:

- **RPO** — irrelevante para o dado analítico: a fonte da verdade é externa e permanente.
- **RTO** — o tempo de recriar papéis, aplicar os DDL e reprocessar as DAGs; da ordem de dezenas de
  minutos, sem dado perdido.
- O que **não** se recupera automaticamente: dashboards do Metabase (montados na UI, documentados
  como passo a passo em `docs/dashboard-fase*.md`) e os segredos, que vivem no `.env` local.

**Pronto quando.** A recuperação está escrita como sequência executável, e não como intenção.

**Custo.** Reprocessar depende de as APIs públicas estarem no ar e estáveis — dependência externa
declarada, não eliminada.

---

## 8. FinOps

FinOps não é "gastar pouco": é **tratar custo como propriedade de arquitetura**, com uma métrica
nomeada, tetos técnicos e trade-offs explícitos. Que a fatura aqui seja R$ 0,00 não dispensa nada
disso — muda a moeda.

### 8.1 Qual é a unidade de custo

A conta deste projeto não é paga em reais, é paga em **cota**:

| Recurso | Unidade escassa | O que a consome |
|---|---|---|
| Neon (Postgres) | compute-hora | qualquer query acorda o compute; ele suspende sozinho após ociosidade |
| Render (MCP) | instance-hora | serviço acordado; hiberna após ~15 min sem requisição |
| GitHub Actions | minuto de runner | cada push que dispara build |

Nomear a métrica é o primeiro passo, e o que muda o raciocínio: uma requisição extra não custa
"quase nada", custa **um ciclo de acordar um banco que estava suspenso**. É por isso que o número a
vigiar é *frequência de acordar*, não volume de dado. (Os limites exatos de cada plano gratuito
mudam com o tempo — confira no painel; o que não muda é qual é a unidade.)

### 8.2 Guardrails que já existiam e agora são decisão registrada

Três escolhas certas já estavam no código por outros motivos. Registrá-las como controle de custo é
o que impede que alguém as desfaça sem perceber:

- **`/healthz` responde JSON estático, sem tocar no banco.** Se ele fizesse um `SELECT 1` — a coisa
  mais natural do mundo num health check — o *health check do host* passaria a acordar a Neon
  ininterruptamente, queimando a cota com o demo parado. É o controle de custo mais valioso do
  projeto e cabe em uma linha.
- **`LIMITE = 500` linhas por ferramenta** (ADR-004): concebido como limite de superfície, funciona
  igualmente como teto de dado transferido e de trabalho do banco.
- **Hibernação e autosuspend não são defeitos a contornar**, são o mecanismo que zera o custo
  ocioso. O cold start (~30–60 s no primeiro acesso) é o preço, e está documentado no README como
  comportamento esperado — não como bug.
  **Limite honesto:** a hibernação do Render depende de *ninguém* bater na URL por ~15 min, e
  `/healthz` é público. Um crawler pingando de minuto em minuto mantém a instância acordada 24/7 e
  consome as horas-instância do mês. Nada dentro do processo resolve isso — quando o middleware
  roda, a instância já acordou; um `429` ali gastaria o mesmo e ainda arriscaria reprovar o health
  check do próprio Render. Por isso `/healthz` fica fora dos tetos, e a mitigação real é externa:
  não divulgar a URL do serviço fora do contexto do demo e vigiar as horas no painel.

### 8.3 Guardrails acrescentados na Fase 5

- **Rate limit com teto global sobre o tráfego autenticado** (pilar 4) — o limite superior de
  compute que um dia ruim pode consumir passa a ser conhecido, não hipotético.
- **`statement_timeout = 15 s`** — consulta travada é compute faturado por nada. Vem por `SET
  LOCAL` na transação **e** por default do papel; nunca por parâmetro de startup, que um pooler
  descarta.
- **`CONNECTION LIMIT 20` no `mcp_ro`** — em banco serverless, conexão aberta é compute. É teto de
  dano: quem regula vazão é o rate limit, não este número.
- **Host *direto* da Neon na `MCP_DB_URL`**, não o `-pooler`. O `_conn()` abre uma conexão por
  consulta, o que em serverless é o padrão que mais desperdiça, e o pooler resolveria isso sem
  mudar código. Mas, no volume deste demo (teto de 120 req/min autenticadas), o desperdício é
  irrelevante perto do que o pooler custa em previsibilidade: em modo transaction ele descarta
  parâmetro de startup e mantém conexões de servidor abertas por papel, atravessando justamente os
  dois controles desta seção. Escolha consciente de **simplicidade verificável** sobre eficiência
  marginal — e o `SET LOCAL` deixa o código correto caso um dia o pooler seja necessário.
- **Build de imagem restrito a PR e `main`** — a imagem embute ~120 MB de modelo; rodar o build em
  todo push de branch gastaria minutos de runner sem informação nova. FinOps se aplica ao CI
  também, não só ao runtime.

### 8.4 O trade-off que se assume

A escolha por free tier (ADR-008) **é** uma decisão de arquitetura e tem preço: cold start no
primeiro acesso, pausa da Neon, uma instância só (que é o que limita o rate limit ao pilar 4). O
vocabulário maduro aqui não é "economizamos", é **otimizar para a restrição vigente**: hoje a
restrição é cota, e a arquitetura responde a ela. Se um dia a restrição virar latência, a resposta
muda — plano pago com instância sempre acordada — e o desenho já está preparado, porque o serviço é
sem estado e o estado está no banco gerenciado.

O anti-padrão evitado merece nome: subir a topologia "de verdade" (VM sempre ligada, Postgres,
Airflow e Metabase públicos) para o demo parecer maior. Custaria dinheiro real e mais superfície de
ataque para entregar exatamente a mesma demonstração.

---

## 9. Adotado × deliberadamente fora

| Prática | Situação | Por quê |
|---|---|---|
| Menor privilégio no banco | **adotado** | ADR-002; reproduzido na Neon |
| Segredo fora do git | **adotado** | ADR-001 + gitleaks no CI |
| Varredura de segredo, lint, auditoria de dependência | **adotado** | ADR-003 |
| Actions pinadas por SHA + Dependabot | **adotado** (Fase 5) | tag móvel é código de terceiro que muda sozinho |
| Container non-root, tag fixada, scan de imagem | **adotado** (Fase 5) | ADR-009; invariante provado no CI |
| Rate limit, `statement_timeout`, `CONNECTION LIMIT` | **adotado** (Fase 5) | ADR-009/010; segurança e custo no mesmo controle |
| Promoção manual (`autoDeploy: false`) | **adotado** (Fase 5) | push não deve ser a operação mais poderosa do projeto |
| Kubernetes / service mesh | **fora** | 1 serviço público sem estado; Compose + host gerenciado bastam (`IDEIAS.md`) |
| mTLS entre serviços | **fora** | não há malha: um serviço, TLS gerenciado na borda |
| WAF | **fora** | superfície é um endpoint JSON autenticado sem SQL arbitrário (ADR-004) |
| SIEM / agregação de logs | **fora** | 3 containers, zero usuários reais; log do host é proporcional |
| Cofre de segredos gerenciado | **fora** | 3 segredos, 1 operador; `.env` + variáveis do host (ADR-001) |
| OAuth 2.1 no MCP | **fora, por ora** | bearer basta para o demo; ressalva declarada no ADR-008 |
| SBOM + assinatura de imagem (cosign) | **fora** | imagem não é distribuída a terceiros; scan cobre o risco real |
| Autoscaling | **fora** | free tier não escala; teto global de taxa é o substituto honesto |
| Backup gerenciado / PITR | **fora** | dado público e ingestão idempotente: o backup é re-rodar as DAGs (pilar 7) |

## Como isto é verificado

Não vale afirmação sem verificação — os comandos estão em
[`deploy/README.md`](../deploy/README.md#verificação-dos-controles): provar `uid != 0` na imagem,
`200` no `/healthz`, `401` sem token, `429` na rajada, e o modo `stdio` local intacto. O job
`imagem-mcp` do CI executa a prova de non-root a cada PR, para que o baseline não regrida de novo —
que foi, afinal, exatamente o que aconteceu entre a Fase 0 e a Fase 5.
