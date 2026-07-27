# ADR-007: RAG onde serve, determinismo onde a precisão manda

- **Status**: aceito
- **Data**: 2026-07-27
- **Fase**: 3
- **Função NIST CSF**: N/A (decisão de arquitetura de IA)

## Contexto e risco
O projeto tem `pgvector` na stack e o hype empurra para "RAG em cima de tudo". Mas aplicar busca
vetorial sobre o dado tabular (produção, preços) é um erro: RAG recupera trechos por similaridade,
não garante o número exato — e o valor deste projeto é responder com o dado **correto**. O risco é
usar RAG no lugar errado e entregar respostas plausíveis, porém imprecisas.

## Decisão
Dividir o problema:
- **Dado tabular** → sempre por **ferramenta tipada** com SQL parametrizado (ADR-004). Determinístico,
  auditável, exato.
- **Metadados** (dicionário de dados: descrições das views/colunas) → **RAG com pgvector**. A tool
  `busca_metadados` embeda a pergunta (modelo multilíngue local, sem API externa) e faz busca
  vetorial para dizer **qual tool/coluna** responde. Retorna descrições e relevância, nunca dado bruto.

Ou seja: o RAG ajuda a **rotear/explicar**; a resposta factual vem sempre da tool tipada.

## O que ficou de fora (e por quê)
**RAG sobre as tabelas de fato** (produção/preços): perde precisão para ganhar nada — o dado já é
consultável exatamente por tool. **Embeddings via API paga** (OpenAI/Voyage): desnecessário e cria
dependência externa; o modelo local `MiniLM` multilíngue basta para um dicionário pequeno. **RAG
documental** (boletins Embrapa/CONAB) fica no `IDEIAS.md`.

## Consequências
`pgvector` deixa de ser decorativo: existe e serve num ponto legítimo. As respostas factuais
permanecem exatas (tools), e a IA ganha um mapa semântico para escolher a ferramenta certa. Defender
"RAG onde serve, determinismo onde a precisão manda" — em vez de RAG em tudo — é justamente o sinal
de maturidade que diferencia o projeto do hype.
