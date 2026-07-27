# ADR-003: cadeia de suprimentos e verificação automatizada no CI

- **Status**: aceito
- **Data**: 2026-07-27
- **Fase**: 2
- **Função NIST CSF**: Protect

## Contexto e risco
Com código Python (DAGs) e dependências de terceiros no repositório, três riscos ficam abertos se
nada os verificar a cada mudança: um segredo commitado por engano (vaza de forma permanente no
histórico público), um erro/anti-padrão de código que só aparece em produção, e uma dependência com
vulnerabilidade conhecida (CVE) entrando sem ninguém notar. São riscos de cadeia de suprimentos e de
higiene, todos baratos de automatizar.

## Decisão
CI no GitHub Actions (`.github/workflows/ci.yml`), disparado em `push` e `pull_request`, com três
verificações independentes:
1. **Segredos** — `gitleaks` varrendo o histórico completo (`fetch-depth: 0`).
2. **Análise estática** — `ruff check dags/` (config em `ruff.toml`; não importa Airflow, só analisa).
3. **Dependências** — `pip-audit -r requirements.txt` (o `requirements.txt` é o manifesto pinado).

O entregável não é a ferramenta e sim a barreira: nenhuma mudança entra sem passar pelos três.

## O que ficou de fora (e por quê)
**SAST pesado** (CodeQL/Semgrep), **assinatura de commits**, **SBOM assinado** e **gate de cobertura
de testes**: desproporcionais a um projeto deste porte com um autor — vivem no `IDEIAS.md`. Três
checks rápidos cobrem os riscos reais (segredo, código, dependência) sem transformar o CI em cerimônia.

## Consequências
Um segredo plantado num commit de teste **faz o pipeline falhar** (é a prova do controle), assim como
uma dependência com CVE ou um erro de lint. O custo é pequeno: ~1–2 min por push e a disciplina de
manter o `requirements.txt` pinado. Como o gitleaks lê o histórico inteiro, um segredo já commitado no
passado seria detectado — reforçando a regra do ADR-001 de que segredo nunca entra no versionamento.

**O controle funcionou na 1ª execução:** o pip-audit apontou `requests 2.32.3` (da imagem base do
Airflow) com PYSEC-2026-1872/2275. A correção foi reprodutível, não cosmética — uma imagem derivada
(`docker/airflow/Dockerfile`) instala `requests 2.33.0`, de modo que o runtime e o manifesto auditado
ficam iguais (nada de "audit verde com runtime vulnerável").
