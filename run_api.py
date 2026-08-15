"""
Ponto de entrada: coleta via API PTAX oficial do Banco Central.

Espelha run_scraping.py: mesma sequencia, mesmo tratamento de erros, mesmo
CSV de saida (estrutura identica) - so muda a fonte, que aqui e a API.

Executar:  python run_api.py
"""

from datetime import datetime

from src.infra.ambiente import preparar_ambiente
from src.infra.logger import Logger
from src.infra import config
from src.dominio.validacao import validar_lote, DadoInvalidoError
from src.saida.escritor_csv import salvar_csv
from src.coletores.coletor_api import coletar_via_api
from src.dominio.periodo import rotulo_mes_anterior


def main():
    preparar_ambiente()
    logger = Logger("api")
    preparar_ambiente(logger)

    inicio = datetime.now()
    sucesso = False
    total = 0

    logger.processo("=" * 60)
    logger.processo("INICIO DA EXECUCAO - COLETA VIA API PTAX (BCB)")
    logger.processo("=" * 60)

    try:
        cotacoes = coletar_via_api(logger)
        validar_lote(cotacoes)

        # Nome com prefixo do mes coletado (AAAA-MM) para manter historico.
        nome_arquivo = f"{rotulo_mes_anterior()}_cotacoes_api.csv"
        caminho = config.PASTA_SAIDA_CSV / nome_arquivo
        salvar_csv(cotacoes, caminho, logger)

        total = len(cotacoes)
        sucesso = True

    except (DadoInvalidoError, RuntimeError) as erro:
        logger.erro(f"Execucao interrompida por erro de negocio: {erro}")

    except Exception as erro:
        logger.excecao(f"Excecao inesperada na execucao: {erro}")

    finally:
        fim = datetime.now()
        logger.resumo_execucao(total, sucesso, inicio, fim)


if __name__ == "__main__":
    main()
