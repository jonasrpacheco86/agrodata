# Post de LinkedIn — rascunho (Fase 4)

> Rascunho para publicar quando a V1 (`v1.0.0`) estiver no ar. Ajuste o tom antes de postar.

---

Terminei a V1 do **AgroData**: uma plataforma open source que leva dados públicos do agronegócio
brasileiro do dado bruto à decisão — e deixa qualquer assistente de IA consultar tudo em linguagem
natural.

A tese que ela materializa: **cada empresa precisa do próprio cérebro — IA aterrada nos seus dados e
processos.** Aqui isso vira código:

🔹 **Ingestão** (Apache Airflow) de 3 fontes abertas: produção (IBGE/SIDRA), clima (Open-Meteo) e
preços (IPEADATA).
🔹 **Modelagem** num DW dimensional em PostgreSQL (`raw` → `mart`, com pgvector).
🔹 **BI** (Metabase) com 3 indicadores que contam a história *passado → impacto → decisão* — a seca de
2021/22 aparece nos dados derrubando o rendimento da soja.
🔹 **IA** por um **servidor MCP**: 5 ferramentas tipadas que a IA chama para responder com o dado
correto — nada de "SQL livre" alucinado.

O que eu mais defendo desse projeto não é o stack, é o **método**:
- **Segurança preventiva de verdade**, não teatro: menor privilégio no banco, e um CI que *pegou um
  CVE real numa dependência* — corrigido de forma reprodutível. Cada decisão virou um ADR curto,
  referenciado ao NIST CSF.
- **RAG onde serve, determinismo onde a precisão manda**: busca semântica só no dicionário de dados;
  o número exato vem sempre de ferramenta tipada.
- **Anti-complexidade como disciplina**: sem Kafka, sem Kubernetes, sem hype. Toda ideia fora de
  escopo foi para um `IDEIAS.md`, não para o código.

Tudo aberto no GitHub, documentado e reproduzível com `docker compose up`.

👉 github.com/jonasrpacheco86/agrodata

#EngenhariaDeDados #IA #MCP #Agro #OpenSource #PostgreSQL

---

## Bullet de CV (quando pronto)
"Construiu e publicou plataforma open source de dados do agronegócio: ingestão de fontes públicas
(IBGE, clima, preços) com Apache Airflow, modelagem em PostgreSQL (mart + pgvector), dashboard de
indicadores (Metabase) e servidor MCP que expõe os dados como ferramentas tipadas para assistentes de
IA — com segurança preventiva (menor privilégio, CI com varredura de segredo/dependência) e decisões
registradas em ADRs referenciados ao NIST CSF."
