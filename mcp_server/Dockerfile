# Imagem do servidor MCP do AgroData para deploy público (HTTP + bearer).
# Contexto de build: raiz do repositório.
# Baseline do ADR-001/ADR-009: tag fixada (nunca latest) e processo non-root.
FROM python:3.12-slim
WORKDIR /app

COPY mcp_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV MCP_TRANSPORT=http \
    PORT=8000 \
    PYTHONPATH=/app/mcp_server \
    HOME=/app \
    XDG_CACHE_HOME=/app/.cache \
    HF_HOME=/app/.cache/huggingface \
    FASTEMBED_CACHE_PATH=/app/.cache/fastembed

# Usuário sem privilégio (ADR-009). O cache precisa existir e ser dele ANTES do download, senão o
# modelo baixaria de novo (como root não daria para ler) no primeiro cold start. São dois caches:
# o do fastembed e o do huggingface_hub (que baixa o arquivo) — faltando o segundo, o build falha
# com "Permission denied" no xet.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin agrodata \
    && mkdir -p "$FASTEMBED_CACHE_PATH" "$HF_HOME" \
    && chown -R 10001:10001 /app/.cache

USER 10001:10001

# Baixa o modelo de embeddings no build, já como o usuário final (evita download no cold start).
RUN python -c "from fastembed import TextEmbedding; \
    TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

# Código por último, DEPOIS da camada de ~120 MB do modelo: editar `server.py` não pode invalidar
# o download (cada rebuild completo custa banda e minutos de build — ADR-010). O COPY grava como
# uid 0 mesmo com o USER acima ativo, então o processo segue sem poder reescrever o próprio código.
COPY mcp_server/ ./mcp_server/

EXPOSE 8000
CMD ["python", "mcp_server/server.py"]
