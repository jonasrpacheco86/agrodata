# ADR-008: exposição pública do demo (só MCP, autenticado)

- **Status**: aceito
- **Data**: 2026-07-27
- **Fase**: 5
- **Função NIST CSF**: Protect

## Contexto e risco
O demo ao vivo do portfólio expõe partes do sistema à internet. Cada serviço público é superfície de
ataque. A tentação seria subir tudo (Postgres, Airflow, Metabase, MCP) numa VM com subdomínios — o que
contradiz o pilar de segurança do próprio projeto (ADR-001/002/004). Some-se a isso a restrição de
custo: sem nuvem paga, e as VMs "always free" de GCP/AWS/Azure (~1 GB) não comportam o stack.

## Decisão
Topologia mínima e sem cartão: **Postgres gerenciado na Neon** (com `pgvector`) + **servidor MCP no
Render** (HTTPS gerenciado). Exposto **apenas o MCP**, e assim:
- **Bearer token** obrigatório (`MCP_AUTH_TOKEN`); rota `/healthz` é a única sem auth.
- Conexão **`mcp_ro`** (só-leitura, só as views + dicionário) — herda o menor privilégio do ADR-002.
- Sem text-to-SQL, consulta parametrizada, `LIMIT` por retorno (ADR-004 intacto).
- **Postgres e Airflow não são expostos**: a ingestão roda local e escreve na Neon; nada de porta de
  banco ou orquestrador na internet. Metabase fica como prints no README.

## O que ficou de fora (e por quê)
**VM própria + Caddy + Terraform/Ansible** (o plano original na Oracle): a Oracle travou no cadastro e
as outras nuvens não têm VM grátis grande o suficiente — a topologia gerenciada (Neon+Render) entrega
o mesmo demo sem VM para manter. Vai para o `IDEIAS.md` como evolução. **OAuth 2.1 no MCP**: o padrão
completo é pesado para um demo; o bearer basta e é demonstrável via **MCP Inspector**. Ressalva honesta:
o conector remoto do Claude Desktop espera OAuth, então o Inspector (com header bearer) é o caminho do
demo; OAuth fica como evolução.

## Consequências
A superfície pública é uma só (o MCP), autenticada, só-leitura, sem SQL arbitrário — o pior caso é ler
dados públicos que já são abertos. Custo zero e nada de VM para patch. O preço é a ergonomia dos free
tiers (cold start do Render, pausa da Neon) e o bearer em vez de OAuth — trade-offs aceitáveis e
declarados, coerentes com "expor só o necessário".
