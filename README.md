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
- [Backend API — Monitor de itens](#backend-api--monitor-de-itens)
- [Frontend](#frontend)

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

## Backend API — Monitor de itens

Além dos dois scripts de coleta em lote (CSV), o projeto tem um **backend
FastAPI** que monitora itens (moedas) ao longo do tempo: cadastro,
coleta automática periódica, coleta manual sob demanda, histórico para
gráfico e uma consulta livre por período. É a base pensada para ser
consumida por um frontend depois (hospedado no Lovable).

### Decisões técnicas e por quê

- **Só a API PTAX, sem scraping.** O backend reaproveita a mesma API oficial
  do BCB que os scripts de CSV já usam — o scraping (Selenium) resolve o
  mesmo dado de um jeito mais frágil e mais lento, sem necessidade aqui.
- **Item = qualquer moeda aceita pela PTAX**, não só USD/EUR/GBP. Como há
  uma única fonte de dados (a PTAX), o item guarda só o código da moeda;
  não há uma camada de "tipos de fonte plugáveis" porque o projeto não
  precisa disso agora — adicionar isso sem uma segunda fonte real seria
  complexidade especulativa.
- **SQLite.** Sem servidor externo, roda numa máquina limpa sem preparação
  manual (mesmo princípio dos scripts de CSV) — o arquivo fica em
  `dados/monitor.db`, criado sozinho no primeiro start.
- **Cadastro de item já faz a primeira coleta.** `POST /items` usa a mesma
  chamada tanto para validar que a moeda existe na PTAX quanto para gravar
  a primeira leitura — evita duas idas à API para o mesmo propósito.
- **Mapeamento de erros:** `404` quando o item não existe; `400` quando o
  payload é inválido ou (só na criação) a moeda não existe na PTAX; `409`
  quando a moeda já está cadastrada (ver abaixo); `502` quando a PTAX está
  fora do ar ou não responde a tempo (a coleta falhou, não o pedido do
  usuário). Nenhuma exceção do Python chega crua ao cliente — há um
  handler global que converte qualquer erro não previsto em `500` com
  mensagem genérica, registrando o detalhe no log.
- **Um item por moeda.** `POST /items` não cria um segundo item para uma
  moeda já cadastrada — devolve `409` com o item existente e quantos
  segundos faltam para a próxima coleta automática
  (`segundos_ate_proxima_coleta`, calculado a partir do `next_run_time` do
  job do agendador). O frontend usa isso para avisar o usuário e oferecer
  "coletar agora mesmo assim" no item já existente, em vez de duplicar.
- **Consulta livre (`GET /cotacoes`).** Além do agendador e da coleta
  manual por item, dá pra consultar qualquer moeda + período direto na
  PTAX sem precisar cadastrar nada antes — pensado pra uma tela
  interativa do frontend onde a pessoa escolhe moeda e intervalo de datas.
- **Autenticação real, não um login fake.** Tabela `usuarios` de verdade
  (senha com hash bcrypt, nunca texto puro) + JWT — a mesma estrutura de
  um sistema multiusuário, só que com um usuário só cadastrado (o do
  Muri). Nos projetos da btime o banco é Supabase; aqui fica em SQLite
  local de propósito, pra não gerar custo num projeto de ambientação, mas
  o desenho do auth é o mesmo que valeria lá. Todas as rotas de
  `/items`, `/cotacoes` e `/moedas` exigem `Authorization: Bearer <token>`
  — só `/auth/registrar` e `/auth/login` ficam abertos (óbvio: sem token
  ainda não tem como autenticar).
- **Alerta de variação brusca.** Em vez do endpoint de regra configurável
  que o desafio original sugere como bônus (`POST /items/{id}/alerts`),
  cada item cadastrado já vem com `variacao_percentual` calculada
  (compra: coleta mais recente vs. a anterior) em `GET /items`. O
  frontend acende um selo quando o módulo passa de
  `config.ALERTA_VARIACAO_PERCENTUAL` (padrão: 2%) — limiar pensado pra
  filtrar ruído normal do dia a dia sem deixar passar um movimento fora
  do comum, e em percentual (não R$) porque um valor fixo não faz sentido
  comparando moedas de escalas tão diferentes (Iene vs. Libra, por
  exemplo).

### Endpoints

| Método | Rota | Descrição | Autenticação |
|---|---|---|---|
| POST | `/auth/registrar` | Cria uma conta (e-mail + senha) | Não |
| POST | `/auth/login` | Autentica e devolve um JWT | Não |
| POST | `/items` | Cadastra um item (moeda) e já grava a primeira coleta | Sim |
| GET | `/items` | Lista os itens, com última coleta e variação % embutidas | Sim |
| GET | `/items/{id}/latest` | Última cotação coletada do item | Sim |
| GET | `/items/{id}/history` | Série histórica de coletas do item (gráfico) | Sim |
| POST | `/items/{id}/collect` | Força uma coleta manual imediata | Sim |
| GET | `/cotacoes?moeda=&data_inicio=&data_fim=` | Consulta livre na PTAX, sem item cadastrado | Sim |
| GET | `/moedas` | Lista as moedas que a PTAX aceita (código + nome) | Sim |

No Swagger (`/docs`), o cadeado "Authorize" aceita colar o `access_token`
devolvido pelo login (esquema Bearer simples, sem OAuth2 form).

### Agendamento

Um job em background (APScheduler) roda a cada
`config.SCHEDULER_INTERVALO_MINUTOS` (padrão: 10 minutos) e coleta a
cotação mais recente de todos os itens cadastrados, sem precisar do
endpoint manual. Falha num item não interrompe os demais.

### Como rodar

```bash
pip install -r requirements.txt
python run_backend.py
# ou: uvicorn src.api.main:app --reload
```

Depois, abrir **http://127.0.0.1:8000/docs** (Swagger).

### Como testar

```bash
pytest -v
```

Os testes usam um banco SQLite temporário isolado e mockam a chamada à
PTAX (`monkeypatch`) — não fazem requisição de rede nem tocam no banco de
desenvolvimento (`dados/monitor.db`).

### O que faria diferente com mais tempo

- `GET /items` faz uma query por item para achar a última coleta e a
  variação (N+1) — aceitável no volume de um projeto de ambientação, mas
  viraria uma query única (subquery/window function) num cenário com
  muitos itens.
- `JWT_SECRET_KEY` tem um valor padrão de desenvolvimento no `config.py`
  — precisa vir de variável de ambiente antes de qualquer deploy real.
- Endpoint de alertas configuráveis por regra (`POST /items/{id}/alerts`,
  o bônus original do desafio) e Dockerfile/docker-compose ficaram fora
  desta rodada.
- Paginação em `GET /items/{id}/history` para itens com histórico muito
  longo.
- Migrations (Alembic) em vez de `create_all()`, se o schema evoluir depois
  do primeiro deploy.
- Sem refresh token — o JWT expira em 24h (`JWT_EXPIRACAO_HORAS`) e a
  pessoa só loga de novo; suficiente pra um usuário só, não pra produção.

## Frontend

HTML/CSS/JS puro (sem build, sem framework) em `frontend/`, seguindo o
design system btime (`frontend/styles.css`, tokens `--bt-*`). Consome a
API real — nada mockado. Publicação futura no Lovable é só hospedagem: por
isso o frontend é estático, sem passo de build, e a URL do backend fica
num único lugar (`frontend/config.js`).

### Telas

- **Login** (`#/login`) — abas Entrar/Criar conta, e-mail + senha reais
  contra `/auth/login` e `/auth/registrar`. É a porta de entrada
  obrigatória: sem token válido, o roteador manda qualquer outra rota de
  volta pra cá.
- **Itens** (`#/items`) — grid dos itens cadastrados, cada card com a
  última cotação e, se a variação passou do limiar, um selo ▲/▼ de
  alerta. Botão "+ Novo item" abre um modal de cadastro, com um seletor
  de moeda populado via `GET /moedas` (em vez de digitar o código de
  cabeça) — sugere o nome do item automaticamente ao escolher a moeda.
- **Detalhe do item** (`#/items/{id}`) — estatísticas da última coleta
  (com o mesmo selo de alerta ao lado do nome), botão "Coletar agora", e
  abas Gráfico/Tabela para o histórico.
- **Consulta livre** (`#/consulta`) — seletor de moeda (só as já
  cadastradas, vindo de `GET /items`) + período, batendo direto no
  `GET /cotacoes` ao vivo em vez de só reaproveitar o que o agendador já
  coletou.

O gráfico de histórico é SVG desenhado à mão (sem biblioteca externa):
duas séries (compra/venda), crosshair com tooltip no hover, marcador de
fim de linha e grade horizontal discreta — mantém o projeto sem
dependência de build ou CDN.

### Autenticação no frontend

O token JWT fica em `localStorage` (`frontend/app.js`, `CHAVE_TOKEN`) e
`apiRequest()` anexa `Authorization: Bearer <token>` em toda chamada
automaticamente. Se qualquer resposta vier `401` (token expirado,
inválido, ou removido manualmente), o token é limpo e a pessoa é jogada
de volta pra `#/login` — não precisa tratar isso em cada tela
individualmente. Botão "Sair" na navbar limpa o token na hora.

### Como rodar

Backend e frontend rodam em processos/portas separados (o frontend chama
a API via `fetch`, então precisa dos dois no ar):

```bash
# terminal 1
python run_backend.py

# terminal 2
python run_frontend.py
```

Depois, abrir **http://127.0.0.1:5500**. Abrir `frontend/index.html`
direto como arquivo (`file://`) não funciona — o navegador bloqueia o
`fetch` por CORS nesse esquema; por isso existe o `run_frontend.py`.

Se o backend rodar em outra porta/host, ajustar `API_BASE_URL` em
`frontend/config.js`.
