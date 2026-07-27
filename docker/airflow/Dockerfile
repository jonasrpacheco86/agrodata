# Imagem do Airflow do AgroData: base oficial pinada + deps das DAGs auditadas (ADR-003).
# Existe para instalar requests 2.33.0 (a base 2.10.3 traz 2.32.3, com CVE que o CI pegou).
FROM apache/airflow:2.10.3
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
