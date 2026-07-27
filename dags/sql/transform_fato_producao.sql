-- AgroData — transforma raw.pam_sidra (longo) → mart (dimensional). Idempotente.
-- Executada pela task `transformar` da DAG, conectada como airflow_rw.

-- 1) Dimensões (upsert a partir do que veio no raw).
--    O nome do município vem como "Aceguá - RS" no seletor de RS; removemos o sufixo.
INSERT INTO mart.dim_municipio (cod_ibge, nome, uf)
SELECT DISTINCT municipio_cod,
       regexp_replace(municipio_nome, '\s*-\s*RS$', ''),
       'RS'
FROM raw.pam_sidra
WHERE municipio_cod IS NOT NULL
ON CONFLICT (cod_ibge) DO UPDATE SET nome = EXCLUDED.nome;

INSERT INTO mart.dim_cultura (cod_produto, nome)
SELECT DISTINCT produto_cod, produto_nome
FROM raw.pam_sidra
WHERE produto_cod IS NOT NULL
ON CONFLICT (cod_produto) DO UPDATE SET nome = EXCLUDED.nome;

-- 2) Fato: pivota as 3 variáveis (uma linha por variável no raw) em colunas.
--    216 = área colhida (ha), 214 = quantidade produzida (t), 112 = rendimento médio (kg/ha).
INSERT INTO mart.fato_producao
    (cod_ibge, ano, cod_produto, area_colhida_ha, quantidade_produzida_t, rendimento_medio_kg_ha)
SELECT municipio_cod, ano, produto_cod,
       max(valor) FILTER (WHERE variavel_cod = 216) AS area_colhida_ha,
       max(valor) FILTER (WHERE variavel_cod = 214) AS quantidade_produzida_t,
       max(valor) FILTER (WHERE variavel_cod = 112) AS rendimento_medio_kg_ha
FROM raw.pam_sidra
WHERE municipio_cod IS NOT NULL AND produto_cod IS NOT NULL AND ano IS NOT NULL
GROUP BY municipio_cod, ano, produto_cod
ON CONFLICT (cod_ibge, ano, cod_produto) DO UPDATE SET
       area_colhida_ha        = EXCLUDED.area_colhida_ha,
       quantidade_produzida_t = EXCLUDED.quantidade_produzida_t,
       rendimento_medio_kg_ha = EXCLUDED.rendimento_medio_kg_ha;
