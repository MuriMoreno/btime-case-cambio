"""
Dados agregados para a tela de Dashboard: ranking de maiores altas/baixas e
volatilidade num período, entre um recorte de moedas relevantes
(config.MOEDAS_DASHBOARD_RANKING); variação média por dia da semana; um
resumo rápido (itens monitorados, quantos com alerta ativo hoje, conversões
já feitas); e o par de moedas mais convertido pelo usuário. Tudo derivado da
mesma PTAX e do mesmo banco que o resto do sistema já usa - nenhum dado
novo é coletado aqui.

/ranking-variacao e /mercado consultam o mesmo recorte de moedas (e, no
caso comum, o mesmo período) - por isso os fechamentos de cada moeda
passam por um cache curto em memória (_CACHE_FECHAMENTOS): a segunda tela
a carregar não bate de novo na PTAX pra moeda que a primeira já buscou.
Além disso, as chamadas de uma mesma leva são feitas em paralelo (a espera
de rede é o que demora, não o processamento), então o tempo de carregamento
fica perto do da chamada mais lenta, não da soma de todas.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.infra import config
from src.api import schemas
from src.api.dependencias import get_db, logger_api, obter_usuario_atual
from src.coletores.ptax_cliente import buscar_boletins
from src.persistencia import repositorio

router = APIRouter(
    prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(obter_usuario_atual)]
)

# Nomes em português, na ordem de segunda a domingo (date.weekday(): 0=segunda).
_DIAS_SEMANA_PT = [
    "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
    "Sexta-feira", "Sábado", "Domingo",
]

# Cache em memória dos fechamentos por (moeda, data_inicio, data_fim). TTL
# curto só pra evitar repetir a mesma consulta em segundos - a PTAX publica
# no máximo 1 boletim de fechamento por dia, então isso nunca serve dado
# desatualizado dentro da janela de validade.
_CACHE_FECHAMENTOS = {}
_CACHE_TTL_SEGUNDOS = 15 * 60


def _fechamentos_ordenados(moeda, data_inicio, data_fim):
    boletins = buscar_boletins(moeda, data_inicio, data_fim, logger_api)
    fechamentos = [
        b for b in boletins if b.get("tipoBoletim") == config.API_TIPO_BOLETIM_FECHAMENTO
    ]
    fechamentos.sort(key=lambda b: b.get("dataHoraCotacao", ""))
    return fechamentos


def _fechamentos_com_cache(moeda, data_inicio, data_fim):
    chave = (moeda, data_inicio, data_fim)
    agora = time.monotonic()

    em_cache = _CACHE_FECHAMENTOS.get(chave)
    if em_cache is not None and (agora - em_cache[0]) < _CACHE_TTL_SEGUNDOS:
        return em_cache[1]

    fechamentos = _fechamentos_ordenados(moeda, data_inicio, data_fim)
    _CACHE_FECHAMENTOS[chave] = (agora, fechamentos)
    return fechamentos


def _fechamentos_do_recorte(data_inicio, data_fim):
    """
    Fechamentos de todas as moedas de config.MOEDAS_DASHBOARD_RANKING no
    período, buscados em paralelo (com cache por moeda). Devolve
    {moeda: fechamentos}, omitindo silenciosamente quem falhar na PTAX -
    quem chama decide o que fazer com uma moeda ausente.
    """

    def buscar(moeda):
        try:
            return moeda, _fechamentos_com_cache(moeda, data_inicio, data_fim)
        except RuntimeError as erro:
            logger_api.erro(f"[Dashboard] Falha ao consultar {moeda}: {erro}")
            return moeda, None

    resultado = {}
    with ThreadPoolExecutor(max_workers=len(config.MOEDAS_DASHBOARD_RANKING)) as executor:
        for moeda, fechamentos in executor.map(buscar, config.MOEDAS_DASHBOARD_RANKING):
            if fechamentos is not None:
                resultado[moeda] = fechamentos

    return resultado


def _variacoes_diarias(fechamentos):
    """
    Variação % (compra) de cada boletim em relação ao anterior, já pareada
    com a data do boletim mais recente do par - a base tanto da maior
    variação diária (volatilidade) quanto da média por dia da semana.
    """
    variacoes = []
    for anterior, atual in zip(fechamentos, fechamentos[1:]):
        compra_anterior = float(anterior.get("cotacaoCompra", 0))
        compra_atual = float(atual.get("cotacaoCompra", 0))
        if not compra_anterior:
            continue

        data_str = atual.get("dataHoraCotacao", "").split(" ")[0]
        variacoes.append(
            (date.fromisoformat(data_str), ((compra_atual - compra_anterior) / compra_anterior) * 100)
        )
    return variacoes


@router.get("/ranking-variacao", response_model=list[schemas.VariacaoMoedaOut])
def ranking_variacao(dias: int = Query(90, ge=1, le=365)):
    """
    Variação % (cotação de compra) de cada moeda do recorte entre o início
    e o fim do período - ordenado da maior alta pra maior baixa. Uma moeda
    que falhar na PTAX (ou não tiver ao menos 2 boletins no período) é
    simplesmente omitida do ranking, em vez de derrubar a resposta inteira.
    """
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=dias)

    resultado = []
    for moeda, fechamentos in _fechamentos_do_recorte(data_inicio, data_fim).items():
        if len(fechamentos) < 2:
            continue

        valor_inicial = float(fechamentos[0].get("cotacaoCompra", 0))
        valor_atual = float(fechamentos[-1].get("cotacaoCompra", 0))
        if not valor_inicial:
            continue

        resultado.append(
            schemas.VariacaoMoedaOut(
                codigo=moeda,
                valor_inicial=valor_inicial,
                valor_atual=valor_atual,
                variacao_percentual=((valor_atual - valor_inicial) / valor_inicial) * 100,
            )
        )

    resultado.sort(key=lambda r: r.variacao_percentual, reverse=True)
    return resultado


@router.get("/mercado", response_model=schemas.DashboardMercadoOut)
def mercado(dias: int = Query(90, ge=1, le=365)):
    """
    Volatilidade (maior variação diária de cada moeda do recorte) e
    variação média por dia da semana (todas as moedas do recorte juntas,
    pra ter amostra suficiente) - as duas vêm da mesma janela de fechamentos
    dia-a-dia, então é uma só passada por moeda na PTAX pras duas métricas.
    """
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=dias)

    volatilidade = []
    soma_por_dia = [0.0] * 7
    qtd_por_dia = [0] * 7

    for moeda, fechamentos in _fechamentos_do_recorte(data_inicio, data_fim).items():
        variacoes = _variacoes_diarias(fechamentos)
        if not variacoes:
            continue

        maior_data, maior_variacao = max(variacoes, key=lambda v: abs(v[1]))
        volatilidade.append(
            schemas.VolatilidadeMoedaOut(
                codigo=moeda,
                maior_variacao_diaria_percentual=maior_variacao,
                data_ocorrencia=maior_data,
            )
        )

        for data_ocorrencia, variacao in variacoes:
            indice = data_ocorrencia.weekday()
            soma_por_dia[indice] += abs(variacao)
            qtd_por_dia[indice] += 1

    volatilidade.sort(key=lambda v: abs(v.maior_variacao_diaria_percentual), reverse=True)

    variacao_por_dia_semana = [
        schemas.VariacaoDiaSemanaOut(
            dia_semana=_DIAS_SEMANA_PT[indice],
            variacao_media_percentual=soma_por_dia[indice] / qtd_por_dia[indice],
            amostras=qtd_por_dia[indice],
        )
        for indice in range(7)
        if qtd_por_dia[indice] > 0
    ]

    return schemas.DashboardMercadoOut(
        volatilidade=volatilidade, variacao_por_dia_semana=variacao_por_dia_semana
    )


@router.get("/conversoes-resumo", response_model=schemas.ResumoConversoesOut)
def conversoes_resumo(db: Session = Depends(get_db), usuario=Depends(obter_usuario_atual)):
    pares_brutos = repositorio.contar_pares_conversao(db, usuario.id)
    total = sum(par.quantidade for par in pares_brutos)

    pares = [
        schemas.ParConversaoOut(
            moeda_origem=par.moeda_origem,
            moeda_destino=par.moeda_destino,
            quantidade=par.quantidade,
            percentual=(par.quantidade / total * 100) if total else 0.0,
        )
        for par in pares_brutos
    ]
    return schemas.ResumoConversoesOut(total=total, pares=pares)


@router.get("/resumo", response_model=schemas.ResumoDashboardOut)
def resumo(db: Session = Depends(get_db), usuario=Depends(obter_usuario_atual)):
    itens = repositorio.listar_itens(db)
    itens_com_alerta = sum(
        1
        for item in itens
        if (variacao := repositorio.calcular_variacao_percentual(db, item.id)) is not None
        and abs(variacao) >= config.ALERTA_VARIACAO_PERCENTUAL
    )

    return schemas.ResumoDashboardOut(
        total_itens=len(itens),
        itens_com_alerta=itens_com_alerta,
        total_conversoes=repositorio.contar_conversoes(db, usuario.id),
    )
