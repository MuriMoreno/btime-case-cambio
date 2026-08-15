"""
Coletor de cotações via API PTAX oficial do Banco Central.

Consome o recurso CotacaoMoedaPeriodo da API PTAX, que retorna os boletins
de câmbio (compra e venda) por data, para um período e uma moeda. Converte
cada boletim de FECHAMENTO no modelo Cotacao padronizado.

Espelha o coletor de scraping: usa o mesmo período (mês anterior) e as
mesmas moedas, produz os mesmos objetos Cotacao, e por isso alimenta o
mesmo escritor de CSV - gerando um arquivo de estrutura idêntica.

Contingência: quando a API falha (timeout, status != 200, JSON quebrado),
o robô salva a resposta crua recebida como evidência - o equivalente, no
mundo de API, ao screenshot que o Selenium tira da tela no erro.

Nota técnica sobre a URL: a API PTAX (OData) exige que os valores dos
parâmetros venham entre aspas simples literais na própria URL (ex.:
@moeda='USD'). Por isso a URL é montada manualmente, e NÃO via params do
requests - o requests codificaria as aspas e o '@', o que a PTAX rejeita
com HTTP 400.
"""

import json

import requests

from src.infra import config
from src.infra.retry import executar_com_retry
from src.infra.evidencia import salvar_resposta_crua
from src.dominio.cotacao import Cotacao
from src.dominio.periodo import periodo_mes_anterior


def _formata_data_ptax(data):
    """
    A API PTAX espera datas no formato MM-DD-AAAA (mês-dia-ano). Converte
    um objeto date para essa string.
    """
    return data.strftime("%m-%d-%Y")


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


def _montar_url(moeda, data_inicial, data_final):
    """
    Monta a URL completa do recurso CotacaoMoedaPeriodo com os valores já
    entre aspas simples, no formato que a PTAX aceita.

    Parâmetros do recurso (nomes exatos exigidos pela API):
      moeda, dataInicial, dataFinalCotacao
    """
    di = _formata_data_ptax(data_inicial)
    df = _formata_data_ptax(data_final)
    return (
        f"{config.API_URL_BASE}"
        f"(moeda=@moeda,dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
        f"?@moeda='{moeda}'"
        f"&@dataInicial='{di}'"
        f"&@dataFinalCotacao='{df}'"
        f"&$format=json"
    )


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

        url = _montar_url(moeda, data_inicial, data_final)

        # A requisição roda sob retry: se a rede/servidor oscilar, tenta de novo.
        def requisitar():
            return requests.get(url, timeout=config.API_TIMEOUT)

        resposta = executar_com_retry(
            requisitar, logger, f"Requisicao PTAX ({moeda})"
        )

        # Só status 200 é aceitável; qualquer outro é erro de negócio.
        if resposta.status_code != 200:
            caminho = salvar_resposta_crua(
                resposta.text, f"api_status_{moeda}", logger
            )
            raise RuntimeError(
                f"API PTAX retornou status {resposta.status_code} para {moeda}. "
                f"Resposta crua em: {caminho}"
            )

        try:
            dados = resposta.json()
        except json.JSONDecodeError:
            caminho = salvar_resposta_crua(
                resposta.text, f"api_json_{moeda}", logger
            )
            raise RuntimeError(
                f"API PTAX retornou JSON invalido para {moeda}. "
                f"Resposta crua em: {caminho}"
            )

        # Os boletins ficam em dados["value"]. Cada data tem varios boletins
        # (abertura, intermediarios, fechamento); filtramos so o de
        # fechamento para casar com o site.
        boletins = dados.get("value", [])

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
