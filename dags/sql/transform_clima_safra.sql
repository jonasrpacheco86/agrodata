-- AgroData — agrega raw.clima_openmeteo (diário) → mart.fato_clima_safra (ciclo da safra).
-- Ciclo da soja no RS: out(Y-1) a mar(Y); a safra é rotulada pelo ano de colheita Y.
INSERT INTO mart.fato_clima_safra (cod_ibge, ano_safra, chuva_ciclo_out_mar_mm, et0_ciclo_mm)
SELECT cod_ibge,
       (CASE WHEN EXTRACT(MONTH FROM data) >= 10
             THEN EXTRACT(YEAR FROM data) + 1
             ELSE EXTRACT(YEAR FROM data) END)::int AS ano_safra,
       SUM(precipitation_mm) AS chuva_ciclo_out_mar_mm,
       SUM(et0_mm)           AS et0_ciclo_mm
FROM raw.clima_openmeteo
WHERE EXTRACT(MONTH FROM data) IN (10, 11, 12, 1, 2, 3)   -- só o ciclo out–mar
GROUP BY cod_ibge, ano_safra
ON CONFLICT (cod_ibge, ano_safra) DO UPDATE SET
       chuva_ciclo_out_mar_mm = EXCLUDED.chuva_ciclo_out_mar_mm,
       et0_ciclo_mm           = EXCLUDED.et0_ciclo_mm;
