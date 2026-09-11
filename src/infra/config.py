"""
Configuração central do projeto.

Toda a parametrização do robô fica concentrada aqui: caminhos de pastas,
timeouts, política de retry, headers, moedas monitoradas e endpoints.

Regra de negócio: nenhum valor "mágico" deve ficar espalhado no meio da
lógica. Quem sustenta o robô ajusta o comportamento neste único arquivo,
sem precisar entender ou tocar no código dos coletores.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos base do projeto.
# Tudo é derivado da raiz do projeto (dois níveis acima deste arquivo:
# .../src/infra/config.py -> raiz), para o robô funcionar independente de
# onde a máquina o executa (ambiente de produção limpo).
# ---------------------------------------------------------------------------
RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent

PASTA_LOGS = RAIZ_PROJETO / "logs"
PASTA_EVIDENCIAS = RAIZ_PROJETO / "evidencias"
PASTA_SAIDA_CSV = RAIZ_PROJETO / "saida_csv"
PASTA_DADOS = RAIZ_PROJETO / "dados"

# Pastas que o robô garante existir no arranque. Se não existirem, cria;
# se existirem, mantém. (ver infra/ambiente.py)
PASTAS_OBRIGATORIAS = [PASTA_LOGS, PASTA_EVIDENCIAS, PASTA_SAIDA_CSV, PASTA_DADOS]

# ---------------------------------------------------------------------------
# Nomes dos arquivos de log (os três níveis).
# ---------------------------------------------------------------------------
ARQUIVO_LOG_PROCESSO = "LogProcesso.log"      # trilha completa do que o robô fez
ARQUIVO_LOG_ERRO = "LogErro.log"              # erros de negócio esperados/tratados
ARQUIVO_LOG_EXCECAO = "LogException.log"      # exceções inesperadas (não previstas)

# ---------------------------------------------------------------------------
# Política de resiliência.
# Falhas transitórias (rede lenta, site fora do ar por 1s, API com limite
# momentâneo) são comuns em scraping/API. Em vez de morrer na 1ª tentativa,
# o robô tenta de novo com espera crescente entre as tentativas.
# ---------------------------------------------------------------------------
MAX_TENTATIVAS = 3            # nº de tentativas antes de desistir
ESPERA_BASE_SEGUNDOS = 2      # espera inicial; cresce a cada tentativa (backoff)

# ---------------------------------------------------------------------------
# Configuração do Selenium (scraping).
# ---------------------------------------------------------------------------
# headless=True roda sem abrir janela (produção). Deixe False para depurar
# visualmente vendo o navegador agir.
SELENIUM_HEADLESS = False
SELENIUM_TIMEOUT = 20         # segundos que o robô espera um elemento aparecer

# User-agent realista reduz bloqueio anti-bot: muitos sites barram o
# user-agent padrão do automator.
SELENIUM_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Configuração da API pública de câmbio (API PTAX oficial do Banco Central).
# Recurso CotacaoMoedaPeriodo: retorna compra e venda por data num período.
# Gratuita, sem necessidade de chave.
# ---------------------------------------------------------------------------
API_TIMEOUT = 20
API_URL_BASE = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoMoedaPeriodo"
)

# Recurso Moedas: lista as moedas parametrizadas na PTAX (código + nome).
# Usado pelo backend para alimentar o seletor de moeda do frontend, em vez
# de o usuário digitar um código de cabeça.
API_URL_MOEDAS = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "Moedas?$format=json"
)

# Boletim que interessa: o site do BCB exibe o FECHAMENTO. A API retorna
# cinco boletins por dia (abertura, 3 intermediários, fechamento); filtramos
# só o de fechamento para casar com o scraping.
API_TIPO_BOLETIM_FECHAMENTO = "Fechamento"

# ---------------------------------------------------------------------------
# Moedas monitoradas (contra o Real), pelos códigos usados pelo BCB.
# Os dois coletores (scraping e API) usam o mesmo conjunto, para os CSVs
# finais serem comparáveis.
# ---------------------------------------------------------------------------
MOEDAS = ["USD", "EUR", "GBP"]

# Rótulo legível de cada moeda no site do BCB (usado no dropdown do scraping).
MOEDA_LABEL_SITE = {
    "USD": "DOLAR DOS EUA",
    "EUR": "EURO",
    "GBP": "LIBRA ESTERLINA",
}

# URL da página de histórico de cotações do site do BCB (scraping).
SITE_BCB_URL = (
    "https://www.bcb.gov.br/estabilidadefinanceira/historicocotacoes"
)

# ---------------------------------------------------------------------------
# Backend (API/FastAPI) - monitor de itens.
# ---------------------------------------------------------------------------
# Banco SQLite: simples, sem servico externo, consistente com o resto do
# projeto (roda numa maquina limpa sem preparacao manual).
CAMINHO_BANCO_DADOS = PASTA_DADOS / "monitor.db"
DATABASE_URL = f"sqlite:///{CAMINHO_BANCO_DADOS}"

# Intervalo da coleta automatica (agendador).
SCHEDULER_INTERVALO_MINUTOS = 10

# Janela de dias usada para achar "a cotacao mais recente" de uma moeda
# (cobre fins de semana/feriados sem boletim publicado).
JANELA_DIAS_COTACAO_ATUAL = 10

# Limite de dias aceito na consulta livre (GET /cotacoes), para nao deixar
# a requisicao varrer um intervalo enorme na PTAX de uma vez.
JANELA_MAXIMA_CONSULTA_DIAS = 90

# ---------------------------------------------------------------------------
# Autenticacao.
# Um usuario so (o do Muri) por enquanto, mas a estrutura (tabela de
# usuarios, senha com hash, token JWT) e a mesma usada num sistema
# multiusuario de verdade - nao um "login fake".
# ---------------------------------------------------------------------------
# Em desenvolvimento local usa o valor padrao abaixo; numa API exposta de
# verdade, isso TEM que vir de variavel de ambiente (nunca commitado).
JWT_SECRET_KEY = os.environ.get(
    "JWT_SECRET_KEY", "chave-de-desenvolvimento-btime-nao-usar-em-producao"
)
JWT_ALGORITHM = "HS256"
JWT_EXPIRACAO_HORAS = 24

# ---------------------------------------------------------------------------
# Alerta de variacao brusca.
# Se a cotacao (compra) variar isso ou mais entre a coleta mais recente e a
# anterior, o item ganha um selo visual de alta/queda no frontend.
# ---------------------------------------------------------------------------
ALERTA_VARIACAO_PERCENTUAL = 2.0

# ---------------------------------------------------------------------------
# Dashboard: ranking de maiores altas/baixas num período.
# Recorte de moedas relevantes e líquidas (não a lista inteira da PTAX,
# ~200 códigos) para o ranking responder rápido e não misturar moeda
# exótica/pouco negociada com pouquíssimo histórico no meio do resultado.
# ---------------------------------------------------------------------------
MOEDAS_DASHBOARD_RANKING = [
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY",
    "ARS", "CLP", "MXN", "NOK", "SEK", "DKK", "NZD",
]
