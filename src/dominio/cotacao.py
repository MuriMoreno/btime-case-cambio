"""
Modelo de domínio: Cotacao.

Representa uma cotação de câmbio PTAX de fechamento, padronizada e
independente de COMO foi obtida (scraping do site do BCB ou API PTAX).
Tanto o coletor Selenium quanto o de API produzem objetos Cotacao iguais,
e a camada de saída (CSV) só conhece Cotacao.

Os campos refletem exatamente o que as DUAS fontes têm em comum (a tabela
do site e o retorno da API PTAX): moeda, data, tipo, compra e venda. Não
há campo "variação" porque a PTAX de fechamento não expõe esse dado - e
inventar coluna vazia geraria um CSV enganoso.

Regra de negócio: padronizar aqui é o que garante que os dois CSVs finais
tenham a mesma estrutura E o mesmo formato numérico. As fontes entregam os
valores de formas diferentes (a API usa ponto decimal e omite zeros a
direita - "5.195"; o site usa virgula e 4 casas - "5,1950"). O modelo
normaliza ambos para VIRGULA com 4 casas decimais, para os arquivos
ficarem consistentes entre si e abrirem corretos no Excel brasileiro.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime


def _normalizar_valor(valor):
    """
    Normaliza um valor monetario para o padrao brasileiro: virgula decimal
    e 4 casas fixas. Aceita entrada com ponto ("5.195") ou virgula
    ("5,1950"). Se o valor nao for numerico (ex.: campo vazio vindo da
    fonte), devolve o original sem quebrar - a validacao trata isso depois.
    """
    if valor is None:
        return ""
    try:
        numero = float(str(valor).replace(",", "."))
        return f"{numero:.4f}".replace(".", ",")
    except ValueError:
        return str(valor)


@dataclass
class Cotacao:
    """
    Uma linha de cotação PTAX de fechamento.

    Campos:
      moeda        : a moeda cotada contra o Real, ex. "USD"
      data_cotacao : data a que a cotação se refere (DD/MM/AAAA)
      tipo         : tipo do boletim (ex. "A" = fechamento PTAX)
      valor_compra : cotação de compra em Real (normalizada: virgula, 4 casas)
      valor_venda  : cotação de venda em Real (normalizada: virgula, 4 casas)
      data_coleta  : data/hora em que o robô coletou (carimbo do robô)
      fonte        : origem do dado ("scraping" ou "api"), para
                     rastreabilidade dentro do próprio CSV
    """

    moeda: str
    data_cotacao: str
    tipo: str
    valor_compra: str
    valor_venda: str
    data_coleta: str
    fonte: str

    def __post_init__(self):
        """
        Executado automaticamente apos a criacao. Normaliza os valores de
        compra e venda para o padrao brasileiro, independentemente do
        formato em que a fonte os entregou. Centralizar isso aqui garante
        que scraping e API produzam CSVs com numeros identicos em formato.
        """
        self.valor_compra = _normalizar_valor(self.valor_compra)
        self.valor_venda = _normalizar_valor(self.valor_venda)

    @staticmethod
    def carimbo_agora():
        """Horário atual formatado, usado como data_coleta pelos dois coletores."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def como_dicionario(self):
        """Converte em dicionário para a camada de saída escrever a linha do CSV."""
        return asdict(self)
