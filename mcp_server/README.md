# Servidor MCP do AgroData

Expõe o `mart` como **ferramentas tipadas** para assistentes de IA (ex.: Claude Desktop). O produtor
que já usa uma IA conecta este servidor e pergunta em linguagem natural — "quanto choveu na minha
cidade na safra passada e como ficou o rendimento?" — e a IA chama as tools e responde com os dados
da plataforma. É a tese do "cérebro próprio" em código.

## Tools
| Tool | O que responde | View |
|---|---|---|
| `producao(municipio, cultura, ano?)` | área, produção e rendimento | `vw_producao` |
| `chuva_no_ciclo(municipio, safra)` | chuva acumulada no ciclo (5 munis) | `vw_clima_safra` |
| `preco(produto, ano_inicio, ano_fim)` | preço mensal R$/saca | `vw_preco_mensal` |
| `receita_por_hectare(municipio, cultura, ano)` | receita estimada por ha | `vw_receita_hectare` |
| `busca_metadados(pergunta)` | qual tool responde (RAG nos metadados) | `dicionario_dados` |

Conecta como `mcp_ro` (só-leitura, só views + dicionário). Sem text-to-SQL (ADR-004).

## Rodar (venv local)

Pré-requisito: a stack no ar (`docker compose up -d`) com o `mart` populado e o
`db/init/05-fase3.sql` aplicado.

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r mcp_server/requirements.txt

# 1) indexar o dicionário (uma vez; baixa o modelo de embeddings ~0.22 GB)
MCP_DB_HOST=localhost AIRFLOW_DB_PASSWORD=<sua_senha_airflow_rw> \
  python mcp_server/index_metadados.py

# 2) rodar o servidor (stdio) — normalmente o Claude Desktop faz isso
MCP_DB_PASSWORD=<sua_senha_mcp_ro> python mcp_server/server.py
```

## Conectar no Claude Desktop

Em `claude_desktop_config.json` (não versione senha):

```json
{
  "mcpServers": {
    "agrodata": {
      "command": "/caminho/para/.venv/bin/python",
      "args": ["/caminho/para/AgroData/mcp_server/server.py"],
      "env": {
        "MCP_DB_HOST": "localhost",
        "MCP_DB_PORT": "5432",
        "MCP_DB_NAME": "agrodata",
        "MCP_DB_USER": "mcp_ro",
        "MCP_DB_PASSWORD": "<sua_senha_mcp_ro>"
      }
    }
  }
}
```

Reinicie o Claude Desktop e pergunte, por exemplo: "Qual foi o rendimento da soja em Passo Fundo em
2022?" ou "Compare a chuva do ciclo em Cruz Alta nas safras 2021 e 2022 com o rendimento."
