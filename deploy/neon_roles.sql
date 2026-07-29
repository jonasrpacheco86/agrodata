-- AgroData — bootstrap de papéis/schemas na Neon (equivalente ao db/init/02-security.sh,
-- mas em SQL puro, rodado pelo papel dono da Neon). Depois rode os DDL 03/04/05 (que criam
-- tabelas/views e concedem SELECT ao mcp_ro).
--
-- ANTES de rodar: troque as duas senhas abaixo por valores fortes e URL-safe.
--   psql "$NEON_OWNER_URL" -f deploy/neon_roles.sql

CREATE EXTENSION IF NOT EXISTS vector;

-- Papel de escrita (as DAGs, rodando localmente, escrevem na Neon por este papel).
CREATE ROLE airflow_rw LOGIN PASSWORD 'TROQUE_airflow_rw';
-- Papel só-leitura que o servidor MCP público usa (menor privilégio, ADR-002/004).
CREATE ROLE mcp_ro     LOGIN PASSWORD 'TROQUE_mcp_ro';

CREATE SCHEMA IF NOT EXISTS raw  AUTHORIZATION airflow_rw;
CREATE SCHEMA IF NOT EXISTS mart AUTHORIZATION airflow_rw;

-- mcp_ro enxerga o schema mart; o SELECT é concedido view a view pelos DDL 03/04/05.
GRANT USAGE ON SCHEMA mart TO mcp_ro;

-- Teto de conexões do papel público: em banco serverless, conexão aberta é compute cobrado.
-- Vale como guarda de custo (ADR-010) e como limite de dano se o bearer vazar (ADR-009).
-- 20, e não 5: o `_query()` abre uma conexão por consulta e o FastMCP roda as tools em threadpool,
-- então 5 estrangularia o uso legítimo (`FATAL: too many connections for role`) muito antes de
-- conter abuso — quem contém abuso é o rate limit da borda. É teto de dano, não de vazão.
ALTER ROLE mcp_ro CONNECTION LIMIT 20;

-- Teto de tempo por consulta, no servidor: vale mesmo se o cliente esquecer de aplicá-lo, e
-- sobrevive ao pooler (que descarta parâmetro de startup). O servidor MCP ainda manda um
-- `SET LOCAL statement_timeout` por transação — os dois juntos, nenhum dependendo do outro.
ALTER ROLE mcp_ro SET statement_timeout = '15s';

-- Neon: o papel dono precisa poder assumir airflow_rw para os DDL (que usam SET ROLE).
GRANT airflow_rw TO CURRENT_USER;
