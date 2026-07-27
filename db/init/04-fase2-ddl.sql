-- AgroData — DDL da Fase 2 (clima + preços + 3 indicadores). Roda no 1º init, após 03.
-- Mesmo padrão do 03: objetos criados COMO airflow_rw (dono/escritor); default privileges do 02
-- concedem SELECT ao metabase_ro; grant explícito a mcp_ro só nas views.
SET ROLE airflow_rw;

-- ── RAW ────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw.clima_openmeteo (
    cod_ibge         integer,
    data             date,
    precipitation_mm numeric,
    et0_mm           numeric,
    ingested_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.precos_ipeadata (
    serie_cod    text,
    cod_produto  integer,
    data         date,
    preco_rs     numeric,
    kg_por_saca  integer,
    ingested_at  timestamptz NOT NULL DEFAULT now()
);

-- ── MART: novos fatos ──────────────────────────────────────────────────────────
-- Clima agregado ao ciclo da safra (out do ano anterior a mar do ano de colheita).
CREATE TABLE IF NOT EXISTS mart.fato_clima_safra (
    cod_ibge                integer NOT NULL REFERENCES mart.dim_municipio (cod_ibge),
    ano_safra               integer NOT NULL,   -- ano de colheita (Y do ciclo out(Y-1)–mar(Y))
    chuva_ciclo_out_mar_mm  numeric,
    et0_ciclo_mm            numeric,
    PRIMARY KEY (cod_ibge, ano_safra)
);

-- Preço mensal por cultura (R$ por saca; kg_por_saca guarda a base de conversão).
CREATE TABLE IF NOT EXISTS mart.fato_preco_mensal (
    cod_produto    integer NOT NULL REFERENCES mart.dim_cultura (cod_produto),
    ano            integer NOT NULL,
    mes            integer NOT NULL,
    preco_rs_saca  numeric,
    kg_por_saca    integer,
    PRIMARY KEY (cod_produto, ano, mes)
);

-- ── MART: as 3 views-indicador (passado → impacto → decisão) ────────────────────
-- Indicador 1: chuva no ciclo × rendimento da soja (caso-vitrine: seca 2021/22).
CREATE OR REPLACE VIEW mart.vw_chuva_rendimento AS
SELECT cl.cod_ibge,
       m.nome AS municipio,
       cl.ano_safra AS ano,
       cl.chuva_ciclo_out_mar_mm,
       fp.rendimento_medio_kg_ha
FROM mart.fato_clima_safra cl
JOIN mart.dim_municipio m ON m.cod_ibge = cl.cod_ibge
JOIN mart.fato_producao fp
     ON fp.cod_ibge = cl.cod_ibge AND fp.ano = cl.ano_safra AND fp.cod_produto = 40124;  -- soja

-- Indicador 2: receita estimada por hectare = (rendimento / kg_por_saca) × preço na colheita.
-- Mês de colheita por cultura: soja abr(4), milho mai(5), trigo out(10). Arroz não tem preço.
CREATE OR REPLACE VIEW mart.vw_receita_hectare AS
SELECT fp.cod_ibge,
       m.nome AS municipio,
       fp.ano,
       c.nome AS cultura,
       fp.cod_produto,
       fp.rendimento_medio_kg_ha,
       pm.preco_rs_saca AS preco_colheita_rs_saca,
       pm.kg_por_saca,
       round((fp.rendimento_medio_kg_ha / pm.kg_por_saca) * pm.preco_rs_saca, 2) AS receita_ha_rs
FROM mart.fato_producao fp
JOIN mart.dim_municipio m ON m.cod_ibge = fp.cod_ibge
JOIN mart.dim_cultura   c ON c.cod_produto = fp.cod_produto
JOIN mart.fato_preco_mensal pm
     ON pm.cod_produto = fp.cod_produto
    AND pm.ano = fp.ano
    AND pm.mes = CASE fp.cod_produto WHEN 40124 THEN 4 WHEN 40122 THEN 5 WHEN 40127 THEN 10 END
WHERE fp.rendimento_medio_kg_ha IS NOT NULL;

-- Indicador 3: sazonalidade do preço (média por cultura e mês, apoia decidir vender/armazenar).
CREATE OR REPLACE VIEW mart.vw_preco_sazonal AS
SELECT pm.cod_produto,
       c.nome AS cultura,
       pm.mes,
       round(avg(pm.preco_rs_saca), 2) AS preco_medio_rs_saca
FROM mart.fato_preco_mensal pm
JOIN mart.dim_cultura c ON c.cod_produto = pm.cod_produto
GROUP BY pm.cod_produto, c.nome, pm.mes;

-- mcp_ro enxerga SOMENTE as views (nunca as tabelas-base) — superfície controlada (ADR-004).
GRANT SELECT ON mart.vw_chuva_rendimento, mart.vw_receita_hectare, mart.vw_preco_sazonal TO mcp_ro;

RESET ROLE;
