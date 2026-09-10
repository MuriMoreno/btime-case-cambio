"""
Coletor da cotação mais recente de UMA moeda, usado pelo backend (API).

Diferente de coletor_api.py (que busca o mês inteiro anterior, de todas as
moedas configuradas, para o CSV), este coletor busca só "qual é a cotação
mais recente disponível agora" para uma moeda escolhida pelo usuário via
API - qualquer moeda aceita pela PTAX, não só USD/EUR/GBP.

Não reaproveita o modelo Cotacao (dominio/cotacao.py): aquele dataclass
normaliza valores para string com vírgula e 4 casas, uma regra pensada
para o CSV abrir certo no Excel brasileiro. Aqui o consumidor é o banco/API
(JSON, gráfico no frontend), então os valores ficam como float puro.
"""

from datetime import date, timedelta
from typing import NamedTuple

from src.infra import config
from src.coletores.ptax_cliente import buscar_boletins


class CotacaoAtual(NamedTuple):
    data_cotacao: date
    valor_compra: float
    valor_venda: float


class CotacaoIndisponivelError(Exception):
    """
    A PTAX respondeu normalmente, mas não trouxe nenhum boletim de
    fechamento para a moeda no período consultado - moeda inexistente na
    PTAX, ou (mais raro, com a janela de dias configurada) período sem
    nenhum pregão.
    """
    pass


def buscar_cotacao_atual(moeda, logger):
    """
    Busca o boletim de FECHAMENTO mais recente de 'moeda' dentro da janela
    de config.JANELA_DIAS_COTACAO_ATUAL dias (cobre fins de semana/feriados
    sem boletim). Levanta CotacaoIndisponivelError se não achar nada, ou
    RuntimeError (propagado de ptax_cliente) se a PTAX falhar na requisição.
    """
    hoje = date.today()
    data_inicial = hoje - timedelta(days=config.JANELA_DIAS_COTACAO_ATUAL)

    boletins = buscar_boletins(moeda, data_inicial, hoje, logger)

    fechamentos = [
        b for b in boletins
        if b.get("tipoBoletim") == config.API_TIPO_BOLETIM_FECHAMENTO
    ]

    if not fechamentos:
        raise CotacaoIndisponivelError(
            f"Nenhuma cotacao de fechamento encontrada para '{moeda}' nos "
            f"ultimos {config.JANELA_DIAS_COTACAO_ATUAL} dias."
        )

    mais_recente = max(fechamentos, key=lambda b: b.get("dataHoraCotacao", ""))

    data_cotacao = _extrair_data(mais_recente.get("dataHoraCotacao", ""))

    return CotacaoAtual(
        data_cotacao=data_cotacao,
        valor_compra=float(mais_recente.get("cotacaoCompra", 0)),
        valor_venda=float(mais_recente.get("cotacaoVenda", 0)),
    )


def _extrair_data(texto_iso):
    """A API devolve 'AAAA-MM-DD HH:MM:SS...'; extrai só a data."""
    parte_data = texto_iso.split(" ")[0]
    return date.fromisoformat(parte_data)
