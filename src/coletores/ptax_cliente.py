"""
Cliente HTTP compartilhado para a API PTAX do Banco Central.

Concentra tudo que é comum a qualquer consulta na PTAX (montagem de URL,
formatação de data, retry, tratamento de status/JSON invalido com captura
de evidencia) para nao duplicar essa mecanica entre quem consulta um mes
inteiro (coletor_api.py, usado pelo run_api.py) e quem consulta uma janela
curta pra pegar a cotacao mais recente de 1 moeda (coletor_item.py, usado
pela API/backend).

Cada chamador decide o que fazer com os boletins crus devolvidos (mapear
pra Cotacao do CSV, ou pra um resultado simples do banco) - este modulo so
sabe buscar.
"""

import json

import requests

from src.infra import config
from src.infra.retry import executar_com_retry
from src.infra.evidencia import salvar_resposta_crua


def _formata_data_ptax(data):
    """A API PTAX espera datas no formato MM-DD-AAAA (mes-dia-ano)."""
    return data.strftime("%m-%d-%Y")


def _montar_url(moeda, data_inicial, data_final):
    """
    Monta a URL completa do recurso CotacaoMoedaPeriodo com os valores ja
    entre aspas simples, no formato que a PTAX aceita.
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


def buscar_boletins(moeda, data_inicial, data_final, logger):
    """
    Busca os boletins PTAX (todos os tipos) de uma moeda num periodo.

    Retorna a lista crua de boletins (dicionarios, como a API devolve em
    "value"). Lista vazia significa requisicao bem-sucedida sem boletins no
    periodo (moeda invalida, ou periodo sem pregao) - quem chama decide como
    interpretar isso.

    Levanta RuntimeError se a requisicao falhar apos as tentativas de retry
    (status != 200) ou se o JSON vier invalido - nos dois casos a resposta
    crua e salva como evidencia antes de propagar o erro.
    """
    url = _montar_url(moeda, data_inicial, data_final)

    def requisitar():
        return requests.get(url, timeout=config.API_TIMEOUT)

    resposta = executar_com_retry(
        requisitar, logger, f"Requisicao PTAX ({moeda})"
    )

    if resposta.status_code != 200:
        caminho = salvar_resposta_crua(resposta.text, f"api_status_{moeda}", logger)
        raise RuntimeError(
            f"API PTAX retornou status {resposta.status_code} para {moeda}. "
            f"Resposta crua em: {caminho}"
        )

    try:
        dados = resposta.json()
    except json.JSONDecodeError:
        caminho = salvar_resposta_crua(resposta.text, f"api_json_{moeda}", logger)
        raise RuntimeError(
            f"API PTAX retornou JSON invalido para {moeda}. "
            f"Resposta crua em: {caminho}"
        )

    return dados.get("value", [])
