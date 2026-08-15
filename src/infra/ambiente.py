"""
Preparação de ambiente.

Antes de qualquer execução, o robô garante que toda a estrutura de pastas
que ele precisa (logs, evidencias, saida_csv) exista na máquina.

Regra de negócio: o robô deve rodar numa máquina limpa sem quebrar por
falta de diretório. Se a pasta existe, mantém; se não existe, cria. Esse
é o comportamento esperado de um ambiente de produção que se auto-prepara.
"""

from src.infra import config


def preparar_ambiente(logger=None):
    """
    Verifica cada pasta obrigatória e a cria se não existir.

    Recebe o logger opcionalmente para registrar o que foi feito no
    LogProcesso. É opcional porque a preparação de pastas precisa poder
    rodar ANTES do logger existir (o próprio logger escreve na pasta de
    logs, que esta função garante que exista).
    """
    for pasta in config.PASTAS_OBRIGATORIAS:
        if pasta.exists():
            # Pasta já existe: nada a criar, apenas registra a verificação.
            if logger:
                logger.processo(f"Diretorio ja existente: {pasta}")
        else:
            # Pasta ausente: cria (inclusive pais, se necessário).
            pasta.mkdir(parents=True, exist_ok=True)
            if logger:
                logger.processo(f"Diretorio criado: {pasta}")
