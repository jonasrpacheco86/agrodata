# Dashboard da Fase 2 (Metabase) — os 3 indicadores

Fio narrativo **passado → impacto → decisão**. Data source: o mesmo `metabase_ro` da Fase 1
(só enxerga `mart`). As views já entregam os cruzamentos prontos.

## Indicador 1 — Chuva no ciclo × rendimento da soja (passado)
Explica o que aconteceu: safras secas derrubam o rendimento. Caso-vitrine: **2021/22** (La Niña).
Gráfico combinado (barras = chuva, linha = rendimento) por safra, filtrável por município.
```sql
SELECT ano, municipio, chuva_ciclo_out_mar_mm, rendimento_medio_kg_ha
FROM mart.vw_chuva_rendimento
ORDER BY municipio, ano;
```

## Indicador 2 — Receita estimada por hectare (impacto)
Mede o bolso: `receita_ha = (rendimento_kg_ha / 60) × preço_da_saca_na_colheita`. Cruza produção
(SIDRA) e preço (DERAL-PR). Gráfico de linha por ano, série por cultura.
```sql
SELECT ano, cultura, ROUND(AVG(receita_ha_rs)) AS receita_ha_rs
FROM mart.vw_receita_hectare
GROUP BY ano, cultura
ORDER BY ano;
```
> Leitura: em anos de rendimento ruim, um preço alto pode **salvar parcialmente** a receita — é o
> vínculo narrativo com o indicador 1 (a seca derruba o rendimento, o preço amortece).

## Indicador 3 — Sazonalidade do preço × calendário de colheita (decisão)
Apoia "vender na colheita ou armazenar?". Preço médio por mês (padrão sazonal), com o mês de
colheita marcado. Gráfico de linha (eixo X = mês 1–12), série por cultura.
```sql
SELECT mes, cultura, preco_medio_rs_saca
FROM mart.vw_preco_sazonal
ORDER BY cultura, mes;
```
Calendário de colheita para anotar no gráfico: **soja** abr, **milho** mai, **trigo** out.

## Honestidade a registrar (README/entrevista)
- Preço é **proxy do Paraná** (DERAL-PR), não RS — ver [ADR-006](adr/ADR-006-precos-deral-pr-proxy.md).
- Clima cobre **5 municípios** do noroeste do RS (não o estado todo) — de propósito, escopo da V1.
- Rendimento vem pronto do SIDRA; a receita/ha é uma **estimativa** (rendimento × preço), não a
  receita realizada de nenhum produtor específico.
