"""
Utilitário de resiliência: retry com espera crescente (backoff).

Falhas transitórias (rede oscilando, site fora do ar por instantes, API
com limite momentâneo) são a maior causa de quebra em scraping e API. Em
vez de morrer na primeira tentativa, o robô repete a operação algumas
vezes, esperando um pouco mais a cada tentativa.

Centralizado aqui para os DOIS coletores (Selenium e API) usarem a mesma
política, definida em config (MAX_TENTATIVAS, ESPERA_BASE_SEGUNDOS).
"""

import time

from src.infra import config


def executar_com_retry(operacao, logger, descricao):
    """
    Executa 'operacao' (uma função sem argumentos) com repetição.

    - operacao : função a ser tentada; deve retornar o resultado desejado.
    - logger   : para registrar cada tentativa no LogProcesso.
    - descricao: texto do que está sendo tentado, para os logs.

    Repete até MAX_TENTATIVAS. Entre uma tentativa e outra, espera um tempo
    que cresce a cada rodada (backoff): 1x, 2x, 3x a espera base. Se todas
    falharem, relança a última exceção para o chamador tratar.
    """
    ultima_excecao = None

    for tentativa in range(1, config.MAX_TENTATIVAS + 1):
        try:
            logger.processo(
                f"{descricao} - tentativa {tentativa} de {config.MAX_TENTATIVAS}"
            )
            return operacao()  # deu certo: devolve o resultado e encerra

        except Exception as erro:
            # Guarda a exceção e decide se ainda há tentativas restantes.
            ultima_excecao = erro
            logger.processo(
                f"{descricao} - falhou na tentativa {tentativa}: {erro}"
            )

            if tentativa < config.MAX_TENTATIVAS:
                espera = config.ESPERA_BASE_SEGUNDOS * tentativa  # backoff linear
                logger.processo(f"Aguardando {espera}s antes de nova tentativa...")
                time.sleep(espera)

    # Esgotou as tentativas: relança a última falha para o chamador tratar
    # (o chamador decide se vira erro de negócio ou exceção inesperada).
    raise ultima_excecao
