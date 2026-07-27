#!/usr/bin/env bash
# AgroData — papéis de MENOR PRIVILÉGIO + schemas raw/mart (ADR-002).
# Roda no 1º init do Postgres (docker-entrypoint-initdb.d), como superusuário.
# Nomes de papel fixos; senhas vêm do ambiente (passadas pelo docker-compose a partir do .env).
set -e

: "${AIRFLOW_DB_PASSWORD:?defina AIRFLOW_DB_PASSWORD no .env}"
: "${METABASE_DB_PASSWORD:?defina METABASE_DB_PASSWORD no .env}"
: "${MCP_DB_PASSWORD:?defina MCP_DB_PASSWORD no .env}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname agrodata \
  --set airflow_pw="$AIRFLOW_DB_PASSWORD" \
  --set metabase_pw="$METABASE_DB_PASSWORD" \
  --set mcp_pw="$MCP_DB_PASSWORD" <<'EOSQL'
-- Papéis de login, nenhum com privilégio de superusuário (ADR-002).
CREATE ROLE airflow_rw  LOGIN PASSWORD :'airflow_pw';   -- escreve em raw + mart
CREATE ROLE metabase_ro LOGIN PASSWORD :'metabase_pw';  -- lê só mart
CREATE ROLE mcp_ro      LOGIN PASSWORD :'mcp_pw';       -- lê só as views de mart (Fase 3)

-- Schemas do DW, de propriedade do papel que escreve.
CREATE SCHEMA IF NOT EXISTS raw  AUTHORIZATION airflow_rw;
CREATE SCHEMA IF NOT EXISTS mart AUTHORIZATION airflow_rw;

-- Leitura de mart para o Metabase (tabelas e views, inclusive as futuras via default privileges).
GRANT USAGE ON SCHEMA mart TO metabase_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE airflow_rw IN SCHEMA mart
  GRANT SELECT ON TABLES TO metabase_ro;

-- mcp_ro só enxerga o schema; o SELECT é concedido view a view no 03-mart-ddl.sql
-- (superfície controlada — nunca as tabelas-base). Prepara o ADR-004.
GRANT USAGE ON SCHEMA mart TO mcp_ro;

-- raw NÃO é concedido a metabase_ro nem mcp_ro: dado bruto é invisível para quem lê.
EOSQL
