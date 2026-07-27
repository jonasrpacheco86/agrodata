# ADR-002: separação de papéis e menor privilégio no banco

- **Status**: aceito
- **Data**: 2026-07-27
- **Fase**: 1
- **Função NIST CSF**: Protect

## Contexto e risco
Com o primeiro fluxo de dados (Fase 1), três serviços passam a tocar o data warehouse: a DAG do
Airflow (escreve), o Metabase (lê para o dashboard) e, na Fase 3, o servidor MCP (lê para a IA).
Se todos conectarem como o superusuário do cluster, qualquer um deles — ou um atacante que
comprometa qualquer um — pode ler e destruir tudo, inclusive o dado bruto. É o maior risco
evitável do projeto e o controle preventivo de maior valor.

## Decisão
Três papéis de login distintos no Postgres, **nenhum superusuário**, criados no init a partir de
senhas do `.env` (`db/init/02-security.sh`):
- `airflow_rw` — dono e escritor de `raw` + `mart` (a DAG usa a Connection `agrodata_dw`).
- `metabase_ro` — `USAGE`+`SELECT` **só** em `mart` (sem acesso a `raw`), via default privileges.
- `mcp_ro` — `SELECT` **só** nas views de `mart` (nunca as tabelas-base), concedido view a view.

Os objetos de `mart` são criados como `airflow_rw` para que as default privileges concedam leitura
ao `metabase_ro` automaticamente conforme novas tabelas/views surgirem.

## O que ficou de fora (e por quê)
**Endurecer também as conexões de metadados do Airflow e de app do Metabase** (bancos `airflow` e
`metabase`), hoje ainda no superusuário do cluster: esses bancos não guardam dado do projeto, então
o ganho é marginal ante o custo de mais papéis e owners. Fica como hardening opcional. **Row-Level
Security, cofre de segredos gerenciado e rotação automática de senha**: desproporcionais a este
porte — vivem no `IDEIAS.md`. O controle que importa é o acesso ao DW `agrodata`, e esse tem menor
privilégio real.

## Consequências
Nenhum serviço lê ou escreve além do que precisa: comprometer o Metabase não expõe o dado bruto nem
permite escrita; comprometer o servidor MCP (Fase 3) só alcança as views publicadas. O custo é
operacional: quatro senhas no `.env` em vez de uma, e o data source do Metabase precisa ser
configurado com `metabase_ro` (não com o superusuário). Como os papéis nascem no init do container,
aplicá-los a um volume já existente exige recriar o volume (`docker compose down -v`).
