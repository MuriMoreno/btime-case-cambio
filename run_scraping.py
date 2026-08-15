"""
Ponto de entrada: coleta via WEB SCRAPING (Selenium) do site do BCB.

Orquestra o fluxo de ponta a ponta e é fino de proposito - a logica mora
nas camadas. Sequencia:
  1. prepara o ambiente (garante as pastas);
  2. inicializa o logger de tres niveis;
  3. coleta as cotacoes via scraping;
  4. valida o lote;
  5. salva o CSV;
  6. registra o resumo da execucao.

Trata os dois tipos de falha de forma separada, exatamente como os logs:
  - DadoInvalidoError / RuntimeError => ERRO DE NEGOCIO esperado (LogErro);
  - qualquer outra excecao            => INESPERADA (LogException).

Executar:  python run_scraping.py
"""

from datetime import datetime

from src.infra.ambiente import preparar_ambiente
from src.infra.logger import Logger
from src.infra import config
from src.dominio.validacao import validar_lote, DadoInvalidoError
from src.saida.escritor_csv import salvar_csv
from src.coletores.coletor_scraping import coletar_via_scraping
from src.dominio.periodo import rotulo_mes_anterior


def main():
    # Garante as pastas ANTES de criar o logger (ele escreve na pasta logs).
    preparar_ambiente()
    logger = Logger("scraping")
    preparar_ambiente(logger)  # agora registra a verificacao no LogProcesso

    inicio = datetime.now()
    sucesso = False
    total = 0

    logger.processo("=" * 60)
    logger.processo("INICIO DA EXECUCAO - COLETA VIA WEB SCRAPING (BCB)")
    logger.processo("=" * 60)

    try:
        cotacoes = coletar_via_scraping(logger)

        # Valida antes de salvar: nunca gerar CSV vazio/quebrado em silencio.
        validar_lote(cotacoes)

        # Nome com prefixo do mes coletado (AAAA-MM) para manter historico.
        nome_arquivo = f"{rotulo_mes_anterior()}_cotacoes_scraping.csv"
        caminho = config.PASTA_SAIDA_CSV / nome_arquivo
        salvar_csv(cotacoes, caminho, logger)

        total = len(cotacoes)
        sucesso = True

    except (DadoInvalidoError, RuntimeError) as erro:
        # Erro de negocio esperado: registrado de forma controlada.
        logger.erro(f"Execucao interrompida por erro de negocio: {erro}")

    except Exception as erro:
        # Excecao inesperada: nao prevista - vai para o LogException.
        logger.excecao(f"Excecao inesperada na execucao: {erro}")

    finally:
        fim = datetime.now()
        logger.resumo_execucao(total, sucesso, inicio, fim)


if __name__ == "__main__":
    main()
