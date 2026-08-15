"""
Catálogo de seletores (XPaths) do site do BCB.

Todos os XPaths usados no scraping ficam CENTRALIZADOS aqui, separados da
lógica de execução. Motivo (e é o ponto central de sustentação): quando o
site muda de layout - e sites mudam - o dev de sustentação corrige o
seletor NESTE único arquivo, sem caçar no meio do código do coletor.

Cada elemento é uma entrada com três informações:
  - xpath    : o seletor em si.
  - descricao: o que é aquele elemento, em linguagem humana.
  - imagem   : caminho de um print de referência (em docs/xpath_imagens/)
               com a área do elemento destacada. Essa imagem é DOCUMENTAÇÃO
               estática, colocada manualmente pelo dev - NÃO é gerada em
               tempo de execução. Serve para o dev de sustentação bater o
               olho e saber exatamente qual elemento é aquele na tela.

Como preencher as imagens: tire o print da tela, destaque (com um retângulo)
onde fica o elemento, salve em docs/xpath_imagens/ e referencie aqui. Se
ainda não houver imagem para um elemento, o campo fica como string vazia.
"""

# Pasta (relativa à raiz do projeto) onde ficam os prints de documentação.
PASTA_IMAGENS_DOC = "docs/xpath_imagens"

# Catálogo de elementos. A chave é um nome curto usado no código do coletor.
ELEMENTOS = {
    "radio_periodo_moeda": {
        # Opção "Cotações de fechamento de uma moeda em um período".
        # Ancorado em tipo + value: resiste a mudanca de ordem dos radios.
        "xpath": "//input[@type='radio' and @value='1']",
        "descricao": "Radio: cotacoes de fechamento de uma moeda em um periodo",
        "imagem": f"{PASTA_IMAGENS_DOC}/radio_periodo_moeda.png",
    },
    "input_data_inicial": {
        "xpath": "//input[@name='DATAINI']",
        "descricao": "Campo de texto: Data Inicial (DD/MM/AAAA)",
        "imagem": f"{PASTA_IMAGENS_DOC}/input_data_inicial.png",
    },
    "input_data_final": {
        "xpath": "//input[@name='DATAFIM']",
        "descricao": "Campo de texto: Data Final (DD/MM/AAAA)",
        "imagem": f"{PASTA_IMAGENS_DOC}/input_data_final.png",
    },
    "select_moeda": {
        # <select> nativo. A seleção é feita pela classe Select do Selenium
        # (select_by_visible_text), por isso guardamos o XPath do próprio
        # select, e não de um <option> específico.
        "xpath": "//select[@name='ChkMoeda']",
        "descricao": "Dropdown de selecao da moeda",
        "imagem": f"{PASTA_IMAGENS_DOC}/select_moeda.png",
    },
    "botao_pesquisar": {
        "xpath": "//input[@value='Pesquisar']",
        "descricao": "Botao Pesquisar (submete o formulario)",
        "imagem": f"{PASTA_IMAGENS_DOC}/botao_pesquisar.png",
    },
    "tabela_resultado": {
        # Tabela de resultado. Observacao de sustentacao: se um dia a classe
        # 'tabela' aparecer em mais de um elemento na pagina, restrinja o
        # seletor ao container de resultado para evitar ambiguidade.
        "xpath": "//table[@class='tabela']",
        "descricao": "Tabela com o resultado das cotacoes",
        "imagem": f"{PASTA_IMAGENS_DOC}/tabela_resultado.png",
    },
    "linhas_dados": {
        # Linhas de DADOS: <tr> que contêm <td>. As linhas de cabecalho usam
        # <th>, entao esta condicao as exclui automaticamente - extracao
        # robusta que nao depende de pular linhas por posicao.
        "xpath": "//table[@class='tabela']//tr[td]",
        "descricao": "Linhas de dados da tabela (exclui cabecalho, que usa th)",
        "imagem": f"{PASTA_IMAGENS_DOC}/tabela_resultado.png",
    },
}
