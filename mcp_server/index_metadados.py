"""Popula mart.dicionario_dados com os embeddings do dicionário de dados (RAG).

Roda uma vez (e quando o dicionário muda). Conecta como airflow_rw (escrita); o servidor MCP
lê como mcp_ro. Uso:
    MCP_DB_HOST=localhost AIRFLOW_DB_PASSWORD=... python mcp_server/index_metadados.py
"""
from __future__ import annotations

import os
import sys

import psycopg
from dicionario import DICIONARIO
from fastembed import TextEmbedding

MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # 384 dims, multilíngue


def _dsn() -> str:
    return (
        f"host={os.environ.get('MCP_DB_HOST', 'localhost')} "
        f"port={os.environ.get('MCP_DB_PORT', '5432')} "
        f"dbname={os.environ.get('MCP_DB_NAME', 'agrodata')} "
        f"user=airflow_rw password={os.environ['AIRFLOW_DB_PASSWORD']}"
    )


def main() -> None:
    print(f"Carregando modelo {MODELO} (baixa ~0.22 GB na 1ª vez)...", file=sys.stderr)
    modelo = TextEmbedding(model_name=MODELO)
    descricoes = [d for _, d in DICIONARIO]
    embeddings = list(modelo.embed(descricoes))

    with psycopg.connect(_dsn()) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM mart.dicionario_dados")
        for (objeto, descricao), emb in zip(DICIONARIO, embeddings):
            vec = "[" + ",".join(f"{x:.6f}" for x in emb) + "]"
            cur.execute(
                "INSERT INTO mart.dicionario_dados (objeto, descricao, embedding) "
                "VALUES (%s, %s, %s::vector)",
                (objeto, descricao, vec),
            )
        conn.commit()
    print(f"Indexados {len(DICIONARIO)} objetos em mart.dicionario_dados.", file=sys.stderr)


if __name__ == "__main__":
    main()
