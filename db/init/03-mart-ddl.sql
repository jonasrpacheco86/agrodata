-- AgroData — DDL de raw e mart (Fase 1). Roda no 1º init, após 02-security.sh.
-- Os objetos são criados COMO airflow_rw para que ele seja o dono (escreve) e para que as
-- default privileges definidas no 02 concedam SELECT ao metabase_ro automaticamente.
SET ROLE airflow_rw;

-- ── RAW: PAM/SIDRA como recebido (formato longo: 1 linha por variável) ─────────
CREATE TABLE IF NOT EXISTS raw.pam_sidra (
    municipio_cod   integer,
    municipio_nome  text,
    ano             integer,
    produto_cod     integer,
    produto_nome    text,
    variavel_cod    integer,
    variavel_nome   text,
    unidade         text,
    valor           numeric,
    ingested_at     timestamptz NOT NULL DEFAULT now()
);

-- ── MART: modelo dimensional (grão = município × ano × cultura) ────────────────
CREATE TABLE IF NOT EXISTS mart.dim_municipio (
    cod_ibge  integer PRIMARY KEY,
    nome      text NOT NULL,
    uf        char(2) NOT NULL DEFAULT 'RS'
);

CREATE TABLE IF NOT EXISTS mart.dim_cultura (
    cod_produto integer PRIMARY KEY,
    nome        text NOT NULL
);

CREATE TABLE IF NOT EXISTS mart.fato_producao (
    cod_ibge                integer NOT NULL REFERENCES mart.dim_municipio (cod_ibge),
    ano                     integer NOT NULL,
    cod_produto             integer NOT NULL REFERENCES mart.dim_cultura (cod_produto),
    area_colhida_ha         numeric,
    quantidade_produzida_t  numeric,
    rendimento_medio_kg_ha  numeric,
    PRIMARY KEY (cod_ibge, ano, cod_produto)
);

-- View achatada consumida pelo Metabase e (Fase 3) pelo servidor MCP.
CREATE OR REPLACE VIEW mart.vw_producao AS
SELECT f.ano,
       m.cod_ibge,
       m.nome  AS municipio,
       m.uf,
       c.cod_produto,
       c.nome  AS cultura,
       f.area_colhida_ha,
       f.quantidade_produzida_t,
       f.rendimento_medio_kg_ha
FROM mart.fato_producao f
JOIN mart.dim_municipio m ON m.cod_ibge   = f.cod_ibge
JOIN mart.dim_cultura   c ON c.cod_produto = f.cod_produto;

-- mcp_ro enxerga SOMENTE a view (nunca as tabelas-base) — superfície controlada (ADR-004).
GRANT SELECT ON mart.vw_producao TO mcp_ro;

RESET ROLE;
