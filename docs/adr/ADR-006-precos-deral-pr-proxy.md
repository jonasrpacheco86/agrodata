# ADR-006: preço agrícola via IPEADATA/DERAL-PR como proxy regional

- **Status**: aceito
- **Data**: 2026-07-27
- **Fase**: 2
- **Função NIST CSF**: N/A (decisão de dados, não de segurança)

## Contexto e risco
A Fase 2 precisa de uma série de preços por cultura, atualizável **pelo Airflow** (sem passo manual).
O IPEADATA expõe séries por API aberta, mas **não tem série CEPEA/ESALQ nem série RS-específica** para
soja/milho/trigo — verificado no catálogo (3585 séries). O que existe e serve é o preço mensal
"recebido pelo agricultor" do **DERAL-PR** (Paraná). Risco: usar preço do PR como se fosse do RS induz
leitura errada de causalidade local.

## Decisão
Usar as séries DERAL-PR (`DERAL12_PRSO12` soja, `DERAL12_PRMI12` milho, `DERAL12_PRTRG12` trigo;
R$/saca de 60 kg, mensais, ativas) como **proxy regional**. PR e RS estão no mesmo cinturão de grãos
do Sul e o produtor é tomador de preço (Chicago + câmbio), então a série representa bem o **padrão**
de preço e sazonalidade — que é o que os indicadores usam. Declarar essa limitação no README e nos
gráficos. Arroz (`DERAL12_PRARIR12`) está inativo no IPEADATA → fica fora dos indicadores de preço.

## O que ficou de fora (e por quê)
**CEPEA/RS via XLS**: seria RS-específico e mais reconhecido, mas exige cadastro + download manual —
quebra o critério "atualiza pelo Airflow" e viraria ingestão semi-manual. Fica no `IDEIAS.md` para
avaliação futura. A honestidade sobre a fonte vale mais que a falsa precisão de fingir que é RS.

## Consequências
Os indicadores de preço (receita/ha, sazonalidade) usam um proxy — coerente para tendência e padrão,
não para o preço exato de um município do RS num dia. O README deixa isso explícito, o que neutraliza
a pergunta capciosa em entrevista e demonstra maturidade de leitura de dados. Se um dia o CEPEA/RS for
integrado, os indicadores trocam de fonte sem mudar de forma.
