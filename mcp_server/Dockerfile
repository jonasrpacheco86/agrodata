# Imagem do servidor MCP do AgroData para deploy público (HTTP + bearer).
# Contexto de build: raiz do repositório.
FROM python:3.12-slim
WORKDIR /app

COPY mcp_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Baixa o modelo de embeddings no build (evita download no cold start do host).
RUN python -c "from fastembed import TextEmbedding; \
    TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

COPY mcp_server/ ./mcp_server/

ENV MCP_TRANSPORT=http \
    PORT=8000 \
    PYTHONPATH=/app/mcp_server
EXPOSE 8000
CMD ["python", "mcp_server/server.py"]
