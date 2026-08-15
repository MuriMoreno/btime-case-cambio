"""
Gestor de evidências.

Quando algo dá errado, o robô guarda uma "prova" do que aconteceu, para o
dev de sustentação diagnosticar depois sem precisar reproduzir o erro:

  - No Selenium: um screenshot da tela no momento exato da falha (a "cena
    do crime" - onde o robô estava quando quebrou).

  - Na API: a resposta crua recebida (o texto/JSON que a API devolveu),
    que é o equivalente ao screenshot no mundo sem tela.

Todas as evidências vão para a pasta 'evidencias', nomeadas com etapa +
timestamp, para localização imediata: abrindo a pasta, dá para saber
"falhou em tal etapa, em tal horário".
"""

from datetime import datetime

from src.infra import config


def _nome_com_timestamp(etapa, extensao):
    """
    Monta um nome de arquivo único: <etapa>_<AAAAMMDD_HHMMSS>.<extensao>.
    O timestamp evita que uma evidência sobrescreva a anterior.
    """
    momento = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{etapa}_{momento}.{extensao}"


def salvar_screenshot(driver, etapa, logger):
    """
    Salva um screenshot da tela atual do navegador (uso no Selenium).

    - driver: o WebDriver ativo do Selenium.
    - etapa : identifica em que ponto do fluxo o erro ocorreu.
    Retorna o caminho do arquivo salvo (para citar no log/erro).
    """
    nome = _nome_com_timestamp(etapa, "png")
    caminho = config.PASTA_EVIDENCIAS / nome
    try:
        driver.save_screenshot(str(caminho))
        logger.processo(f"Screenshot de evidencia salvo: {caminho}")
    except Exception as erro:
        # Falhar ao salvar a evidência não pode mascarar o erro original;
        # apenas registra que a evidência não pôde ser capturada.
        logger.processo(f"Nao foi possivel salvar screenshot: {erro}")
    return caminho


def salvar_resposta_crua(texto, etapa, logger):
    """
    Salva o corpo cru de uma resposta (uso na API) como arquivo de texto.

    É o análogo do screenshot para o mundo de API: preserva exatamente o
    que a fonte devolveu no momento da falha, para inspeção posterior.
    """
    nome = _nome_com_timestamp(etapa, "txt")
    caminho = config.PASTA_EVIDENCIAS / nome
    try:
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto if texto is not None else "")
        logger.processo(f"Resposta crua salva como evidencia: {caminho}")
    except Exception as erro:
        logger.processo(f"Nao foi possivel salvar resposta crua: {erro}")
    return caminho
