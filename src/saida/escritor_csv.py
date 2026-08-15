"""
Camada de saída: escritor de CSV.

Recebe cotações já validadas e as grava num CSV bem estruturado. É a ÚNICA
peça que sabe escrever CSV, usada tanto pelo fluxo de scraping quanto pelo
de API - por isso os dois arquivos finais saem com a mesma estrutura.

Regra de negócio: o CSV é o entregável final consumido por outra pessoa,
então precisa ser previsível - cabeçalho claro, ordem de colunas fixa, e
codificação que abre certo no Excel brasileiro (UTF-8 com BOM).
"""

import csv


# Ordem e nomes das colunas do CSV. Definir aqui garante cabeçalho estável
# e legível, independente da fonte.
COLUNAS = {
    "moeda": "Moeda",
    "data_cotacao": "Data da Cotacao",
    "tipo": "Tipo",
    "valor_compra": "Compra",
    "valor_venda": "Venda",
    "data_coleta": "Data da Coleta",
    "fonte": "Fonte",
}


def salvar_csv(cotacoes, caminho_arquivo, logger):
    """
    Grava a lista de cotações no caminho informado.

    - utf-8-sig (UTF-8 com BOM): acentos abrem corretos no Excel.
    - delimitador ';': padrão do Excel brasileiro.
    - cabeçalho amigável + uma linha por cotação, sempre na mesma ordem.
    """
    logger.processo(f"Iniciando escrita do CSV em: {caminho_arquivo}")

    with open(caminho_arquivo, mode="w", newline="", encoding="utf-8-sig") as arquivo:
        writer = csv.writer(arquivo, delimiter=";")
        writer.writerow(COLUNAS.values())  # cabeçalho
        for cotacao in cotacoes:
            dados = cotacao.como_dicionario()
            writer.writerow([dados[chave] for chave in COLUNAS.keys()])

    logger.processo(
        f"CSV gerado com sucesso: {len(cotacoes)} registro(s) em {caminho_arquivo}"
    )
