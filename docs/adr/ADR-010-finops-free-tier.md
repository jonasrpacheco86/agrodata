# ADR-010: FinOps — o free tier como restrição de arquitetura, não como economia

- **Status**: aceito
- **Data**: 2026-07-28
- **Fase**: 5
- **Função NIST CSF**: não se aplica (decisão econômica). O efeito colateral em **disponibilidade**
  é o que conecta este ADR ao [ADR-009](ADR-009-secdevops-do-deploy.md): vários controles servem
  aos dois propósitos.

## Contexto e risco
A conta do demo é R$ 0,00, e é justamente isso que engana. Custo zero não significa recurso
ilimitado: significa que **a moeda mudou**. O que se esgota na Neon é **compute-hora**; no Render,
**instance-hora**; no GitHub Actions, **minuto de runner**. Todos têm cota, e a cota acaba.

O risco concreto, então, não é uma fatura inesperada — é **a cota acabar e o demo sair do ar** no
dia em que alguém for vê-lo. Três caminhos levam a isso, e nenhum exige má intenção:

- um health check que consulta o banco acorda um Postgres serverless a cada ping, **com o demo
  parado**;
- um agente de IA em laço, ou um scanner varrendo a internet, dispara milhares de requisições;
- uma consulta travada continua consumindo compute com ninguém do outro lado esperando a resposta.

Havia também a tentação oposta: subir a topologia "de verdade" (VM sempre ligada com Postgres,
Airflow e Metabase públicos) para o portfólio parecer maior — pagando dinheiro real e mais
superfície de ataque pela mesma demonstração.

## Decisão
Tratar custo como propriedade de arquitetura, com métrica nomeada e tetos técnicos:

1. **Nomear a unidade de custo**: não é R$/mês, é compute-hora (Neon) e instance-hora (Render). O
   número a vigiar é **frequência de acordar**, não volume de dado.
2. **Registrar como decisão os guardrails que já existiam por acaso**, para que ninguém os desfaça
   sem perceber: `/healthz` responde **JSON estático, sem tocar no banco**; `LIMITE = 500` linhas
   por ferramenta (ADR-004) é teto de custo além de teto de superfície; hibernação e autosuspend
   são **o mecanismo que zera o custo ocioso**, não defeitos a contornar — com a ressalva de que a
   hibernação depende de ninguém bater na URL pública, e nenhum controle dentro do processo pode
   garantir isso (quando o código roda, a instância já acordou).
3. **Acrescentar tetos**: limite de taxa com **teto global sobre o tráfego autenticado** (o limite
   superior de compute que um dia ruim pode consumir passa a ser conhecido; sobre tráfego anônimo
   o teto global seria autogol, porque um scanner negaria o serviço a quem tem o token),
   `statement_timeout = 15 s` aplicado por `SET LOCAL` na transação **e** como default do papel, e
   `CONNECTION LIMIT 20` no `mcp_ro` — teto de dano, não de vazão: apertá-lo demais recusa uso
   legítimo antes de conter abuso, que é trabalho do rate limit.
   A `MCP_DB_URL` usa o host **direto**, não o `-pooler`: o pooler pouparia conexões que, neste
   volume, não pesam, e em troca descartaria parâmetros de sessão e manteria conexões abertas por
   papel — atravessando os dois tetos acima. Previsibilidade verificável acima de eficiência
   marginal.
4. **Aplicar FinOps ao próprio CI**: o build da imagem embute ~120 MB de modelo, então roda só em
   PR e no `main`, não em todo push de branch.

## O que ficou de fora (e por quê)
**Plano pago com instância sempre acordada**: resolveria o cold start, mas a restrição vigente é
cota, não latência — e o desenho já está pronto para a troca (serviço sem estado, estado no banco
gerenciado). **Ambiente de staging**: dobraria o consumo das duas cotas. **Alerta automático de
consumo**: os painéis de Neon e Render já mostram a cota, e um alerta exigiria integração externa
para um projeto de um operador só. **Cache de resposta das ferramentas**: economizaria compute, mas
adiciona invalidação e um estado que hoje não existe — vai para o `IDEIAS.md`, não para a V1.
**Reserva/committed use**: não existe no porte, e citá-lo aqui seria vocabulário sem substância.

## Consequências
O custo passa a ter teto conhecido em vez de hipotético, e o abuso passa a ser limitado pelo mesmo
mecanismo que limita o gasto — segurança e FinOps são, aqui, o mesmo controle. O preço é ergonomia:
cold start de ~30–60 s no primeiro acesso (Render hiberna, Neon pausa) e um `429` possível sob
rajada legítima. É um trade-off declarado, não um defeito: **otimizar para a restrição vigente**.
Se a restrição mudar de cota para latência, a resposta muda junto — e este ADR passa a ser o
registro de por que ela era outra. Detalhamento em
[`docs/secdevops-finops.md`](../secdevops-finops.md#8-finops).
