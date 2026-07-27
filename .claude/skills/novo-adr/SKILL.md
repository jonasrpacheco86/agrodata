---
name: novo-adr
description: Cria um ADR (Architecture Decision Record) curto e numerado em docs/adr/ para o projeto AgroData. Use para registrar uma decisão de arquitetura ou de segurança, incluindo os ADRs "por que NÃO usei X". Cada ADR mapeia risco → decisão → o que ficou de fora, e (quando de segurança) a função do NIST CSF.
disable-model-invocation: true
---

# novo-adr — registrar uma decisão de arquitetura

No AgroData o **ADR é o entregável de verdade** (não a ferramenta). Esta skill cria um ADR
curto, numerado e consistente em `docs/adr/`.

## Passos

1. **Garanta a pasta**: crie `docs/adr/` se não existir.

2. **Descubra o próximo número**: liste `docs/adr/ADR-*.md`, pegue o maior número existente
   e some 1. Formate com 3 dígitos (`001`, `002`, ...). Se a pasta estiver vazia, comece em `001`.
   Nota: o Plano já reserva `ADR-001` a `ADR-005` para o pilar de segurança
   (segredos, menor privilégio no banco, CI/supply chain, superfície do MCP, escopo de ameaças).
   Respeite essa numeração; ADRs novos de arquitetura entram a partir de `ADR-006`.

3. **Colete o conteúdo**. Se o usuário passou um título como argumento, use-o. Preencha os
   campos a partir do contexto da conversa e **confirme com o usuário antes de gravar**.
   Perguntas-chave: qual risco/problema motiva? qual a decisão? o que foi rejeitado e por quê?
   é uma decisão de segurança (então qual função do NIST CSF)?

4. **Nomeie o arquivo**: `docs/adr/ADR-NNN-<slug-do-titulo>.md` (slug em minúsculas, com hífens,
   sem acentos). Ex.: `ADR-006-particionamento-do-fato-producao.md`.

5. **Grave** usando o template abaixo. Use a data de hoje (formato `AAAA-MM-DD`).

6. **Feche o laço**: se o ADR for do tipo "por que NÃO usei X", confirme que **X está listado
   no `IDEIAS.md`** (regra 2). Se não estiver, ofereça adicionar.

## Template

```markdown
# ADR-NNN: <título da decisão>

- **Status**: proposto | aceito | substituído por ADR-XXX
- **Data**: AAAA-MM-DD
- **Fase**: <0 a 5>
- **Função NIST CSF**: Identify | Protect | Detect | Respond | Recover — ou "N/A" (não é segurança)

## Contexto e risco
<Qual problema ou risco motiva a decisão. Uma a três frases. Se for segurança, nomeie a ameaça.>

## Decisão
<O que foi decidido, no presente: "Usamos X" / "Não usamos Y". Direto ao ponto.>

## O que ficou de fora (e por quê)
<Alternativas rejeitadas. Se este ADR é um "por que não usei Y", este é o coração do documento:
justifique a ausência — para este porte, Y seria complexidade/teatro. Y vive no IDEIAS.md.>

## Consequências
<Trade-offs assumidos: o que fica mais fácil, o que fica mais difícil, o que passa a ser
responsabilidade de quem opera. Seja honesto sobre as limitações.>
```

## Regras de qualidade

- **Curto**: um ADR cabe numa tela. Se passar disso, provavelmente são dois ADRs.
- **Honesto**: registrar limitações e o que ficou de fora vale mais que vender a decisão.
- **Rastreável**: ao substituir um ADR antigo, marque o antigo como `substituído por ADR-XXX`
  em vez de apagá-lo — o histórico conta a história do projeto.
