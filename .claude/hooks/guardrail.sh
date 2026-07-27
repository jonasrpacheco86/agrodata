#!/usr/bin/env bash
# PreToolUse (Edit|Write) — Guardrail do AgroData.
#
# Duas proteções, ambas derivadas do Plano/CLAUDE.md:
#   1. ANTI-COMPLEXIDADE (regra 2): bloqueia dependências/imports fora da stack fixa.
#      Toda ideia fora de escopo vai para o IDEIAS.md, nunca para o código.
#   2. SEGREDOS (ADR-001): bloqueia edição de arquivos de segredo e o vazamento de
#      credenciais em arquivos versionados. Segredos ficam em .env LOCAL (gitignored)
#      e NUNCA no repositório/GitHub. Só .env.example é versionado.
#
# Bloqueia com exit 2 (a mensagem em stderr volta para o Claude reconsiderar).
# jq pode não existir no runner de hooks; o parsing do stdin é feito via node.

INPUT=$(cat)

# Extrai "file_path base64(conteúdo)" numa linha só (base64 evita quebra em newlines).
PARSED=$(printf '%s' "$INPUT" | node -e '
let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{
  try{
    const j=JSON.parse(s), t=j.tool_input||{};
    const fp=t.file_path||"";
    const c=(t.new_string!=null?t.new_string:(t.content!=null?t.content:""));
    process.stdout.write(fp+" "+Buffer.from(String(c)).toString("base64"));
  }catch(e){process.stdout.write(" ");}
});' 2>/dev/null)

FP="${PARSED%% *}"
B64="${PARSED#* }"
CONTENT=$(printf '%s' "$B64" | base64 -d 2>/dev/null || true)

# ── 1. Proteção de segredos: arquivos ──────────────────────────────────────────
# .env.example / .template / .sample são liberados (é o que se versiona).
case "$FP" in
  *.env.example|*.env.template|*.env.sample) : ;;
  *.env|*/.env|*.env.local|*.env.*.local|*.pem|*.key|*.pfx|*id_rsa*|*credentials*|*secrets.*)
    {
      echo "GUARDRAIL (segredos): edição de arquivo de segredo bloqueada → $FP"
      echo "Segredos ficam em .env LOCAL (no .gitignore) e NUNCA no repositório/GitHub."
      echo "Versione apenas .env.example com placeholders. Ver ADR-001."
    } >&2
    exit 2 ;;
esac

# ── 2. Proteção de segredos: vazamento de credencial em arquivo versionado ──────
if [ -n "$CONTENT" ]; then
  case "$FP" in
    *.env.example|*.env.template|*.env.sample) : ;;  # placeholders são esperados aqui
    *)
      if printf '%s' "$CONTENT" | grep -qE 'sk-ant-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----'; then
        {
          echo "GUARDRAIL (segredos): credencial real detectada no conteúdo → $FP"
          echo "Não grave chaves/tokens em arquivos versionados. Use variável de ambiente (.env local)."
        } >&2
        exit 2
      fi ;;
  esac
fi

# ── 3. Anti-complexidade: dependências fora da stack fixa ───────────────────────
# Aplica-se só a código/manifests (NÃO a .md/docs — um ADR "por que não usei Kafka"
# precisa citar Kafka livremente).
if [ -n "$CONTENT" ]; then
  HIT=""
  case "$FP" in
    *.py)
      if printf '%s' "$CONTENT" | grep -qiE '^[[:space:]]*(import|from)[[:space:]]+(pyspark|kafka|aiokafka|confluent_kafka|langchain|llama_index|kubernetes|boto3|botocore|pymongo)'; then
        HIT="import fora da stack"
      fi ;;
    *requirements*.txt|*pyproject.toml|*Pipfile|*setup.py|*setup.cfg|*environment.yml)
      if printf '%s' "$CONTENT" | grep -qiE '(^|["'\''[:space:]=<>~])(pyspark|apache-flink|kafka-python|confluent-kafka|aiokafka|langchain|llama-index|kubernetes|boto3|botocore|pymongo)([[:space:]"'\''<>=~]|$)'; then
        HIT="dependência fora da stack"
      fi ;;
    *docker-compose*.yml|*docker-compose*.yaml|*compose.yml|*compose.yaml)
      if printf '%s' "$CONTENT" | grep -qiE '^[[:space:]]*image:[[:space:]]*["'\'']?([^[:space:]"'\'']*/)?(spark|pyspark|kafka|zookeeper|flink|kubernetes|k8s)'; then
        HIT="serviço fora da stack"
      fi ;;
  esac
  if [ -n "$HIT" ]; then
    {
      echo "GUARDRAIL (anti-complexidade): $HIT em $FP."
      echo "A stack é fixa (Python/Airflow/Postgres+pgvector/Metabase/FastMCP/Compose)."
      echo "Kafka, Spark, Kubernetes, AWS/boto3, LangChain, Mongo etc. estão FORA de escopo."
      echo "→ Registre a ideia no IDEIAS.md (regra 2). Se precisar mesmo, o humano libera."
    } >&2
    exit 2
  fi
fi

exit 0
