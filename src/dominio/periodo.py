"""
Cálculo do período de consulta: o mês anterior completo.

Regra de negócio: o robô sempre consulta o mês CIVIL anterior ao da
execução, do primeiro ao último dia. Rodando em qualquer dia de agosto,
o período é 01/07 a 31/07. Rodando em março, é 01/02 a 28 ou 29/02.

Esta regra vale para os DOIS coletores (scraping e API), por isso fica
centralizada aqui: os dois pedem exatamente o mesmo período, o que mantém
os CSVs comparáveis.

O último dia do mês NÃO é fixo (28/29/30/31) - é calculado, o que trata
corretamente meses de tamanhos diferentes e fevereiro em ano bissexto.
"""

from datetime import date
import calendar


def periodo_mes_anterior(data_referencia=None):
    """
    Retorna (data_inicial, data_final) como objetos date, cobrindo todo o
    mês anterior ao da data de referência (por padrão, hoje).

    Exemplo: referência 15/08/2026 -> (01/07/2026, 31/07/2026).
    """
    if data_referencia is None:
        data_referencia = date.today()

    ano = data_referencia.year
    mes = data_referencia.month

    # Retrocede um mês. Se estamos em janeiro, o mês anterior é dezembro
    # do ano passado - por isso o ajuste de ano.
    if mes == 1:
        mes_anterior = 12
        ano_anterior = ano - 1
    else:
        mes_anterior = mes - 1
        ano_anterior = ano

    # Primeiro dia é sempre 1. O último dia vem de calendar.monthrange, que
    # devolve quantos dias o mês tem (trata bissexto automaticamente).
    primeiro_dia = date(ano_anterior, mes_anterior, 1)
    ultimo_dia_numero = calendar.monthrange(ano_anterior, mes_anterior)[1]
    ultimo_dia = date(ano_anterior, mes_anterior, ultimo_dia_numero)

    return primeiro_dia, ultimo_dia


def rotulo_mes_anterior(data_referencia=None):
    """
    Retorna o rótulo AAAA-MM do mês anterior (o mês dos dados coletados),
    usado como prefixo no nome dos arquivos CSV para manter histórico.

    Exemplo: referência 15/08/2026 -> "2026-07".

    O formato ano-mês faz os arquivos se ordenarem cronologicamente sozinhos
    ao listar a pasta.
    """
    inicio, _ = periodo_mes_anterior(data_referencia)
    return inicio.strftime("%Y-%m")
