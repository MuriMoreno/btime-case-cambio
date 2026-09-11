"""
Agendador de coleta automática: a cada config.SCHEDULER_INTERVALO_MINUTOS,
percorre todos os itens cadastrados e coleta a cotação mais recente de
cada um, sem depender do endpoint manual de coleta.

O job roda numa thread do APScheduler, fora do ciclo de requisição da API -
por isso abre sua própria sessão de banco em vez de usar a dependência
get_db das rotas.
"""

from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from src.infra import config
from src.persistencia.database import SessionLocal
from src.persistencia import repositorio
from src.coletores.coletor_item import buscar_cotacao_atual, CotacaoIndisponivelError
from src.api.dependencias import logger_api

_scheduler = BackgroundScheduler()


def _coletar_todos_os_itens():
    db = SessionLocal()
    try:
        itens = repositorio.listar_itens(db)
        logger_api.processo(f"[Agendador] Iniciando coleta de {len(itens)} item(ns).")

        for item in itens:
            try:
                resultado = buscar_cotacao_atual(item.moeda, logger_api)
                repositorio.criar_coleta(
                    db,
                    item_id=item.id,
                    data_cotacao=resultado.data_cotacao,
                    valor_compra=resultado.valor_compra,
                    valor_venda=resultado.valor_venda,
                )
                logger_api.processo(
                    f"[Agendador] Item {item.id} ({item.moeda}): coleta gravada."
                )
            except CotacaoIndisponivelError as erro:
                logger_api.erro(f"[Agendador] Item {item.id} ({item.moeda}): {erro}")
            except Exception as erro:
                logger_api.excecao(
                    f"[Agendador] Falha inesperada no item {item.id} "
                    f"({item.moeda}): {erro}"
                )
    finally:
        db.close()


def iniciar_agendador():
    if not _scheduler.running:
        _scheduler.add_job(
            _coletar_todos_os_itens,
            "interval",
            minutes=config.SCHEDULER_INTERVALO_MINUTOS,
            id="coleta_periodica",
        )
        _scheduler.start()
        logger_api.processo(
            f"[Agendador] Iniciado - coleta a cada "
            f"{config.SCHEDULER_INTERVALO_MINUTOS} minuto(s)."
        )


def parar_agendador():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger_api.processo("[Agendador] Encerrado.")


def proxima_execucao():
    """
    Devolve o datetime (timezone-aware) da próxima coleta automática
    agendada, ou None se o agendador não estiver rodando. Usado pra avisar
    o usuário quanto tempo falta quando ele tenta cadastrar uma moeda que
    já existe.
    """
    job = _scheduler.get_job("coleta_periodica")
    return job.next_run_time if job else None


def segundos_ate_proxima_execucao():
    """
    Quantos segundos faltam para a próxima coleta automática, ou None se o
    agendador não estiver rodando. Usado tanto no aviso de moeda duplicada
    quanto no relógio de contagem regressiva do frontend.
    """
    proxima = proxima_execucao()
    if proxima is None:
        return None

    agora = datetime.now(proxima.tzinfo or timezone.utc)
    return max(0, int((proxima - agora).total_seconds()))
