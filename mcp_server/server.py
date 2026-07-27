"""AgroData — servidor MCP (Fase 3). Expõe o `mart` como ferramentas tipadas para assistentes de IA.

Cada tool roda uma consulta parametrizada fixa sobre uma VIEW, conectando como `mcp_ro`
(só-leitura). Sem text-to-SQL: a IA escolhe a tool, não escreve SQL (ADR-004). Log em stderr
(stdout é o transporte do protocolo MCP). Rodar via Claude Desktop (stdio) — ver README.
"""
from __future__ import annotations

import logging
import os
import sys
from decimal import Decimal

import psycopg
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, stream=sys.stderr)  # NUNCA stdout: é o canal MCP
log = logging.getLogger("agrodata-mcp")

LIMITE = 500  # teto de linhas por retorno (ADR-004)
MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

mcp = FastMCP("agrodata")
_embedder = None


def _conn() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("MCP_DB_HOST", "localhost"),
        port=os.environ.get("MCP_DB_PORT", "5432"),
        dbname=os.environ.get("MCP_DB_NAME", "agrodata"),
        user=os.environ.get("MCP_DB_USER", "mcp_ro"),
        password=os.environ["MCP_DB_PASSWORD"],
    )


def _query(sql: str, params: list) -> list[dict]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d.name for d in cur.description]
        return [
            {c: (float(v) if isinstance(v, Decimal) else v) for c, v in zip(cols, row)}
            for row in cur.fetchall()
        ]


@mcp.tool()
def producao(municipio: str, cultura: str, ano: int | None = None) -> list[dict]:
    """Produção agrícola no RS: área colhida (ha), quantidade produzida (t) e rendimento médio
    (kg/ha) por município e cultura. `municipio` e `cultura` aceitam nome parcial (ex.: 'Passo
    Fundo', 'soja'). `ano` é opcional; se omitido, retorna todos os anos. Fonte IBGE/SIDRA."""
    log.info("producao municipio=%r cultura=%r ano=%r", municipio, cultura, ano)
    sql = (
        "SELECT ano, municipio, cultura, area_colhida_ha, quantidade_produzida_t, "
        "rendimento_medio_kg_ha FROM mart.vw_producao "
        "WHERE municipio ILIKE %s AND cultura ILIKE %s"
    )
    params: list = [f"%{municipio}%", f"%{cultura}%"]
    if ano is not None:
        sql += " AND ano = %s"
        params.append(ano)
    sql += " ORDER BY ano, municipio LIMIT %s"
    params.append(LIMITE)
    return _query(sql, params)


@mcp.tool()
def chuva_no_ciclo(municipio: str, safra: int) -> list[dict]:
    """Chuva acumulada (mm) no ciclo da safra (out–mar) e evapotranspiração por município e safra
    (ano de colheita). Disponível só para 5 municípios do noroeste do RS. Fonte Open-Meteo."""
    log.info("chuva_no_ciclo municipio=%r safra=%r", municipio, safra)
    return _query(
        "SELECT municipio, ano_safra, chuva_ciclo_out_mar_mm, et0_ciclo_mm "
        "FROM mart.vw_clima_safra WHERE municipio ILIKE %s AND ano_safra = %s LIMIT %s",
        [f"%{municipio}%", safra, LIMITE],
    )


@mcp.tool()
def preco(produto: str, ano_inicio: int, ano_fim: int) -> list[dict]:
    """Preço mensal recebido pelo agricultor (R$/saca de 60 kg) por cultura (soja, milho ou trigo),
    entre ano_inicio e ano_fim. Fonte IPEADATA/DERAL-PR (proxy regional do Paraná)."""
    log.info("preco produto=%r %s-%s", produto, ano_inicio, ano_fim)
    return _query(
        "SELECT cultura, ano, mes, preco_rs_saca, kg_por_saca FROM mart.vw_preco_mensal "
        "WHERE cultura ILIKE %s AND ano BETWEEN %s AND %s ORDER BY ano, mes LIMIT %s",
        [f"%{produto}%", ano_inicio, ano_fim, LIMITE],
    )


@mcp.tool()
def receita_por_hectare(municipio: str, cultura: str, ano: int) -> list[dict]:
    """Receita estimada por hectare (R$) = (rendimento kg/ha ÷ saca) × preço na colheita, por
    município, cultura e ano. Estimativa (produção SIDRA × preço DERAL-PR), não a receita
    realizada."""
    log.info("receita_por_hectare municipio=%r cultura=%r ano=%r", municipio, cultura, ano)
    return _query(
        "SELECT municipio, ano, cultura, rendimento_medio_kg_ha, preco_colheita_rs_saca, "
        "receita_ha_rs FROM mart.vw_receita_hectare "
        "WHERE municipio ILIKE %s AND cultura ILIKE %s AND ano = %s ORDER BY municipio LIMIT %s",
        [f"%{municipio}%", f"%{cultura}%", ano, LIMITE],
    )


@mcp.tool()
def busca_metadados(pergunta: str) -> list[dict]:
    """Busca semântica no dicionário de dados do AgroData: dada uma pergunta em linguagem natural,
    retorna quais objetos/tools respondem (com descrição e relevância). NÃO retorna dado bruto —
    serve para descobrir qual ferramenta usar (RAG só nos metadados, ADR-007)."""
    global _embedder
    log.info("busca_metadados pergunta=%r", pergunta)
    if _embedder is None:
        from fastembed import TextEmbedding

        _embedder = TextEmbedding(model_name=MODELO)
    emb = next(iter(_embedder.embed([pergunta])))
    vec = "[" + ",".join(f"{x:.6f}" for x in emb) + "]"
    return _query(
        "SELECT objeto, descricao, "
        "round((1 - (embedding <=> %s::vector))::numeric, 3) AS score "
        "FROM mart.dicionario_dados ORDER BY embedding <=> %s::vector LIMIT 5",
        [vec, vec],
    )


if __name__ == "__main__":
    mcp.run()  # transporte stdio (padrão)
