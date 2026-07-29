# ADR-009: SecDevOps do deploy — cadeia de entrega e baseline do runtime publicado

- **Status**: aceito
- **Data**: 2026-07-28
- **Fase**: 5
- **Função NIST CSF**: Protect (com um pouco de Detect)

## Contexto e risco
Os ADR-001 a ADR-005 foram escritos para um sistema que rodava inteiro em `docker compose` local.
A Fase 5 quebrou três premissas de uma vez: passou a existir uma **superfície pública** (o MCP no
Render, ADR-008), um **banco de terceiro** (Neon) e uma **esteira que promove código para
produção**. Três lacunas concretas apareceram:

1. **Promoção sem decisão.** O padrão do Render é publicar a cada push no `main`. Isso faz do
   `git push` a operação mais poderosa do projeto — sem revisão, sem CI verde obrigatório.
2. **Baseline invertido.** O `mcp_server/Dockerfile`, escrito na Fase 5, rodava **como root**,
   enquanto o `docker-compose.yml` local já cumpria o non-root do ADR-001. O serviço mais exposto
   tinha o baseline mais fraco — e nada no CI detectava isso.
3. **Dependência que muda sozinha.** Actions referenciadas por tag móvel (`@v4`) são código de
   terceiro com permissão de executar dentro do pipeline; `starlette` e `uvicorn`, importados
   direto pelo `server.py`, entravam sem pin como transitivas do `mcp[cli]`.

## Decisão
Controles pequenos, todos dentro da stack fixa, aplicados onde a lacuna está:

- **Promoção manual**: `autoDeploy: false` em `deploy/render.yaml`. Publicar é um ato nomeado,
  depois do CI verde. Rollback é redeploy do commit anterior (o serviço é sem estado).
- **Runtime non-root**: usuário `10001` sem shell no `mcp_server/Dockerfile`, com os caches do
  `fastembed` e do `huggingface_hub` criados e transferidos **antes** do download do modelo. O CI
  **prova** o invariante (`test "$uid" -ne 0`) em vez de confiar na leitura do Dockerfile.
- **Cadeia de suprimentos**: todas as actions pinadas por **SHA de commit** (versão legível no
  comentário), `starlette`/`uvicorn` pinados em `mcp_server/requirements.txt`, e um job que
  constrói a imagem publicada e a varre com `trivy` (`CRITICAL,HIGH`, `ignore-unfixed`). O
  Dependabot mensal (`.github/dependabot.yml`) é o contrapeso obrigatório do pin.
- **Borda endurecida** (`mcp_server/server.py`): bearer comparado com `hmac.compare_digest` em
  **bytes** (tempo constante, e sem o `TypeError` que `str` não-ASCII causaria — seria um `500`
  acionável sem token); teto por IP **antes** da autenticação, para que uma enxurrada sem token
  custe o mínimo, e teto global **depois** dela, para que tráfego anônimo não consiga negar o
  serviço a quem tem o token; requisição recusada não realimenta a janela e o dicionário de IPs
  tem teto duro. Mais `statement_timeout = 15 s` por transação. Log de `401` e `429` com o IP: em
  um endpoint público, esses dois códigos em série são o sinal barato de varredura.

## O que ficou de fora (e por quê)
**Assinatura de imagem (cosign) e SBOM**: a imagem não é distribuída a terceiros — só o Render a
constrói e a executa —, então o scanner cobre o risco real e a assinatura resolveria um problema
que não temos. **WAF**: a superfície é um endpoint JSON autenticado sem SQL arbitrário (ADR-004);
um WAF na frente disso é teatro. **SIEM**: três containers e zero usuários reais; o log do host,
lido quando há motivo, é proporcional. **Rate limit distribuído (Redis)**: exigiria um serviço
novo para resolver um problema que só existe com mais de uma instância — o free tier tem uma.
**Ambiente de staging**: duplicaria o consumo de cota (ADR-010) para um demo cuja recuperação é
recriar tudo do zero em minutos.

## Consequências
O baseline do serviço público deixou de depender de disciplina e passou a ser verificado a cada PR
— o que importa, já que foi exatamente uma regressão silenciosa de baseline que motivou este ADR.
O preço é atrito assumido: um clique manual por release, diffs de `uses:` ilegíveis (SHA vs SHA) e
PRs mensais do Dependabot para revisar. O limite de taxa vive em memória: **não sobrevive a restart
nem se soma entre instâncias** — correto para uma instância, insuficiente no dia em que houver
duas, e registrado aqui para não ser descoberto depois. Detalhamento dos controles em
[`docs/secdevops-finops.md`](../secdevops-finops.md).
