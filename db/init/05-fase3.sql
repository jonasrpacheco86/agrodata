-- AgroData — DDL da Fase 3 (servidor MCP). Roda no 1º init após 04; aditivo/idempotente, também
-- pode ser aplicado a um volume existente com `psql -f` (sem down -v).
-- Padrão do 03/04: objetos criados COMO airflow_rw; grant explícito de leitura a mcp_ro.
SET ROLE airflow_rw;

-- Clima por município e safra (todos os 5 munis; o vw_chuva_rendimento só traz soja).
CREATE OR REPLACE VIEW mart.vw_clima_safra AS
SELECT cl.cod_ibge,
       m.nome AS municipio,
       cl.ano_safra,
       cl.chuva_ciclo_out_mar_mm,
       cl.et0_ciclo_mm
FROM mart.fato_clima_safra cl
JOIN mart.dim_municipio m ON m.cod_ibge = cl.cod_ibge;

-- Série temporal de preço por cultura e mês.
CREATE OR REPLACE VIEW mart.vw_preco_mensal AS
SELECT pm.cod_produto,
       c.nome AS cultura,
       pm.ano,
       pm.mes,
       pm.preco_rs_saca,
       pm.kg_por_saca
FROM mart.fato_preco_mensal pm
JOIN mart.dim_cultura c ON c.cod_produto = pm.cod_produto;

-- Dicionário de dados para o RAG (busca_metadados). Uma linha por objeto/coluna relevante do mart.
-- embedding do modelo multilíngue MiniLM (384 dims). Populado por mcp_server/index_metadados.py.
CREATE TABLE IF NOT EXISTS mart.dicionario_dados (
    id         serial PRIMARY KEY,
    objeto     text NOT NULL,
    descricao  text NOT NULL,
    embedding  vector(384)
);

-- mcp_ro enxerga SOMENTE views + o dicionário (nunca as tabelas-base nem raw) — ADR-002/ADR-004.
GRANT SELECT ON mart.vw_clima_safra, mart.vw_preco_mensal, mart.dicionario_dados TO mcp_ro;

RESET ROLE;
