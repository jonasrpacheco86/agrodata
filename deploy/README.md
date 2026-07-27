# Deploy — demo público leve (Neon + Render)

Topologia grátis e sem cartão de crédito: **Postgres na Neon** (com `pgvector`) + **servidor MCP no
Render** (HTTPS incluso). Metabase e Airflow **não** vão ao ar (Airflow roda local só para carregar os
dados; o dashboard vira prints). O MCP é exposto com **bearer token** e conecta como `mcp_ro`
(só-leitura) — ver [ADR-008](../docs/adr/ADR-008-exposicao-publica.md).

```
Local (você)                         Nuvem (grátis)
DAGs (Airflow) --escreve na Neon-->  Neon Postgres (mart + pgvector)
index_metadados.py --embeddings-->        ▲ mcp_ro (só-leitura)
                                          │
                                     Render: servidor MCP (HTTP + bearer)  <- IA / MCP Inspector
```

## 1. Neon (Postgres)
1. Crie um projeto em neon.tech (login GitHub, sem cartão). Postgres 16.
2. Pegue a **connection string do dono** (`NEON_OWNER_URL`).
3. Crie papéis e schemas (troque as senhas no arquivo antes):
   ```bash
   psql "$NEON_OWNER_URL" -f deploy/neon_roles.sql
   ```
4. Crie as tabelas/views (reaproveita os DDL do projeto):
   ```bash
   for f in db/init/03-mart-ddl.sql db/init/04-fase2-ddl.sql db/init/05-fase3.sql; do
     psql "$NEON_OWNER_URL" -f "$f"
   done
   ```

## 2. Carregar os dados na Neon (Airflow local → Neon)
Com a stack local no ar, aponte a conexão do DW para a Neon (papel `airflow_rw`) e rode as DAGs:
```bash
export AIRFLOW_CONN_AGRODATA_DW="postgresql://airflow_rw:<senha>@<host-neon>/<db>?sslmode=require"
for d in ibge_sidra_producao clima_openmeteo precos_ipeadata; do
  docker compose exec -T -e AIRFLOW_CONN_AGRODATA_DW="$AIRFLOW_CONN_AGRODATA_DW" airflow \
    airflow dags test $d
done
# embeddings do dicionário (RAG):
MCP_DB_URL="postgresql://airflow_rw:<senha>@<host-neon>/<db>?sslmode=require" \
  python mcp_server/index_metadados.py
```
> Alternativa: `pg_dump` do `mart` local e `psql` restore na Neon.

## 3. Render (servidor MCP)
1. No Render (login GitHub, sem cartão), **New → Blueprint** apontando para este repo
   (`deploy/render.yaml`).
2. Defina os secrets:
   - `MCP_DB_URL` = connection string da Neon como **`mcp_ro`** (`...?sslmode=require`).
   - `MCP_AUTH_TOKEN` = um token forte (ex.: `openssl rand -hex 32`).
3. Deploy. O health check é `/healthz` (sem auth); o endpoint MCP é `/mcp` (exige bearer).
4. (Opcional) Domínio: aponte `mcp.agrodata.agilit.me` via **CNAME** para o host `*.onrender.com`.

## 4. Validar
```bash
# health (200, sem token):
curl https://agrodata-mcp.onrender.com/healthz
# sem token (401):
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://agrodata-mcp.onrender.com/mcp
```
Para exercitar as ferramentas, use o **MCP Inspector** apontando para a URL `/mcp` com o header
`Authorization: Bearer <MCP_AUTH_TOKEN>` (o conector nativo do Claude Desktop espera OAuth; o bearer é
mais direto no Inspector — ver ADR-008).

## Notas
- Render free **hiberna após ~15 min** ociosa → primeiro acesso tem cold start (~30–60 s). É esperado.
- Neon free pode **pausar** o projeto após inatividade → primeira query "acorda" o banco.
- Só o MCP fica público (bearer, só-leitura). Nada de Postgres/Airflow expostos.
