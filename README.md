# btime-case-cambio

Coleta automatizada de cotações de câmbio (PTAX) do Banco Central do Brasil por **duas técnicas independentes** — web scraping e API pública — gravando o resultado em CSV. Projeto desenvolvido como case técnico para a vaga de Dev RPA.

O robô sempre consulta o **mês civil anterior** ao da execução (rodando em qualquer dia de agosto, coleta 01/07 a 31/07), para as moedas **USD, EUR e GBP** contra o Real.

## Sumário

- [Como funciona](#como-funciona)
- [Arquitetura](#arquitetura)
- [Estrutura de pastas](#estrutura-de-pastas)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Como executar](#como-executar)
- [Saída gerada](#saída-gerada)
- [Sistema de logs](#sistema-de-logs)
- [Tratamento de erros e resiliência](#tratamento-de-erros-e-resiliência)
- [Detalhes técnicos do scraping](#detalhes-técnicos-do-scraping)
- [Manutenção dos seletores (XPath)](#manutenção-dos-seletores-xpath)

## Como funciona

São dois scripts independentes que resolvem o mesmo problema por caminhos diferentes:

- **`run_scraping.py`** — abre o site do BCB com Selenium, preenche o formulário (período e moeda), pesquisa e extrai a tabela de cotações da tela.
- **`run_api.py`** — consulta a API PTAX oficial do BCB (recurso `CotacaoMoedaPeriodo`) e lê os mesmos dados de forma estruturada.

Ambos produzem um CSV de **estrutura idêntica**, o que permite comparar diretamente o resultado das duas técnicas.

## Arquitetura

O projeto segue uma arquitetura em camadas inspirada na **Clean Architecture**, com uma regra central: *scraping e API são apenas duas fontes diferentes que produzem o mesmo modelo de dado e passam pelo mesmo caminho de saída, apoiadas por uma infraestrutura comum*.

```
                        ┌──────────────────────────┐
                        │   Pontos de entrada       │
                        │  run_scraping / run_api   │
                        └────────────┬─────────────┘
                                     │ orquestra
             ┌───────────────────────┼───────────────────────┐
             │                       │                       │
      ┌──────▼───────┐        ┌──────▼───────┐        ┌──────▼───────┐
      │  Coletores    │        │   Domínio     │        │    Saída      │
      │ (fontes)      │        │              │        │              │
      │ • scraping    │───────▶│ • Cotacao     │───────▶│ • escritor    │
      │ • api         │ produz │ • validação   │ valida │   CSV         │
      │              │        │ • período     │        │              │
      └──────┬───────┘        └──────────────┘        └──────────────┘
             │
             │ usa
      ┌──────▼──────────────────────────────────────────────────────┐
      │                      Infraestrutura                          │
      │  config · logger (3 níveis) · ambiente · retry · evidência   │
      │  · catálogo de XPaths                                        │
      └──────────────────────────────────────────────────────────────┘
```

**Princípio da separação de responsabilidades:** cada camada conhece só o necessário. Os coletores sabem ir na fonte e produzir um `Cotacao`; o domínio define o que é uma cotação válida; a saída sabe escrever CSV. Trocar a fonte (outro site, outra API) não afeta domínio nem saída. Trocar o formato de saída não afeta a coleta.

- **Domínio** (`src/dominio/`) — o núcleo, independente de como o dado é obtido. Contém o modelo `Cotacao` (a "língua comum"), a validação e a regra de negócio do período (mês anterior).
- **Coletores** (`src/coletores/`) — as duas fontes de dados. Cada uma lida com as falhas do seu jeito (screenshot no Selenium, resposta crua na API) e devolve o modelo padronizado.
- **Saída** (`src/saida/`) — escreve o CSV. Uma só, usada pelos dois fluxos, o que garante arquivos consistentes.
- **Infraestrutura** (`src/infra/`) — suporte comum: configuração central, logging de três níveis, preparação de ambiente, política de retry, captura de evidências e o catálogo de XPaths.

## Estrutura de pastas

```
btime-case-cambio/
├── run_scraping.py          # ponto de entrada: coleta via Selenium
├── run_api.py               # ponto de entrada: coleta via API PTAX
├── requirements.txt
├── README.md
├── src/
│   ├── dominio/
│   │   ├── cotacao.py        # modelo padronizado da cotação
│   │   ├── validacao.py      # validação + exceção de negócio
│   │   └── periodo.py        # regra do mês anterior
│   ├── coletores/
│   │   ├── coletor_scraping.py  # fluxo Selenium no site do BCB
│   │   ├── coletor_api.py       # consulta à API PTAX
│   │   └── xpaths_bcb.py        # catálogo central de seletores
│   ├── saida/
│   │   └── escritor_csv.py   # escrita do CSV
│   └── infra/
│       ├── config.py         # toda a parametrização
│       ├── logger.py         # LogProcesso, LogErro, LogException
│       ├── ambiente.py       # cria as pastas se não existirem
│       ├── retry.py          # repetição com espera crescente
│       └── evidencia.py      # screenshot / resposta crua no erro
├── logs/                     # gerado em runtime
├── evidencias/               # gerado em runtime (prints e respostas cruas)
├── saida_csv/                # CSVs finais
└── docs/
    └── xpath_imagens/        # prints de documentação dos elementos
```

## Pré-requisitos

- **Python 3.10 ou superior**
- **Google Chrome** instalado (o driver é resolvido automaticamente pelo Selenium Manager, embutido no Selenium 4.6+ — não é preciso baixar chromedriver manualmente)
- Acesso à internet

## Instalação

Recomenda-se um ambiente virtual:

```bash
# 1. Clone o repositório
git clone <url-do-repositorio>
cd btime-case-cambio

# 2. Crie e ative um ambiente virtual
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt
```

## Como executar

Cada script é independente e roda separadamente, a partir da raiz do projeto:

```bash
# Coleta via web scraping (abre o Chrome e opera o site do BCB)
python run_scraping.py

# Coleta via API PTAX
python run_api.py
```

Ao iniciar, o robô verifica e cria as pastas necessárias automaticamente, então pode ser executado numa máquina limpa sem preparação manual.

> **Dica:** para acompanhar o Selenium visualmente (ver o navegador agindo), abra `src/infra/config.py` e altere `SELENIUM_HEADLESS = True` para `False`.

## Saída gerada

Os arquivos são gravados em `saida_csv/`, com o **mês dos dados no nome** (formato `AAAA-MM`), para manter histórico entre execuções sem sobrescrever coletas anteriores:

- `2026-07_cotacoes_scraping.csv`
- `2026-07_cotacoes_api.csv`

O prefixo `AAAA-MM` faz os arquivos se ordenarem cronologicamente sozinhos ao listar a pasta. Ambos têm as mesmas colunas, separadas por `;` (padrão do Excel brasileiro) e codificação UTF-8 com BOM (acentos abrem corretos no Excel):

| Coluna | Descrição |
|---|---|
| Moeda | Código da moeda (USD, EUR, GBP) |
| Data da Cotacao | Data a que a cotação se refere (DD/MM/AAAA) |
| Tipo | Tipo do boletim PTAX (fechamento) |
| Compra | Cotação de compra em Real |
| Venda | Cotação de venda em Real |
| Data da Coleta | Quando o robô coletou |
| Fonte | `scraping` ou `api` |

**Consistência numérica entre as fontes:** as duas fontes entregam os valores em formatos diferentes — a API PTAX usa ponto decimal e omite zeros à direita (ex.: `5.195`), enquanto o site usa vírgula e quatro casas (ex.: `5,1950`). O modelo de domínio normaliza ambos para **vírgula com quatro casas decimais**, de modo que os dois CSVs fiquem idênticos em formato e abram corretos no Excel brasileiro.

## Sistema de logs

O robô mantém **três trilhas** em `logs/`, cada uma com um propósito:

- **`LogProcesso.log`** — trilha completa e cronológica de tudo que o robô fez (a "fita" da execução, do início ao fim). Registra também os erros, para manter a história inteira em ordem.
- **`LogErro.log`** — recorte só dos **erros de negócio esperados** (tabela vazia, site fora do ar, API com status inválido). Situações previstas e tratadas de forma controlada.
- **`LogException.log`** — recorte só das **exceções inesperadas**, não previstas, que precisam de investigação.

Essa separação acelera o diagnóstico em produção: o `LogProcesso` conta a história completa, e os outros dois são atalhos direto para o problema.

## Tratamento de erros e resiliência

- **Retry com espera crescente** — falhas transitórias (rede, site momentaneamente fora do ar, limite de API) disparam novas tentativas com intervalo crescente, em vez de derrubar a execução na primeira falha.
- **Evidência no erro** — no scraping, um **screenshot** da tela é salvo em `evidencias/` no momento exato da falha (a "cena do crime"). Na API, salva-se a **resposta crua** recebida. Ambos nomeados com etapa + timestamp.
- **Validação antes de salvar** — o robô nunca gera um CSV vazio ou quebrado em silêncio; um lote inválido é registrado como erro de negócio.
- **Encerramento garantido** — o navegador é sempre fechado ao fim, mesmo em caso de erro, evitando processos órfãos.

## Detalhes técnicos do scraping

A página de histórico de cotações do BCB tem duas particularidades que o robô trata explicitamente:

- **Formulário dentro de um `iframe`** — o formulário de consulta não está no documento principal da página, mas embutido num `iframe` (o sistema `ptax_internet`). O Selenium, por padrão, só enxerga o documento principal, então o robô troca de contexto para dentro do `iframe` antes de interagir com qualquer campo, e retorna ao contexto principal a cada nova moeda.
- **Campos de data com máscara** — os campos de data aplicam formatação automática das barras. Digitar caractere a caractere faz a máscara se atropelar com o texto e embaralhar a data. Para contornar, o valor é definido diretamente via JavaScript, disparando os eventos `input` e `change` para o site reconhecer a alteração.

A tabela de resultado também varia conforme a moeda: para o dólar ela traz quatro colunas (Data, Tipo, Compra, Venda); para as demais, seis colunas (com Taxa e Paridade). Como as quatro primeiras colunas têm o mesmo significado nos dois formatos, o robô lê sempre as quatro primeiras e ignora as colunas extras de paridade — extração que funciona para todas as moedas sem ramificação de código.

## Manutenção dos seletores (XPath)

Todos os seletores do site ficam centralizados em `src/coletores/xpaths_bcb.py`. Quando o site do BCB mudar de layout, a correção é feita **nesse único arquivo**, sem tocar na lógica do coletor.

Cada elemento traz o XPath, uma descrição e o caminho de uma **imagem de documentação** (em `docs/xpath_imagens/`) com a área do elemento destacada. Essas imagens são documentação estática — ajudam o desenvolvedor de sustentação a identificar visualmente cada elemento na tela. Para adicioná-las: tire o print, destaque o elemento e salve na pasta com o nome referenciado no catálogo.
