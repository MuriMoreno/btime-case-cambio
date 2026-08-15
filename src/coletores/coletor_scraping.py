"""
Coletor de cotações via web scraping do site do BCB (Selenium).

Executa o fluxo real que um humano faria na página de histórico de cotações
do Banco Central: marca a opção de período, preenche data inicial e final
(mês anterior), seleciona a moeda, clica em Pesquisar, espera a tabela e
extrai as linhas (Data, Tipo, Compra, Venda).

Produz os mesmos objetos Cotacao do coletor de API, alimentando o mesmo
escritor de CSV - por isso os dois arquivos finais têm a mesma estrutura.

Robustez (o site pede, e é o coração do RPA de sustentacao):
  - todos os seletores vêm do catálogo central xpaths_bcb (fáceis de
    corrigir quando o site muda);
  - esperas explícitas aguardam cada elemento aparecer (o site do BCB
    renderiza via JavaScript);
  - a coleta de cada moeda roda sob retry (falhas transitórias);
  - QUALQUER erro dispara um screenshot da tela (a "cena do crime") salvo
    como evidência antes de propagar o erro.

Observação de ambiente: requer o pacote 'selenium' e o navegador Chrome
instalado. O driver é resolvido automaticamente pelo Selenium Manager
(embutido no Selenium 4.6+), sem download manual de chromedriver.
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from src.infra import config
from src.infra.retry import executar_com_retry
from src.infra.evidencia import salvar_screenshot
from src.dominio.cotacao import Cotacao
from src.dominio.periodo import periodo_mes_anterior
from src.coletores.xpaths_bcb import ELEMENTOS


def _criar_driver(logger):
    """
    Inicializa o navegador Chrome com as opções do config.

    headless (sem janela) e user-agent realista vêm do config - o
    user-agent reduz bloqueio anti-bot, e o headless permite rodar em
    servidor sem interface grafica.
    """
    opcoes = Options()
    if config.SELENIUM_HEADLESS:
        opcoes.add_argument("--headless=new")
    opcoes.add_argument("--no-sandbox")
    opcoes.add_argument("--disable-dev-shm-usage")
    opcoes.add_argument(f"--user-agent={config.SELENIUM_USER_AGENT}")

    logger.processo("Inicializando navegador Chrome (Selenium Manager resolve o driver)")
    driver = webdriver.Chrome(options=opcoes)
    driver.maximize_window()
    return driver


def _esperar(driver, chave_elemento):
    """
    Espera um elemento do catálogo ficar presente na página e o retorna.

    Recebe a CHAVE do elemento no catálogo xpaths_bcb (não o xpath direto),
    para toda referência a seletor passar pelo catálogo central.
    """
    xpath = ELEMENTOS[chave_elemento]["xpath"]
    espera = WebDriverWait(driver, config.SELENIUM_TIMEOUT)
    return espera.until(EC.presence_of_element_located((By.XPATH, xpath)))


def _preencher_via_js(driver, elemento, valor):
    """
    Preenche um campo de texto definindo seu valor diretamente via
    JavaScript, em vez de digitar caractere a caractere.

    Usado nos campos de data, que tem mascara de formatacao: a digitacao
    normal (send_keys) se atropela com a mascara e embaralha o valor.
    Definir o value de uma vez contorna a mascara. Em seguida disparamos
    os eventos 'input' e 'change' para o site reconhecer a alteracao como
    se tivesse sido feita pelo usuario.
    """
    driver.execute_script(
        """
        const campo = arguments[0];
        campo.value = arguments[1];
        campo.dispatchEvent(new Event('input',  { bubbles: true }));
        campo.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        elemento,
        valor,
    )


def _coletar_moeda(driver, moeda, logger):
    """
    Executa o fluxo completo para UMA moeda e devolve suas cotações.

    É esta função que roda sob retry no chamador: se algo falhar por causa
    transitória, o fluxo inteiro da moeda é repetido.
    """
    data_inicial, data_final = periodo_mes_anterior()
    data_ini_txt = data_inicial.strftime("%d/%m/%Y")
    data_fim_txt = data_final.strftime("%d/%m/%Y")
    label_moeda = config.MOEDA_LABEL_SITE[moeda]

    logger.processo(f"[{moeda}] Abrindo a pagina do BCB: {config.SITE_BCB_URL}")
    # Garante que estamos no documento principal antes de navegar (na 2a
    # moeda em diante, o contexto poderia ainda estar no iframe anterior).
    driver.switch_to.default_content()
    driver.get(config.SITE_BCB_URL)

    # A pagina do BCB embute o formulario real dentro de um <iframe> (o
    # sistema ptax_internet). O Selenium so enxerga o documento principal,
    # entao e preciso trocar o contexto para dentro do iframe ANTES de
    # procurar qualquer elemento do formulario - senao nada e encontrado.
    logger.processo(f"[{moeda}] Entrando no iframe do formulario")
    espera_iframe = WebDriverWait(driver, config.SELENIUM_TIMEOUT)
    espera_iframe.until(
        EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe"))
    )

    # 1) Marca a opção "cotacoes de fechamento de uma moeda em um periodo".
    logger.processo(f"[{moeda}] Selecionando a opcao de periodo por moeda")
    radio = _esperar(driver, "radio_periodo_moeda")
    if not radio.is_selected():
        radio.click()

    # 2) Preenche data inicial.
    # OBS: os campos de data do BCB tem MASCARA (formatacao automatica das
    # barras). Digitar caractere a caractere faz a mascara se atropelar com
    # o texto enviado, embaralhando a data. Para evitar isso, o valor e
    # definido diretamente via JavaScript, que preenche o campo de uma vez
    # sem disparar a digitacao caractere a caractere.
    logger.processo(f"[{moeda}] Preenchendo data inicial: {data_ini_txt}")
    campo_ini = _esperar(driver, "input_data_inicial")
    _preencher_via_js(driver, campo_ini, data_ini_txt)

    # 3) Preenche data final (mesma tecnica).
    logger.processo(f"[{moeda}] Preenchendo data final: {data_fim_txt}")
    campo_fim = _esperar(driver, "input_data_final")
    _preencher_via_js(driver, campo_fim, data_fim_txt)

    # 4) Seleciona a moeda pelo TEXTO EXATO (Select nativo). Texto exato
    #    evita ambiguidade que um 'contains' teria (ex.: varios "BOLIVAR").
    logger.processo(f"[{moeda}] Selecionando a moeda no dropdown: {label_moeda}")
    elemento_select = _esperar(driver, "select_moeda")
    Select(elemento_select).select_by_visible_text(label_moeda)

    # 5) Clica em Pesquisar.
    logger.processo(f"[{moeda}] Clicando em Pesquisar")
    _esperar(driver, "botao_pesquisar").click()

    # 6) Espera a tabela de resultado aparecer (renderizada apos a consulta).
    logger.processo(f"[{moeda}] Aguardando a tabela de resultado")
    _esperar(driver, "tabela_resultado")

    # 7) Extrai as linhas de dados (tr que contem td; cabecalho usa th).
    xpath_linhas = ELEMENTOS["linhas_dados"]["xpath"]
    linhas = driver.find_elements(By.XPATH, xpath_linhas)
    logger.processo(f"[{moeda}] {len(linhas)} linha(s) de dados encontrada(s)")

    momento_coleta = Cotacao.carimbo_agora()
    cotacoes = []

    for linha in linhas:
        celulas = linha.find_elements(By.TAG_NAME, "td")
        # As quatro primeiras colunas tem o mesmo significado nas duas
        # variacoes de tabela (dolar tem 4 colunas; euro/libra tem 6, com
        # duas de PARIDADE ao final que ignoramos). Por isso lemos apenas as
        # quatro primeiras: Data, Tipo, Compra, Venda.
        if len(celulas) < 4:
            continue  # linha fora do padrao esperado; ignora com seguranca

        cotacao = Cotacao(
            moeda=moeda,
            data_cotacao=celulas[0].text.strip(),
            tipo=celulas[1].text.strip(),
            valor_compra=celulas[2].text.strip(),
            valor_venda=celulas[3].text.strip(),
            data_coleta=momento_coleta,
            fonte="scraping",
        )
        cotacoes.append(cotacao)

    return cotacoes


def coletar_via_scraping(logger):
    """
    Coleta as cotações de todas as moedas configuradas via scraping.

    Abre um único navegador e reaproveita para todas as moedas. Cada moeda
    roda sob retry. Se uma moeda falhar em todas as tentativas, tira o
    screenshot de evidencia e propaga como RuntimeError para o ponto de
    entrada registrar (LogErro/LogException).
    """
    driver = None
    todas_cotacoes = []

    try:
        driver = _criar_driver(logger)

        for moeda in config.MOEDAS:
            def coletar():
                return _coletar_moeda(driver, moeda, logger)

            try:
                cotacoes_moeda = executar_com_retry(
                    coletar, logger, f"Scraping da moeda {moeda}"
                )
                todas_cotacoes.extend(cotacoes_moeda)
                logger.processo(
                    f"[{moeda}] coleta concluida: {len(cotacoes_moeda)} registro(s)"
                )
            except Exception as erro:
                # Falhou todas as tentativas desta moeda: evidencia + propaga.
                salvar_screenshot(driver, f"erro_scraping_{moeda}", logger)
                raise RuntimeError(
                    f"Falha ao coletar {moeda} via scraping: {erro}"
                ) from erro

        return todas_cotacoes

    finally:
        # Fecha o navegador sempre, mesmo se deu erro no meio.
        if driver is not None:
            logger.processo("Encerrando o navegador")
            driver.quit()
