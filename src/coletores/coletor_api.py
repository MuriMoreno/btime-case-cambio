"""
Coletor de cotações via API PTAX oficial do Banco Central.

Consome o recurso CotacaoMoedaPeriodo da API PTAX (via ptax_cliente), que
retorna os boletins de câmbio (compra e venda) por data, para um período e
uma moeda. Converte cada boletim de FECHAMENTO no modelo Cotacao
padronizado.

Espelha o coletor de scraping: usa o mesmo período (mês anterior) e as
mesmas moedas, produz os mesmos objetos Cotacao, e por isso alimenta o
mesmo escritor de CSV - gerando um arquivo de estrutura idêntica.

A montagem de URL, o retry e o tratamento de erro de requisição/JSON ficam
em ptax_cliente.py, compartilhados com coletor_item.py (usado pela API do
backend) - aqui só sobra a regra própria deste fluxo: período do mês
anterior, todas as moedas configuradas, e o mapeamento pro Cotacao do CSV.
"""

from src.infra import config
from src.coletores.ptax_cliente import buscar_boletins
from src.dominio.cotacao import Cotacao
from src.dominio.periodo import periodo_mes_anterior


def _formata_data_br(texto_iso):
    """
    A API devolve a data como 'AAAA-MM-DD HH:MM:SS...'. Para o CSV, queremos
    DD/MM/AAAA (igual ao site). Se o formato vier diferente, devolve o
    texto original para não perder o dado.
    """
    try:
        parte_data = texto_iso.split(" ")[0]          # 'AAAA-MM-DD'
        ano, mes, dia = parte_data.split("-")
        return f"{dia}/{mes}/{ano}"
    except (ValueError, AttributeError, IndexError):
        return texto_iso


def coletar_via_api(logger):
    """
    Coleta as cotações PTAX de fechamento de todas as moedas configuradas,
    no período do mês anterior, via API oficial do BCB.

    Retorna uma lista de objetos Cotacao. Erros de negócio esperados
    (status != 200, JSON inválido) são levantados como RuntimeError, para
    o ponto de entrada registrar no LogErro.
    """
    data_inicial, data_final = periodo_mes_anterior()
    logger.processo(
        f"Periodo de consulta (mes anterior): "
        f"{data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}"
    )

    momento_coleta = Cotacao.carimbo_agora()
    cotacoes = []

    for moeda in config.MOEDAS:
        logger.processo(f"Consultando API PTAX para a moeda: {moeda}")

        # Cada data tem varios boletins (abertura, intermediarios,
        # fechamento); filtramos so o de fechamento para casar com o site.
        boletins = buscar_boletins(moeda, data_inicial, data_final, logger)

        if not boletins:
            logger.erro(f"API PTAX nao retornou boletins para {moeda} no periodo.")
            continue

        qtd_moeda = 0
        for boletim in boletins:
            if boletim.get("tipoBoletim") != config.API_TIPO_BOLETIM_FECHAMENTO:
                continue

            cotacao = Cotacao(
                moeda=moeda,
                data_cotacao=_formata_data_br(boletim.get("dataHoraCotacao", "")),
                tipo="A",  # PTAX de fechamento, igual ao rótulo do site
                valor_compra=str(boletim.get("cotacaoCompra", "")),
                valor_venda=str(boletim.get("cotacaoVenda", "")),
                data_coleta=momento_coleta,
                fonte="api",
            )
            cotacoes.append(cotacao)
            qtd_moeda += 1

        logger.processo(f"{moeda}: {qtd_moeda} cotacao(oes) de fechamento coletada(s).")

    return cotacoes
