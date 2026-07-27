"""AgroData — Fase 2: clima (Open-Meteo Historical) → raw → mart.

Extrai precipitação diária e evapotranspiração (ET0) de 5 municípios do noroeste do RS e agrega
a chuva do ciclo da safra (out–mar) em mart.fato_clima_safra. Fonte: Open-Meteo (open-meteo.com),
citada no README conforme a licença. Trigger manual, idempotente. Conecta como airflow_rw.
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
OPENMETEO_URL = "https://archive-api.open-meteo.com/v1/archive"

# 5 municípios do noroeste do RS (cod_ibge conferido contra mart.dim_municipio; lat/lon aproximados
# — a Open-Meteo faz snap para a célula de grade mais próxima).
MUNICIPIOS = [
    (4306106, -28.6386, -53.6062),  # Cruz Alta
    (4310207, -28.3878, -53.9147),  # Ijuí
    (4313706, -27.8994, -53.3138),  # Palmeira das Missões
    (4314100, -28.2628, -52.4067),  # Passo Fundo
    (4317202, -27.8708, -54.4815),  # Santa Rosa
]


def _dsn() -> str:
    c = BaseHook.get_connection(CONN_ID)
    return (
        f"host={c.host} port={c.port or 5432} dbname={c.schema} "
        f"user={c.login} password={c.password}"
    )


@dag(
    dag_id="clima_openmeteo",
    schedule=None,
    start_date=dt.datetime(2024, 1, 1),
    catchup=False,
    tags=["agrodata", "clima"],
    params={"ano_inicio": 2012, "ano_fim": 2023},  # 2012 dá out–dez p/ a safra 2013
    doc_md=__doc__,
)
def clima_openmeteo():
    @task
    def extrair(**context) -> int:
        p = context["params"]
        start = f"{int(p['ano_inicio'])}-01-01"
        end = f"{int(p['ano_fim'])}-12-31"
        total = 0
        with psycopg2.connect(_dsn()) as conn:
            for cod_ibge, lat, lon in MUNICIPIOS:
                resp = requests.get(
                    OPENMETEO_URL,
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "start_date": start,
                        "end_date": end,
                        "daily": "precipitation_sum,et0_fao_evapotranspiration",
                        "timezone": "America/Sao_Paulo",
                    },
                    timeout=90,
                )
                resp.raise_for_status()
                daily = resp.json().get("daily", {})
                datas = daily.get("time", [])
                chuva = daily.get("precipitation_sum", [])
                et0 = daily.get("et0_fao_evapotranspiration", [])
                registros = [
                    (cod_ibge, datas[i], chuva[i], et0[i]) for i in range(len(datas))
                ]
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM raw.clima_openmeteo WHERE cod_ibge = %s", (cod_ibge,))
                    if registros:
                        execute_values(
                            cur,
                            "INSERT INTO raw.clima_openmeteo "
                            "(cod_ibge, data, precipitation_mm, et0_mm) VALUES %s",
                            registros,
                        )
                conn.commit()
                total += len(registros)
        return total

    @task
    def transformar() -> None:
        sql = (SQL_DIR / "transform_clima_safra.sql").read_text(encoding="utf-8")
        with psycopg2.connect(_dsn()) as conn, conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()

    extrair() >> transformar()


clima_openmeteo()
