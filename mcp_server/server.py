"""AgroData — servidor MCP (Fase 3). Expõe o `mart` como ferramentas tipadas para assistentes de IA.

Cada tool roda uma consulta parametrizada fixa sobre uma VIEW, conectando como `mcp_ro`
(só-leitura). Sem text-to-SQL: a IA escolhe a tool, não escreve SQL (ADR-004). Log em stderr
(stdout é o transporte do protocolo MCP). Rodar via Claude Desktop (stdio) — ver README.
"""
from __future__ import annotations

import hmac
import logging
import os
import sys
import time
from decimal import Decimal

import psycopg
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, stream=sys.stderr)  # NUNCA stdout: é o canal MCP
log = logging.getLogger("agrodata-mcp")

LIMITE = 500  # teto de linhas por retorno (ADR-004)
MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# Consulta que trava é compute queimado na cota do banco serverless (ADR-010).
TIMEOUT_MS = 15_000

mcp = FastMCP("agrodata")
_embedder = None


def _conn() -> psycopg.Connection:
    # MCP_DB_URL (string de conexão, ex.: Neon com sslmode=require) tem prioridade;
    # senão monta a partir dos params soltos (dev local).
    url = os.environ.get("MCP_DB_URL")
    if url:
        return psycopg.connect(url)
    return psycopg.connect(
        host=os.environ.get("MCP_DB_HOST", "localhost"),
        port=os.environ.get("MCP_DB_PORT", "5432"),
        dbname=os.environ.get("MCP_DB_NAME", "agrodata"),
        user=os.environ.get("MCP_DB_USER", "mcp_ro"),
        password=os.environ["MCP_DB_PASSWORD"],
    )


def _query(sql: str, params: list) -> list[dict]:
    with _conn() as conn, conn.cursor() as cur:
        # `SET LOCAL` dentro da transação, e não `options=-c ...` no pacote de startup: um pooler
        # em modo transaction (PgBouncer, que é o que a Neon oferece no host `-pooler`) recusa
        # parâmetro de startup arbitrário. Assim o teto vale nos dois hosts, direto ou pooled.
        # O `mcp_ro` também carrega o mesmo teto no servidor (deploy/neon_roles.sql) — este SET é
        # o que garante o limite quando o papel do ambiente local não tem o default aplicado.
        cur.execute(f"SET LOCAL statement_timeout = {TIMEOUT_MS}")  # int nosso, não vem de entrada
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


# --- Rate limit da borda pública (ADR-009/ADR-010) --------------------------------------------
# Janela deslizante em memória, sem dependência nova. São dois tetos, com propósitos distintos e
# aplicados em momentos distintos:
#
# - **por IP, antes da auth**: contém a enxurrada barata. A chave vem do `X-Forwarded-For`, que é
#   falsificável, então isto é dissuasivo — não uma garantia.
# - **global, depois da auth**: é o teto que protege a cota de compute do banco. Fica depois de
#   propósito: se valesse também para tráfego anônimo, qualquer scanner esgotaria o orçamento e
#   negaria o serviço justamente a quem tem o token.
#
# Requisição recusada **não** é contabilizada: contar o próprio 429 realimenta a janela, e uma
# enxurrada sustentada manteria o teto estourado para sempre (negação de serviço permanente).
#
# Concorrência: as funções abaixo não têm `await`, então rodam atômicas no laço de eventos.
JANELA_S = 60.0
TETO_IP = 30
TETO_AUTENTICADO = 120
MAX_CHAVES = 2_000  # teto duro do dicionário (ver `_podar`)
_hits_ip: dict[str, list[float]] = {}
_hits_auth: list[float] = []


def _sob_teto(janela: list[float], teto: int, agora: float) -> bool:
    """Descarta o que saiu da janela e registra o hit — mas só se couber no teto."""
    janela[:] = [t for t in janela if agora - t < JANELA_S]
    if len(janela) >= teto:
        return False
    janela.append(agora)
    return True


def _podar(agora: float) -> None:
    """Mantém `_hits_ip` limitado. Sem isto, uma enxurrada variando o `X-Forwarded-For` cria uma
    chave por requisição — todas dentro da janela, nenhuma expirada — e a instância free (512 MB)
    morre por OOM antes de qualquer teto disparar."""
    if len(_hits_ip) < MAX_CHAVES:
        return
    for chave in [k for k, v in _hits_ip.items() if agora - v[-1] >= JANELA_S]:
        del _hits_ip[chave]
    excedente = len(_hits_ip) - MAX_CHAVES + 1  # +1: abre espaço para a chave que entra a seguir
    if excedente > 0:  # nada expirou: despeja quem bateu há mais tempo, para o teto ser duro
        for chave in sorted(_hits_ip, key=lambda k: _hits_ip[k][-1])[:excedente]:
            del _hits_ip[chave]


def _aceita_ip(ip: str) -> bool:
    agora = time.monotonic()
    _podar(agora)
    return _sob_teto(_hits_ip.setdefault(ip, []), TETO_IP, agora)


def _aceita_autenticado() -> bool:
    return _sob_teto(_hits_auth, TETO_AUTENTICADO, time.monotonic())


def _bearer_confere(recebido: str, esperado: bytes) -> bool:
    """Compara o header `Authorization` em tempo constante — e em **bytes**.

    `hmac.compare_digest` sobre `str` levanta `TypeError` diante de qualquer caractere não-ASCII, e
    o header vem do cliente: em `str`, um `Authorization: Bearer \xff` viraria 500 com traceback,
    acionável sem token nenhum. Starlette decodifica headers em latin-1, então é por latin-1 que
    se volta aos bytes originais."""
    return hmac.compare_digest(recebido.encode("latin-1", "replace"), esperado)


def _run() -> None:
    """stdio (padrão, Claude Desktop local) ou http+bearer (deploy público)."""
    if os.environ.get("MCP_TRANSPORT") == "http":
        import uvicorn
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        token = os.environ["MCP_AUTH_TOKEN"]  # obrigatório no modo público
        if not token.isascii():  # senão o header nunca bate e o serviço responde 401 para sempre
            log.warning("MCP_AUTH_TOKEN tem caractere não-ASCII; gere com `openssl rand -hex 32`")
        esperado = f"Bearer {token}".encode()  # bytes: ver `_bearer_confere`

        async def health(_request):  # /healthz sem auth (health check do host)
            # Responde estático de propósito: um SELECT aqui acordaria o banco serverless a cada
            # ping do host e queimaria a cota sem ninguém usar o demo (ADR-010).
            return JSONResponse({"status": "ok"})

        def _limitado(ip, path, motivo):
            log.warning("MCP http: 429 (%s) ip=%s path=%s", motivo, ip, path)
            return JSONResponse({"error": "rate limited"}, status_code=429,
                                headers={"Retry-After": str(int(JANELA_S))})

        class BordaPublica(BaseHTTPMiddleware):
            """Teto por IP antes da autenticação (enxurrada anônima custa pouco) e teto global
            depois dela (a cota do banco só é consumida por quem passou no bearer)."""

            async def dispatch(self, request, call_next):
                # /healthz fica fora dos dois tetos de propósito: o 429 não impediria a instância
                # de acordar (a requisição já chegou ao processo), e estrangular a rota reprovaria
                # o health check do próprio Render — derrubaria o demo para poupar um JSON.
                if request.url.path == "/healthz":
                    return await call_next(request)
                ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                      or (request.client.host if request.client else "desconhecido"))
                if not _aceita_ip(ip):
                    return _limitado(ip, request.url.path, "ip")
                if not _bearer_confere(request.headers.get("authorization", ""), esperado):
                    log.warning("MCP http: 401 ip=%s path=%s", ip, request.url.path)
                    return JSONResponse({"error": "unauthorized"}, status_code=401)
                if not _aceita_autenticado():
                    return _limitado(ip, request.url.path, "global")
                return await call_next(request)

        app = mcp.streamable_http_app()
        app.router.routes.append(Route("/healthz", health))
        app.add_middleware(BordaPublica)
        uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
    else:
        mcp.run()  # stdio


if __name__ == "__main__":
    _run()
