"""Dicionário de dados do AgroData — descrições dos objetos do `mart`.

É a base do RAG (tool `busca_metadados`): as descrições são embedadas e indexadas em
`mart.dicionario_dados` por `index_metadados.py`. Escritas para casar semanticamente com
perguntas em linguagem natural e apontar a tool/coluna certa.
"""

# (objeto, descricao). `objeto` referencia a tool ou a view/coluna do mart.
DICIONARIO: list[tuple[str, str]] = [
    (
        "producao / vw_producao",
        "Produção agrícola municipal: área colhida em hectares, quantidade produzida em toneladas "
        "e rendimento médio em kg por hectare, por município, ano e cultura (soja, milho, trigo, "
        "arroz) no Rio Grande do Sul. Fonte IBGE/SIDRA (PAM). Use a tool producao.",
    ),
    (
        "chuva_no_ciclo / vw_clima_safra",
        "Chuva acumulada no ciclo da safra (outubro a março) em milímetros e evapotranspiração por "
        "município e safra, para 5 municípios do noroeste do RS (Cruz Alta, Ijuí, Palmeira das "
        "Missões, Passo Fundo, Santa Rosa). Fonte Open-Meteo. Use a tool chuva_no_ciclo.",
    ),
    (
        "preco / vw_preco_mensal",
        "Preço mensal recebido pelo agricultor em reais por saca (60 kg) para soja, milho e trigo. "
        "Série temporal por cultura, ano e mês. Fonte IPEADATA/DERAL-PR (proxy regional). Use a tool preco.",
    ),
    (
        "receita_por_hectare / vw_receita_hectare",
        "Receita estimada por hectare em reais, calculada como rendimento (kg/ha) dividido pela saca "
        "vezes o preço na colheita, por município, ano e cultura. Mede o impacto no bolso do produtor. "
        "Use a tool receita_por_hectare.",
    ),
    (
        "vw_chuva_rendimento",
        "Relação entre a chuva no ciclo da safra e o rendimento da soja por município e ano de "
        "colheita. Explica quebras de safra por seca, como a estiagem de 2021/22 no RS.",
    ),
    (
        "vw_preco_sazonal",
        "Padrão sazonal do preço: preço médio por mês do ano, por cultura. Apoia a decisão de vender "
        "na colheita ou armazenar para a entressafra.",
    ),
    (
        "conceito: safra e ciclo",
        "A safra é rotulada pelo ano de colheita. O ciclo da soja no RS vai de outubro do ano anterior "
        "a março do ano da colheita. Colheita aproximada: soja em abril, milho em maio, trigo em outubro.",
    ),
    (
        "conceito: cobertura e limites",
        "Produção e preços cobrem soja, milho, trigo e arroz (arroz sem preço). Clima cobre só 5 "
        "municípios do noroeste do RS. Preço é do Paraná como proxy regional, não do RS.",
    ),
]
