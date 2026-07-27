"""AgroData — Fase 2: preços (IPEADATA / DERAL-PR) → raw → mart.

Extrai o preço mensal recebido pelo agricultor (soja/milho/trigo) das séries DERAL-PR publicadas
pelo IPEADATA e grava em mart.fato_preco_mensal. É um proxy regional (Paraná ≈ RS; ver ADR-006),
não RS-específico. Trigger manual, idempotente. Conecta como airflow_rw.
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
IPEADATA_URL = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{cod}')"

# (série DERAL, cod_produto do dim_cultura, kg por saca). Arroz está inativo no IPEADATA → fora.
SERIES = [
    ("DERAL12_PRSO12", 40124, 60),   # soja
    ("DERAL12_PRMI12", 40122, 60),   # milho
    ("DERAL12_PRTRG12", 40127, 60),  # trigo
]


def _dsn() -> str:
    c = BaseHook.get_connection(CONN_ID)
    return (
        f"host={c.host} port={c.port or 5432} dbname={c.schema} "
        f"user={c.login} password={c.password}"
    )


@dag(
    dag_id="precos_ipeadata",
    schedule=None,
    start_date=dt.datetime(2024, 1, 1),
    catchup=False,
    tags=["agrodata", "precos"],
    params={"ano_inicio": 2012},  # antes disso os valores vêm em moedas antigas (cruzeiro etc.)
    doc_md=__doc__,
)
def precos_ipeadata():
    @task
    def extrair(**context) -> int:
        ano_inicio = int(context["params"]["ano_inicio"])
        total = 0
        with psycopg2.connect(_dsn()) as conn:
            for serie_cod, cod_produto, kg_por_saca in SERIES:
                resp = requests.get(IPEADATA_URL.format(cod=serie_cod), timeout=90)
                resp.raise_for_status()
                pontos = resp.json().get("value", [])
                registros = []
                for pt in pontos:
                    data = (pt.get("VALDATA") or "")[:10]  # 'AAAA-MM-DD'
                    if not data or int(data[:4]) < ano_inicio:
                        continue
                    preco = pt.get("VALVALOR")
                    registros.append((serie_cod, cod_produto, data, preco, kg_por_saca))
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM raw.precos_ipeadata WHERE serie_cod = %s", (serie_cod,)
                    )
                    if registros:
                        execute_values(
                            cur,
                            "INSERT INTO raw.precos_ipeadata "
                            "(serie_cod, cod_produto, data, preco_rs, kg_por_saca) VALUES %s",
                            registros,
                        )
                conn.commit()
                total += len(registros)
        return total

    @task
    def transformar() -> None:
        sql = (SQL_DIR / "transform_precos.sql").read_text(encoding="utf-8")
        with psycopg2.connect(_dsn()) as conn, conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()

    extrair() >> transformar()


precos_ipeadata()
