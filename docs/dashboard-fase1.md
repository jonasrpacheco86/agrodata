# Dashboard da Fase 1 (Metabase)

O dashboard é montado na UI do Metabase (Metabase-as-code fica no `IDEIAS.md`). Passo a passo
para reproduzir os 3 gráficos que contam a história da Fase 1.

## 1. Conectar o data source (com menor privilégio)

Metabase → **Admin → Databases → Add database**:

| Campo | Valor |
|---|---|
| Database type | PostgreSQL |
| Host | `postgres` |
| Port | `5432` |
| Database name | `agrodata` |
| Username | `metabase_ro` |
| Password | o `METABASE_DB_PASSWORD` do seu `.env` |

`metabase_ro` só enxerga o schema `mart` (nunca `raw`) — é a prova viva do ADR-002. Todas as
questões abaixo usam a view **`mart.vw_producao`**.

## 2. As três questões (SQL nativo)

**a) Produção do RS por ano e cultura** (gráfico de linha — eixo X: ano, série: cultura)
```sql
SELECT ano, cultura, SUM(quantidade_produzida_t) AS producao_t
FROM mart.vw_producao
GROUP BY ano, cultura
ORDER BY ano;
```

**b) Top 10 municípios produtores de soja (último ano)** (gráfico de barras)
```sql
SELECT municipio, SUM(quantidade_produzida_t) AS producao_t
FROM mart.vw_producao
WHERE cultura = 'Soja (em grão)'
  AND ano = (SELECT MAX(ano) FROM mart.vw_producao)
  AND quantidade_produzida_t IS NOT NULL   -- municípios sem soja têm valor NULL (SIDRA '..')
GROUP BY municipio
ORDER BY producao_t DESC                    -- sem o filtro acima, NULL ordena primeiro em DESC
LIMIT 10;
```

**c) Rendimento médio (kg/ha) por ano e cultura** (gráfico de linha — tendência)
```sql
SELECT ano, cultura, AVG(rendimento_medio_kg_ha) AS rendimento_medio_kg_ha
FROM mart.vw_producao
WHERE rendimento_medio_kg_ha IS NOT NULL
GROUP BY ano, cultura
ORDER BY ano;
```

## 3. Montar o dashboard
Salve as três questões e adicione-as a um dashboard "AgroData — Produção RS". Critério de pronto
da Fase 1: **um leigo entende os gráficos** sem explicação.

> Nota de honestidade (para o README/entrevista): o rendimento médio (var 112) vem pronto do
> SIDRA; a Fase 1 apenas o exibe. O cruzamento chuva × rendimento e receita/ha entra na Fase 2.
