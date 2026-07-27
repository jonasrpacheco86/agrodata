-- AgroData — inicialização do Postgres (roda só no 1º start, via docker-entrypoint-initdb.d).
-- Cria os bancos de metadados/app dos serviços e habilita pgvector no DW.
-- Os papéis de MENOR PRIVILÉGIO (airflow_rw, metabase_ro, mcp_ro) entram na Fase 1 (ADR-002).

-- Bancos separados por serviço (o DW agrodata já foi criado via POSTGRES_DB):
CREATE DATABASE airflow;
CREATE DATABASE metabase;

-- pgvector no data warehouse (usado na busca de metadados do servidor MCP, Fase 3):
\connect agrodata
CREATE EXTENSION IF NOT EXISTS vector;
