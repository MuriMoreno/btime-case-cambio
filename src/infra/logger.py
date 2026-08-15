"""
Sistema de logging de três níveis.

O robô mantém três trilhas separadas, cada uma com um propósito distinto
para o dev que sustenta a automação em produção:

  - LogProcesso   : trilha COMPLETA e cronológica de tudo que o robô fez
                    (abriu navegador, acessou URL, extraiu tabela, salvou
                    CSV...). É a "fita" do que aconteceu, do início ao fim.

  - LogErro       : recorte só dos ERROS DE NEGÓCIO ESPERADOS - situações
                    que o robô prevê que podem acontecer e trata de forma
                    controlada (tabela vazia, site fora do ar, elemento
                    nao encontrado, API retornou 429...).

  - LogException  : recorte só das EXCECOES INESPERADAS - erros que o robô
                    NAO previu, que estouram como erro genérico do Python.
                    É o que precisa de investigação porque fugiu do previsto.

Regra de negócio central: todo erro/excecao também é registrado no
LogProcesso. Assim a trilha principal conta a história inteira (incluindo
as falhas, em ordem), e os outros dois logs são atalhos de diagnóstico
para quem quer ir direto ao problema.
"""

import logging
from datetime import datetime

from src.infra import config


class Logger:
    """
    Encapsula as três trilhas de log num objeto só.

    O restante do código nunca mexe em arquivo de log diretamente: chama
    logger.processo(...), logger.erro(...) ou logger.excecao(...), e esta
    classe decide onde cada mensagem é gravada.
    """

    def __init__(self, nome_execucao):
        """
        nome_execucao identifica o fluxo que está rodando (ex: 'scraping'
        ou 'api'), para diferenciar os logs de cada script.
        """
        self.nome_execucao = nome_execucao

        # Cada trilha é um logger nomeado e independente do Python, apontando
        # para seu próprio arquivo. Nomes distintos evitam que o Python
        # misture os handlers das três trilhas.
        self._log_processo = self._montar_logger(
            f"{nome_execucao}_processo", config.PASTA_LOGS / config.ARQUIVO_LOG_PROCESSO
        )
        self._log_erro = self._montar_logger(
            f"{nome_execucao}_erro", config.PASTA_LOGS / config.ARQUIVO_LOG_ERRO
        )
        self._log_excecao = self._montar_logger(
            f"{nome_execucao}_excecao", config.PASTA_LOGS / config.ARQUIVO_LOG_EXCECAO
        )

    def _montar_logger(self, nome, caminho_arquivo):
        """
        Cria um logger do Python que grava em arquivo (append) e também
        ecoa no console, com timestamp e nível padronizados.
        """
        logger = logging.getLogger(nome)
        logger.setLevel(logging.INFO)

        # Evita handlers duplicados se a classe for instanciada mais de uma
        # vez no mesmo processo (senão a mensagem sairia repetida).
        if logger.handlers:
            return logger

        formato = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Handler de arquivo (persistência da trilha).
        handler_arquivo = logging.FileHandler(caminho_arquivo, encoding="utf-8")
        handler_arquivo.setFormatter(formato)
        logger.addHandler(handler_arquivo)

        # Handler de console (acompanhamento em tempo real durante execução).
        handler_console = logging.StreamHandler()
        handler_console.setFormatter(formato)
        logger.addHandler(handler_console)

        return logger

    # -- Métodos públicos: é por aqui que o resto do robô registra tudo. --

    def processo(self, mensagem):
        """Registra um passo normal do fluxo no LogProcesso."""
        self._log_processo.info(mensagem)

    def erro(self, mensagem):
        """
        Registra um erro de negócio ESPERADO.

        Grava no LogErro (recorte de diagnóstico) e TAMBÉM no LogProcesso
        (para a trilha principal manter a história completa em ordem).
        """
        self._log_erro.error(mensagem)
        self._log_processo.error(f"[ERRO DE NEGOCIO] {mensagem}")

    def excecao(self, mensagem):
        """
        Registra uma exceção INESPERADA.

        Grava no LogException (recorte de diagnóstico) e TAMBÉM no
        LogProcesso, pelo mesmo motivo do método erro().
        """
        self._log_excecao.error(mensagem)
        self._log_processo.error(f"[EXCECAO INESPERADA] {mensagem}")

    def resumo_execucao(self, total_coletado, sucesso, inicio, fim):
        """
        Registra no LogProcesso o fechamento da execução: quantos registros
        foram coletados, se terminou com sucesso, e quanto tempo levou.

        É o "relatório final" que quem monitora RPA usa para saber, num
        relance, como foi a rodada sem ler a trilha inteira.
        """
        duracao = (fim - inicio).total_seconds()
        status = "SUCESSO" if sucesso else "FALHA"
        self.processo("-" * 60)
        self.processo(f"RESUMO DA EXECUCAO ({self.nome_execucao})")
        self.processo(f"  Status............: {status}")
        self.processo(f"  Registros coletados: {total_coletado}")
        self.processo(f"  Duracao (segundos).: {duracao:.2f}")
        self.processo("-" * 60)
