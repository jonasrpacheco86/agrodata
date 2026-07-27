"""AgroData — Fase 1: IBGE/SIDRA (PAM, tabela 5457) → raw → mart.

Extrai Produção Agrícola Municipal do RS (área colhida, quantidade produzida, rendimento médio)
para 4 culturas e grava em raw.pam_sidra; a task de transform pivota para o mart dimensional.
Trigger manual (schedule=None) = "atualiza com um clique". Idempotente por ano.
Conecta ao DW como airflow_rw (menor privilégio, ADR-002) via a Connection `agrodata_dw`.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import psycopg2
import requests
from airflow.decorators import dag, task
from airflow.hooks.base import BaseHook
from psycopg2.extras import execute_values

CONN_ID = "agrodata_dw"
SQL_DIR = Path(__file__).parent / "sql"

# PAM 5457: v214 (qtd produzida, t), v216 (área colhida, ha), v112 (rendimento médio, kg/ha);
# c782 = produto; RS inteiro via seletor "in n3 43". Culturas: soja/milho/trigo/arroz.
SIDRA_URL = (
    "https://apisidra.ibge.gov.br/values/t/5457/n6/in%20n3%2043"
    "/v/214,216,112/p/{ano}/c782/40124,40122,40127,40102"
)


def _dsn() -> str:
    c = BaseHook.get_connection(CONN_ID)
    return (
        f"host={c.host} port={c.port or 5432} dbname={c.schema} "
        f"user={c.login} password={c.password}"
    )


def _num(v):
    """SIDRA devolve valor como texto; '..' (indisponível), '-' e '...' viram NULL."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@dag(
    dag_id="ibge_sidra_producao",
    schedule=None,
    start_date=dt.datetime(2024, 1, 1),
    catchup=False,
    tags=["agrodata", "ibge"],
    params={"ano_inicio": 2013, "ano_fim": 2023},
    doc_md=__doc__,
)
def ibge_sidra_producao():
    @task
    def extrair(**context) -> int:
        p = context["params"]
        anos = range(int(p["ano_inicio"]), int(p["ano_fim"]) + 1)
        total = 0
        with psycopg2.connect(_dsn()) as conn:
            for ano in anos:
                resp = requests.get(SIDRA_URL.format(ano=ano), timeout=90)
                resp.raise_for_status()
                data = resp.json()
                # data[0] é o cabeçalho (rótulos); pode não haver dados para o ano.
                linhas = data[1:] if isinstance(data, list) and len(data) > 1 else []
                registros = [
                    (
                        int(x["D1C"]), x["D1N"], int(x["D3C"]),
                        int(x["D4C"]), x["D4N"],
                        int(x["D2C"]), x["D2N"], x["MN"], _num(x["V"]),
                    )
                    for x in linhas
                ]
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM raw.pam_sidra WHERE ano = %s", (ano,))
                    if registros:
                        execute_values(
                            cur,
                            "INSERT INTO raw.pam_sidra (municipio_cod, municipio_nome, ano, "
                            "produto_cod, produto_nome, variavel_cod, variavel_nome, unidade, "
                            "valor) VALUES %s",
                            registros,
                        )
                conn.commit()
                total += len(registros)
        return total

    @task
    def transformar() -> None:
        sql = (SQL_DIR / "transform_fato_producao.sql").read_text(encoding="utf-8")
        with psycopg2.connect(_dsn()) as conn, conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()

    extrair() >> transformar()


ibge_sidra_producao()
