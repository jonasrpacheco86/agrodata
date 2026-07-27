# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Estado atual

**Fase 2 em implementação — três fontes + 3 indicadores + CI.** Fonte de verdade, ler antes
de trabalhar: `Portfolio_AgroData_Plano.md` (arquitetura, stack, fases, critérios de "pronto",
pilar de segurança — prevalece sobre este CLAUDE.md em conflito) e `IDEIAS.md`. **Atenção:** os
dois `Portfolio_*.md` são documentos de estratégia **locais e privados** (no `.gitignore`, fora
do repositório público) — se você clonou o repo público, eles não estarão aqui; use este
CLAUDE.md e `docs/adr/` como referência.

Fases 0–1 publicadas (`v0.1.0`, `v0.2.0`) em github.com/jonasrpacheco86/agrodata.
- **DAGs** (`dags/`, todas `schedule=None`, idempotentes, conn `agrodata_dw` = `airflow_rw`):
  `ibge_sidra_producao` (produção), `clima_openmeteo` (5 munis noroeste RS), `precos_ipeadata`
  (soja/milho/trigo, DERAL-PR). Transforms em `dags/sql/*.sql`.
- **Modelo** em `db/init/` (03 = produção; 04 = clima+preços): `raw.*` → `mart.dim_*`,
  `mart.fato_producao`/`fato_clima_safra`/`fato_preco_mensal` + views `vw_producao`,
  `vw_chuva_rendimento`, `vw_receita_hectare`, `vw_preco_sazonal`.
- **Segurança**: papéis em `02-security.sh` (ADR-002); CI em `.github/workflows/ci.yml`
  (gitleaks + ruff + pip-audit, ADR-003); `requirements.txt` é o manifesto pinado.
- **Dashboards**: `docs/dashboard-fase{1,2}.md` (montados na UI, data source `metabase_ro`).

**Convenções aprendidas:** APIs validadas na prática antes de codar (SIDRA/Open-Meteo OK; IPEADATA
não suporta `contains()`/`$select`, filtrar no cliente). Os scripts `db/init/*` só rodam em volume
novo → aplicar nova fase exige `docker compose down -v && up`, depois disparar as DAGs. `requests` +
`psycopg2` já vêm na imagem do Airflow. Preço é proxy PR, não RS (ADR-006). Falta fechar a Fase 2:
rodar as 2 DAGs novas, validar as views, montar o dashboard, checar o CI e taggear `v0.3.0`.

## O que é o projeto

AgroData é a peça central de um **portfólio** (não um produto comercial): uma plataforma
open source que vai do dado público agro à decisão, com IA aterrada nos dados. Prova o fluxo
completo ETL → modelagem → BI → IA/RAG. Cada bloco é uma competência que o mercado reconhece.
Vocabulário de entrevista: é um **DW dimensional** (raw → mart, dimensões e fatos), não "big data".

## Regras invioláveis (anti-complexidade)

Estas regras existem para o projeto não inchar. Não as renegocie durante a execução.

1. **V1 de ponta a ponta primeiro.** Uma fonte, uma tabela, um gráfico, uma pergunta
   respondida pela IA. Só então adicionar.
2. **Toda ideia nova vai para `IDEIAS.md`, nunca direto para o código.** Só entra na V1 se
   sobreviver duas semanas na lista e a V1 já estiver publicada. Isso vale inclusive para
   arquiteturas de projetos de referência: copie a disciplina, nunca o stack.
3. **Pronto > perfeito.** Cada fase tem critério de pronto objetivo; atingiu, congela e passa.
4. **Se uma fase passar do dobro do prazo, corte escopo — não estique o prazo.**

## Stack fixa (não renegociar)

Python · Apache Airflow · PostgreSQL 16+ (com pgvector) · Metabase (dashboard, via Docker) ·
Claude API / Claude Code (agente) · **servidor MCP em Python com FastMCP** · Docker Compose ·
GitHub (código + docs, README com diagramas Mermaid).

**Explicitamente fora de escopo (ver `IDEIAS.md`; cada ausência vira ADR de "por que não"):**
Kafka, Spark, data lake, Kubernetes, Jenkins, AWS/Lambda/EventBridge, interface web própria,
multi-agente, memória longa, text-to-SQL livre, WAF, SIEM, cofre de segredos gerenciado, mTLS,
PostGIS/ML, streaming.

## Fontes de dados da V1 (três, e só três)

1. **IBGE / SIDRA** — API REST pública sem chave (`apisidra.ibge.gov.br`, tabelas da PAM). Recorte: RS, ~10 anos.
2. **Clima — Open-Meteo Historical** — gratuita, sem chave (`archive-api.open-meteo.com/v1/archive`, `daily=precipitation_sum`). **Citar a fonte no README (exigência da licença).**
3. **Preços agro** — rota principal IPEADATA (OData, sem chave); **validar o endpoint na Fase 0**. Fallback: CEPEA via XLS, com ADR registrando que nem toda fonte real é API limpa.

## Fases e critérios de "pronto"

Entregar por fase, com **tag + GitHub Release** ao concluir (versionamento semântico):

| Fase | Entrega | Pronto quando | Tag |
|---|---|---|---|
| 0 — Esqueleto | Repo + README + Docker Compose (Postgres+Airflow+Metabase) + `IDEIAS.md` na raiz | `docker compose up` sobe os 3 serviços; README explica em 10 linhas | v0.1.0 |
| 1 — Uma fonte ponta a ponta | 1 DAG (SIDRA) → `raw` → `mart` (dim: município/ano/cultura; fato: produção) + dashboard 2–3 gráficos | atualiza com 1 clique e o dashboard reflete; leigo entende | v0.2.0 |
| 2 — 3 fontes + 3 indicadores | DAGs de clima e preços; indicadores fechados em 3 (ver plano §Fase 2) | as 3 fontes atualizam pelo Airflow e os 3 indicadores contam a história | v0.3.0 |
| 3 — Servidor MCP | 3–5 ferramentas tipadas (FastMCP) sobre o mart; conecta no Claude Desktop | 10 perguntas de teste respondidas com os dados corretos do mart | v0.4.0 |
| 4 — Documentar e publicar | README completo, 3–5 ADRs, licença, post LinkedIn | um dev externo clona e roda; post no ar | **v1.0.0** |
| 5 (opcional) — IaC | Terraform (VM) + Ansible (Docker + Compose) | `terraform apply` + `ansible-playbook` reconstroem tudo sem passo manual | v1.1.0 |

Os três indicadores da Fase 2 são fixos e seguem o fio **passado → impacto → decisão**:
chuva no ciclo × rendimento; receita estimada por hectare (cruza as 3 fontes — gráfico-vitrine);
sazonalidade do preço × calendário de colheita.

## Decisões de arquitetura a defender (viram ADRs em `docs/adr/`)

- **Ferramentas MCP tipadas com SQL controlado, não text-to-SQL livre** — confiabilidade e
  também controle preventivo de segurança (limita superfície de injeção de prompt).
- **RAG leve só onde serve** — pgvector sobre metadados/dicionário de dados (`busca_metadados`);
  o dado tabular vai por ferramenta tipada. "RAG onde serve, determinismo onde a precisão manda."
- **Compose + IaC (não Kubernetes)** para este porte; saber justificar a ausência é maturidade.

## Pilar de segurança (função Protect do NIST CSF)

Não é fase nova — são controles pequenos (20–40 linhas) distribuídos nas fases existentes.
**O entregável de verdade é o ADR, não a ferramenta.** Recorte honesto a declarar no README:
todas as fontes são dados públicos abertos, logo **não há dado pessoal/LGPD em escopo**.

- **Fase 0** — `.env` fora do git, `.env.example` versionado, `.gitignore` no 1º commit; imagens Docker com tag fixada (nunca `latest`), containers non-root. `ADR-001`.
- **Fase 1** — Menor privilégio no Postgres (o controle mais valioso): 3 papéis — Airflow escreve em `raw`+`mart`, Metabase lê só `mart`, MCP lê só as views que expõe; nada como superusuário. `ADR-002`.
- **Fase 2** — CI (GitHub Actions) com 3 verificações: varredura de segredo no histórico, análise estática Python, auditoria de dependências. `ADR-003`.
- **Fase 3** — MCP: consulta parametrizada sempre, limite de linhas por retorno, conexão só-leitura, log de qual ferramenta foi chamada com quais argumentos. `ADR-004`.
- **Fase 4** — Seção "Modelo de ameaças, versão curta" no README. `ADR-005`.

**Pronto quando:** os 5 ADRs existem, o CI falha de propósito num commit com segredo plantado,
e nenhum serviço conecta ao banco como superusuário.

## Automações Claude Code (`.claude/`)

- **Hook guardrail** (`PreToolUse` Edit|Write → `.claude/hooks/guardrail.sh`): bloqueia (exit 2,
  reconsiderar) duas coisas — (1) **anti-complexidade**: imports/dependências/serviços fora da
  stack fixa em `*.py`, manifests e `docker-compose` (Kafka, Spark, Kubernetes, AWS/boto3,
  LangChain, Mongo...); a mensagem manda registrar a ideia no `IDEIAS.md`. Não afeta `*.md`, então
  ADRs "por que não usei X" citam livremente. (2) **segredos**: edição de `.env`/`*.key`/`*.pem`/
  credenciais e vazamento de chave real (`sk-ant-…`, `AKIA…`, private key) em arquivo versionado.
  `.env.example` é liberado. Para liberar um caso legítimo, o humano ajusta o hook.
- **Skill `/novo-adr`** (user-only): cria um ADR curto e numerado em `docs/adr/` (risco → decisão
  → o que ficou de fora → função NIST CSF). `ADR-001`–`ADR-005` reservados ao pilar de segurança;
  novos de arquitetura a partir de `ADR-006`.

## Segredos (ADR-001)

Segredos vivem **só em `.env` local**, que está no `.gitignore` e **nunca vai para o GitHub**.
O repositório versiona apenas `.env.example` (placeholders). Os papéis de banco de menor
privilégio (ADR-002) já estão parametrizados no `.env.example`. O hook guardrail reforça isso
automaticamente. Ao criar o repositório git na Fase 0, o `.gitignore` já deve estar no 1º commit.

## Idioma

Português brasileiro em UI, commits, documentação e comunicação. Commits pequenos e frequentes
(o histórico conta a história do projeto).
