# ADR-005: escopo de segurança e modelo de ameaças (versão curta)

- **Status**: aceito
- **Data**: 2026-07-27
- **Fase**: 4
- **Função NIST CSF**: Identify

## Contexto e risco
Fechar a V1 exige declarar, de forma honesta, **o que o sistema protege, contra quê, e o que está
fora de escopo** — inclusive antecipando a exposição pública do demo (Fase 5). Sem esse recorte, a
segurança do projeto vira uma lista de controles sem fronteira, e a pergunta capciosa em entrevista
("e o dado sensível?") fica sem resposta.

## Decisão
Registrar o modelo de ameaças curto:

**O que protegemos e como**
- **Segredos** nunca no versionamento (`.env` local, `.gitignore`, gitleaks no CI) — ADR-001/003.
- **Menor privilégio no banco**: `airflow_rw`/`metabase_ro`/`mcp_ro`, nenhum superusuário no DW — ADR-002.
- **Superfície da IA**: MCP só-leitura, ferramentas tipadas, sem text-to-SQL, LIMIT e log — ADR-004.
- **Cadeia de suprimentos**: lint + auditoria de dependências no CI, imagem derivada corrigindo CVE — ADR-003.
- **Exposição pública** (demo, Fase 5): só Metabase (login) e MCP (bearer); Postgres/Airflow privados — ADR-008.

**Fora de escopo (declarado, não esquecido)**
- **Dado pessoal / LGPD**: todas as fontes são **dados públicos abertos** (IBGE, Open-Meteo, IPEADATA).
  Não há PII em escopo; o projeto **não** demonstra tratamento de dado sensível.
- **Alta disponibilidade, DR, WAF, SIEM, cofre gerenciado, mTLS**: teatro para este porte → `IDEIAS.md`.
- **Autenticação forte/OAuth no MCP**: o demo usa bearer; OAuth completo fica como evolução.

## O que ficou de fora (e por quê)
Um modelo de ameaças formal (STRIDE completo, matriz de risco) seria desproporcional a um portfólio
de um autor. A "versão curta" cobre o que importa: fronteira de dados (público, sem PII), fronteira de
acesso (menor privilégio) e fronteira de exposição (só o necessário, autenticado).

## Consequências
A fronteira fica explícita: comprometer qualquer serviço não alcança dado pessoal (não existe) nem
escrita/SQL arbitrário (menor privilégio + tools tipadas). Declarar o fora-de-escopo é honestidade
que neutraliza a pergunta capciosa e demonstra maturidade — vale mais que fingir cobrir tudo.
