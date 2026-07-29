"""Testes da borda pública do servidor MCP: rate limit e bearer (ADR-009/ADR-010).

Cobre os invariantes que uma leitura desatenta desfaz sem perceber — teto que não realimenta a
janela, contadores que não se misturam, dicionário que não cresce sem limite, e comparação do
bearer que não vira 500 diante de header não-ASCII.

Roda sem dependência de runtime: `psycopg` e `mcp` entram como stubs, porque o que está sob teste
é a lógica da borda, não o acesso ao banco. O caminho HTTP de ponta a ponta (200/401/429 reais) é
verificado pelo roteiro em `deploy/README.md`.

    python -m pytest mcp_server/ -q
"""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest


def _carrega_server():
    """Importa `server.py` com stubs no lugar das dependências de runtime."""
    psycopg = types.ModuleType("psycopg")
    psycopg.Connection = object
    psycopg.connect = lambda *a, **k: None
    sys.modules["psycopg"] = psycopg

    class _FastMCPFake:
        def __init__(self, *a, **k):
            pass

        def tool(self, *a, **k):
            return lambda f: f

    fastmcp = types.ModuleType("mcp.server.fastmcp")
    fastmcp.FastMCP = _FastMCPFake
    sys.modules["mcp"] = types.ModuleType("mcp")
    sys.modules["mcp.server"] = types.ModuleType("mcp.server")
    sys.modules["mcp.server.fastmcp"] = fastmcp

    sys.path.insert(0, str(Path(__file__).parent))
    return importlib.import_module("server")


@pytest.fixture
def srv():
    """Módulo carregado com os contadores zerados (são estado global de processo)."""
    modulo = _carrega_server()
    modulo._hits_ip.clear()
    modulo._hits_auth.clear()
    return modulo


def test_teto_por_ip_para_exatamente_no_limite(srv):
    aceitos = sum(srv._aceita_ip("1.2.3.4") for _ in range(srv.TETO_IP * 2))
    assert aceitos == srv.TETO_IP


def test_requisicao_recusada_nao_realimenta_a_janela(srv):
    """Contar o próprio 429 manteria o teto estourado enquanto a enxurrada durasse."""
    for _ in range(srv.TETO_IP * 5):
        srv._aceita_ip("1.2.3.4")
    assert len(srv._hits_ip["1.2.3.4"]) == srv.TETO_IP


def test_ip_volta_a_ser_aceito_depois_da_janela(srv, monkeypatch):
    for _ in range(srv.TETO_IP * 5):
        srv._aceita_ip("1.2.3.4")
    agora = srv.time.monotonic() + srv.JANELA_S + 1
    monkeypatch.setattr(srv.time, "monotonic", lambda: agora)
    assert srv._aceita_ip("1.2.3.4")


def test_ip_curinga_nao_contamina_o_contador_global(srv):
    """`*` já foi a sentinela do contador global no mesmo dicionário dos IPs."""
    for _ in range(10):
        srv._aceita_ip("*")
    assert srv._hits_auth == []


def test_teto_global_conta_uma_vez_por_requisicao(srv):
    aceitos = sum(srv._aceita_autenticado() for _ in range(srv.TETO_AUTENTICADO * 2))
    assert aceitos == srv.TETO_AUTENTICADO


def test_dicionario_de_ips_tem_teto_duro(srv):
    """Sem isto, um X-Forwarded-For variável cria uma chave por requisição até estourar a RAM."""
    for i in range(srv.MAX_CHAVES * 3):
        srv._aceita_ip(f"10.0.{i // 256}.{i % 256}")
    assert len(srv._hits_ip) <= srv.MAX_CHAVES


def test_bearer_nao_ascii_recusa_sem_excecao(srv):
    """Em `str`, `compare_digest` levantaria TypeError: 500 acionável sem token."""
    assert srv._bearer_confere("Bearer \xff", b"Bearer abc") is False


def test_bearer_correto_confere(srv):
    assert srv._bearer_confere("Bearer abc", b"Bearer abc")


def test_bearer_errado_recusa(srv):
    assert srv._bearer_confere("Bearer errado", b"Bearer abc") is False
