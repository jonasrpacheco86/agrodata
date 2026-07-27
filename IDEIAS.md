# IDEIAS.md — estacionamento de ideias do AgroData

> Regra: toda ideia nova entra AQUI, não no código. Se sobreviver duas semanas na lista e a V1 já estiver publicada, ela pode ser promovida a Issue. Nada daqui entra na V1.

## Fontes de dados
- Embrapa (dados de pesquisa, zoneamento agrícola)
- Mais estados além do RS
- NASA POWER / satélite (NDVI, índice de vegetação)

## Dados e análise
- Previsão/ML (safra, preço) — só depois do descritivo estar sólido
- Streaming/tempo quase real — sem caso de uso na V1
- Mapa geoespacial (PostGIS) nos dashboards

## IA
- Multi-agente / orquestração
- RAG documental (boletins Embrapa/CONAB como corpus)
- Scoring real de recomendação (lição do LocaAgro: nunca exibir percentual não calculado)

## Plataforma e infra
- Kubernetes (Compose + IaC bastam para este porte — escrever ADR "por que não")
- Jenkins (GitHub Actions cobre — ADR "por que não")
- Coroot/observabilidade avançada (3 containers, zero usuários — ADR "por que não")
- Interface web própria para o agente (o MCP + Claude Desktop é a interface da V1)
- App mobile

## Segurança
> Guarda-corpos do pilar de segurança: para este porte seriam teatro. Cada ausência é justificada por ADR (ver ADR-001 a ADR-005). Nada entra na V1.
- Cofre de segredos gerenciado (Vault, Secrets Manager, Doppler) — .env local basta (ADR-001)
- Assinatura de imagem (cosign/Notary) e scan de imagem em profundidade — baseline mínimo basta (ADR-001)
- WAF (firewall de aplicação) — sem exposição pública de superfície web na V1
- SIEM / correlação de logs — 3 containers, zero usuários; log de chamada da ferramenta MCP basta (ADR-004)
- mTLS entre serviços — rede interna do Compose; desproporcional ao porte

## Produto
- Alertas por WhatsApp/e-mail (chuva anômala, preço fora do padrão)
- Multi-tenant / versão para cooperativas
