# ADR-001: gestão de segredos e baseline de container

- **Status**: aceito
- **Data**: 2026-07-27
- **Fase**: 0
- **Função NIST CSF**: Protect

## Contexto e risco
O AgroData é público no GitHub desde o primeiro commit. Um segredo commitado (senha do
Postgres, chave da Claude API) vaza de forma efetivamente permanente — fica no histórico do
git mesmo após remoção e pode ser indexado por terceiros. Da mesma forma, containers rodando
como root ou com imagens `latest` dão superfície de ataque e builds não reprodutíveis, sem
que isso agregue qualquer valor ao projeto.

## Decisão
Segredos vivem **apenas em `.env` local**, listado no `.gitignore` desde o 1º commit; o
repositório versiona somente `.env.example` com placeholders. Um hook `PreToolUse`
(`.claude/hooks/guardrail.sh`) bloqueia edição de arquivos de segredo e a gravação de
credenciais reais em arquivos versionados. Todas as imagens Docker usam **tag fixada** (nunca
`latest`) e os containers rodam com **usuário não root**.

## O que ficou de fora (e por quê)
**Cofre de segredos gerenciado** (Vault, AWS Secrets Manager, Doppler): para 3 containers e
zero usuários seria teatro operacional — vive no `IDEIAS.md`. **Assinatura de imagem**
(cosign/Notary) e **scan de imagem em profundidade**: mesma razão, desproporcionais ao porte.
O baseline aqui é o mínimo defensável, e justificar a ausência do resto por ADR vale mais que
a presença sem justificativa.

## Consequências
Nenhum segredo trafega para o GitHub, e o guardrail torna esse controle automático em vez de
depender de disciplina manual. O custo é operacional pequeno: cada dev precisa copiar
`.env.example` para `.env` e preencher localmente antes de subir a stack, e toda bump de imagem
Docker é uma edição consciente de tag (não um `pull latest` silencioso) — exatamente a
reprodutibilidade que se quer demonstrar.
