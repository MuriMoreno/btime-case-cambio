"""
Validação de domínio.

Antes de salvar qualquer cotação no CSV, o robô confere se o dado coletado
faz sentido. Isso evita o pior cenário de RPA: gerar um arquivo de saída
silenciosamente vazio ou quebrado, descoberto só lá na frente por quem
consome o CSV.

Regra de negócio: uma cotação inválida é um ERRO DE NEGÓCIO ESPERADO
(a fonte pode mudar de layout, vir vazia, etc.), não uma exceção genérica.
Por isso esta camada sinaliza o problema de forma controlada, para o
chamador registrar no LogErro e decidir o que fazer.
"""


class DadoInvalidoError(Exception):
    """
    Erro de negócio: uma cotação não passou na validação.

    É uma exceção própria (não genérica) justamente para o robô distinguir
    "dado ruim que eu já esperava" de "erro inesperado do Python".
    """
    pass


def validar_cotacao(cotacao):
    """
    Valida uma única cotação. Levanta DadoInvalidoError se algo essencial
    estiver ausente ou claramente incorreto.

    Critérios mínimos:
      - moeda preenchida
      - data da cotação preenchida
      - compra e venda presentes e numéricas
    """
    if not cotacao.moeda or not cotacao.moeda.strip():
        raise DadoInvalidoError("Cotacao sem moeda.")

    if not cotacao.data_cotacao or not cotacao.data_cotacao.strip():
        raise DadoInvalidoError(f"Cotacao da moeda {cotacao.moeda} sem data.")

    if not _eh_numero(cotacao.valor_compra) or not _eh_numero(cotacao.valor_venda):
        raise DadoInvalidoError(
            f"Cotacao {cotacao.moeda} em {cotacao.data_cotacao} com valor "
            f"invalido (compra='{cotacao.valor_compra}', venda='{cotacao.valor_venda}')."
        )


def validar_lote(cotacoes):
    """
    Valida uma lista de cotações. Lista vazia também é erro de negócio
    (a coleta não trouxe nada). Retorna a própria lista se tudo válido.
    """
    if not cotacoes:
        raise DadoInvalidoError("Nenhuma cotacao coletada (lote vazio).")

    for cotacao in cotacoes:
        validar_cotacao(cotacao)

    return cotacoes


def _eh_numero(texto):
    """
    Diz se um texto representa um número. Aceita vírgula ou ponto como
    separador decimal: o site brasileiro usa vírgula ("5,0975") e a API
    usa ponto ("5.0975").
    """
    if texto is None:
        return False
    try:
        float(str(texto).replace(",", "."))
        return True
    except ValueError:
        return False
