# ADR-004: superfície de exposição do servidor MCP e por que não text-to-SQL livre

- **Status**: aceito
- **Data**: 2026-07-27
- **Fase**: 3
- **Função NIST CSF**: Protect

## Contexto e risco
O servidor MCP conecta o data warehouse a um assistente de IA controlado pelo usuário final. Duas
ameaças surgem: **injeção de prompt** (a IA ser induzida a rodar consultas maliciosas) e
**exfiltração** (a IA acessar mais dado do que deveria). Um servidor que aceitasse text-to-SQL livre
daria à IA — e a quem a manipule — a superfície inteira do banco.

## Decisão
A superfície é **fechada em ferramentas tipadas**, não SQL aberto:
- Cada tool executa uma **consulta parametrizada fixa** sobre uma **view** (params do psycopg,
  nunca interpolação de input do usuário).
- Conexão como **`mcp_ro`**: só-leitura, e enxerga só as views + o dicionário (nunca `raw` nem as
  tabelas-base) — herda o menor privilégio do ADR-002.
- **Limite de linhas** por retorno (`LIMIT 500`) e **log** de qual tool foi chamada com quais
  argumentos (em stderr, pois stdout é o transporte MCP).
- A IA **escolhe a tool**, não escreve SQL. A superfície de injeção fica reduzida ao que as tools
  permitem.

## O que ficou de fora (e por quê)
**Text-to-SQL livre**: mais "flexível", mas transforma cada prompt malicioso em SQL arbitrário —
inaceitável mesmo em só-leitura (exfiltração, DoS por query cara). Fica no `IDEIAS.md` como
não-objetivo. **Autenticação/rate-limit no servidor**: o transporte é stdio local lançado pelo
próprio usuário (não há rede exposta), então seria cerimônia — reavaliar se um dia virar HTTP.

## Consequências
Comprometer a IA ou injetar um prompt só alcança o que as 5 tools retornam de views de leitura —
nunca escrita, nunca dado bruto, nunca SQL arbitrário. O custo é rigidez: uma pergunta fora das 5
tools não é respondida sem adicionar uma tool nova. É a troca certa: confiabilidade e contenção
acima de flexibilidade. Defender isso (determinismo onde a precisão manda) é um diferencial de
maturidade — ver ADR-007 para o par com o RAG.
