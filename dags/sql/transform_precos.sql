-- AgroData — agrega raw.precos_ipeadata → mart.fato_preco_mensal (preço por cultura e mês).
-- A série DERAL já é mensal (1 ponto/mês); o AVG apenas consolida em caso de duplicata.
INSERT INTO mart.fato_preco_mensal (cod_produto, ano, mes, preco_rs_saca, kg_por_saca)
SELECT cod_produto,
       EXTRACT(YEAR  FROM data)::int AS ano,
       EXTRACT(MONTH FROM data)::int AS mes,
       AVG(preco_rs)     AS preco_rs_saca,
       MAX(kg_por_saca)  AS kg_por_saca
FROM raw.precos_ipeadata
WHERE preco_rs IS NOT NULL
GROUP BY cod_produto, EXTRACT(YEAR FROM data), EXTRACT(MONTH FROM data)
ON CONFLICT (cod_produto, ano, mes) DO UPDATE SET
       preco_rs_saca = EXCLUDED.preco_rs_saca,
       kg_por_saca   = EXCLUDED.kg_por_saca;
