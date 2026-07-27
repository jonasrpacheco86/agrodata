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

-- Neon: o papel dono precisa poder assumir airflow_rw para os DDL (que usam SET ROLE).
GRANT airflow_rw TO CURRENT_USER;
