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
   - `MCP_DB_URL` = connection string da Neon como **`mcp_ro`**, usando o host **direto**
     (`ep-....<região>.aws.neon.tech`, com `?sslmode=require`) — **não** o `-pooler`. O servidor
     abre uma conexão por consulta, e o pooler pouparia conexões que neste volume não pesam; em
     troca, em modo transaction ele descarta parâmetro de sessão e mantém conexões abertas por
     papel, atravessando o `statement_timeout` e o `CONNECTION LIMIT` (ADR-010). O código funciona
     nos dois hosts (o timeout vai por `SET LOCAL`), mas o runbook fixa o previsível.
   - `MCP_AUTH_TOKEN` = um token forte (ex.: `openssl rand -hex 32`).
3. Deploy. O blueprint vem com **`autoDeploy: false`** (ADR-009): push no `main` não publica
   sozinho — publique pelo painel depois do CI verde. Rollback = redeploy do commit anterior.
   O health check é `/healthz` (sem auth); o endpoint MCP é `/mcp` (exige bearer).
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

## Verificação dos controles
Prova rápida do que os ADR-009/010 afirmam (roda local, sem depender de Neon/Render):
```bash
docker build -f mcp_server/Dockerfile -t agrodata-mcp:test .
docker run --rm agrodata-mcp:test id -u                    # != 0 (non-root, ADR-009)
docker run --rm --network none agrodata-mcp:test python -c \
  "from fastembed import TextEmbedding; TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"
# sem rede e sem erro = o modelo está no cache da imagem, não é baixado no cold start

docker run -d --rm --name mcp-test -p 8123:8000 \
  -e MCP_AUTH_TOKEN=teste123 -e MCP_DB_URL="postgresql://mcp_ro:...@127.0.0.1/agrodata" agrodata-mcp:test
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8123/healthz          # 200 (sem token)
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8123/mcp      # 401
# header não-ASCII: 401 também, nunca 500 (o bearer é comparado em bytes)
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8123/mcp \
  -H "$(printf 'Authorization: Bearer \xff')"                                   # 401
# teto por IP (30/min) barra a enxurrada anônima; o 429 não realimenta a janela:
for i in $(seq 1 40); do curl -s -o /dev/null -w '%{http_code} ' \
  -X POST http://localhost:8123/mcp; done                                       # 401×30, depois 429
# e o teto global é só do tráfego autenticado — depois da rajada acima, quem tem token é atendido:
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8123/mcp \
  -H 'Authorization: Bearer teste123' -H 'X-Forwarded-For: 203.0.113.9'         # != 429
docker stop mcp-test
```
O job `imagem-mcp` do CI repete a prova de non-root e varre a imagem com `trivy` a cada PR; o job
`testes-borda` (`mcp_server/test_borda.py`) verifica os invariantes do rate limit e do bearer a
cada push, sem precisar subir o container.

## Rotação de segredos
São três, e nenhuma rotação exige janela de manutenção:

| Segredo | Como trocar | Impacto |
|---|---|---|
| `MCP_AUTH_TOKEN` | gerar novo (`openssl rand -hex 32`), atualizar no painel do Render, redeployar | quem usava o token antigo passa a receber 401 |
| senha de `mcp_ro` | `ALTER ROLE mcp_ro PASSWORD '...';` na Neon → atualizar `MCP_DB_URL` no Render → redeploy | segundos de erro de conexão no MCP |
| senha de `airflow_rw` | `ALTER ROLE airflow_rw PASSWORD '...';` → atualizar `AIRFLOW_CONN_AGRODATA_DW` local | nenhum (a ingestão é sob demanda) |

Nenhum deles aparece em log ou em arquivo versionado (ADR-001).

## Notas e guardrails de custo (ADR-010)
- Render free **hiberna após ~15 min** ociosa → primeiro acesso tem cold start (~30–60 s). É esperado
  — a hibernação é o que zera o custo ocioso, não um defeito a contornar. **Mas ela depende de
  ninguém bater na URL**: `/healthz` é público e um crawler pingando de minuto em minuto mantém a
  instância acordada 24/7. Nada no processo evita isso (quando o código roda, já acordou) — por
  isso `/healthz` fica fora dos tetos, e a mitigação é não divulgar a URL fora do demo e olhar as
  horas-instância no painel.
- Neon free pode **pausar** o projeto após inatividade → primeira query "acorda" o banco. Por isso
  `/healthz` responde estático: se consultasse o banco, o health check do Render acordaria a Neon
  para sempre, queimando cota com o demo parado.
- Tetos ativos: 30 req/min **por IP antes da auth** e 120 req/min **globais sobre o tráfego
  autenticado** (429 com `Retry-After`), `statement_timeout` de 15 s (por transação e como default
  do papel), `CONNECTION LIMIT 20` no `mcp_ro`, `LIMIT 500` por ferramenta.
- Só o MCP fica público (bearer, só-leitura). Nada de Postgres/Airflow expostos.
