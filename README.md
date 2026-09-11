# btime-case-cambio

Monitor de cotações de câmbio (PTAX do Banco Central) com backend FastAPI, frontend próprio e autenticação real — cadastro de moedas, coleta automática periódica, alerta de variação brusca, consulta livre por período, comparação e conversão entre moedas, um dashboard com indicadores de mercado, e uma tela de login. Nasceu como um case técnico de RPA (coleta em CSV via scraping e via API) e foi evoluído, num projeto de ambientação na btime, para o sistema completo descrito aqui.

## Sumário

- [Visão geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Estrutura de pastas](#estrutura-de-pastas)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Como rodar o backend](#como-rodar-o-backend)
- [Como rodar o frontend](#como-rodar-o-frontend)
- [Endpoints da API](#endpoints-da-api)
- [Decisões técnicas e por quê](#decisões-técnicas-e-por-quê)
- [Sistema de logs](#sistema-de-logs)
- [Tratamento de erros e resiliência](#tratamento-de-erros-e-resiliência)
- [Testes automatizados](#testes-automatizados)
- [O que faria diferente com mais tempo](#o-que-faria-diferente-com-mais-tempo)
- [Os scripts originais de coleta em CSV](#os-scripts-originais-de-coleta-em-csv)

## Visão geral

O repositório tem duas partes:

1. **O sistema principal** — backend (FastAPI + SQLite) e frontend (HTML/CSS/JS puro) que monitoram moedas ao longo do tempo: cadastro de itens, coleta automática a cada N minutos, coleta manual, histórico com gráfico, consulta livre por período, comparação e conversão entre moedas, um dashboard com indicadores de mercado, alerta visual de variação brusca, e login com usuário/senha reais. É o que roda no dia a dia — ver [Como rodar o backend](#como-rodar-o-backend) e [Como rodar o frontend](#como-rodar-o-frontend).
2. **Os scripts originais de coleta em CSV** (`run_scraping.py` e `run_api.py`) — o case de RPA que deu origem ao projeto: duas técnicas independentes (Selenium e API) que coletam o mês anterior de USD/EUR/GBP e gravam em CSV. Continuam funcionando exatamente como antes; a camada que consultam (`src/coletores/ptax_cliente.py`) é a mesma que o backend usa. Detalhes em [Os scripts originais de coleta em CSV](#os-scripts-originais-de-coleta-em-csv).

## Arquitetura

```
                 Frontend (HTML/CSS/JS, frontend/)
                              │  fetch + Authorization: Bearer <JWT>
                              ▼
   ┌────────────────────────────────────────────────────────────────────┐
   │                        API (FastAPI, src/api/)                     │
   │  main.py · routers: auth · itens · cotacoes · moedas · conversoes ·│
   │  agendador · dashboard                                             │
   │  schemas (Pydantic) · dependencias (get_db, obter_usuario_atual)   │
   └──────────┬───────────────────────────────────────┬─────────────────┘
              │                                        │
              ▼                                        ▼
   ┌────────────────────┐                  ┌───────────────────────┐
   │  Auth (src/auth/)    │                  │  Agendador (src/agendador/) │
   │  hash de senha       │                  │  coleta periódica via     │
   │  emissão/leitura JWT │                  │  APScheduler               │
   └──────────────────────┘                  └──────────┬────────────────┘
                                                          │
              ┌───────────────────────────────────────────┘
              ▼
   ┌──────────────────────┐        ┌───────────────────────────────┐
   │  Coletores             │──────▶│  Persistência (src/persistencia/) │
   │  (src/coletores/)       │       │  SQLAlchemy: Item, Coleta, Usuario │
   │  ptax_cliente (comum)   │       │  SQLite (dados/monitor.db)          │
   │  coletor_item (backend) │       └───────────────────────────────┘
   │  coletor_api (CSV)      │
   │  coletor_scraping (CSV) │
   └───────────┬──────────────┘
               │ usa (só o fluxo CSV)
               ▼
   ┌──────────────────────────────┐        ┌──────────────────────┐
   │  Domínio (src/dominio/)         │──────▶│  Saída CSV (src/saida/) │
   │  Cotacao · validação · período  │        └──────────────────────┘
   └──────────────────────────────┘

   Infraestrutura comum a tudo (src/infra/): config · logger (3 níveis) ·
   ambiente · retry · evidência · catálogo de XPaths
```

**Regra central:** cada camada conhece só o necessário. O backend novo (auth, persistência, agendador, API) e o fluxo antigo de CSV (domínio, saída) compartilham a mesma infraestrutura e o mesmo cliente PTAX (`ptax_cliente.py`), mas não se misturam — trocar como o backend guarda dado (SQLite → outra coisa) não afeta o CSV, e vice-versa.

- **`src/dominio/`** — núcleo do fluxo de CSV: o modelo `Cotacao`, a validação, e a regra do "mês anterior". Não é usado pelo backend (que guarda `float` puro em vez do formato de string pensado pro Excel — ver [decisões](#decisões-técnicas-e-por-quê)).
- **`src/coletores/`** — todas as fontes de dado. `ptax_cliente.py` é o cliente HTTP compartilhado com a PTAX (retry, tratamento de erro, evidência); `coletor_api.py` e `coletor_scraping.py` alimentam o fluxo de CSV; `coletor_item.py` alimenta o backend (cotação mais recente de 1 moeda, usada tanto pelo agendador quanto pelas rotas de item).
- **`src/saida/`** — escreve o CSV do fluxo legado.
- **`src/persistencia/`** — modelos SQLAlchemy (`Item`, `Coleta`, `Usuario`) e o repositório (única camada que faz query/gravação no banco).
- **`src/auth/`** — hash de senha (bcrypt) e emissão/verificação de JWT. Não sabe nada de HTTP.
- **`src/agendador/`** — o job do APScheduler que coleta todos os itens periodicamente.
- **`src/api/`** — a camada FastAPI: `main.py` monta a app e os handlers globais de erro; `routers/` tem uma rota por recurso (`auth`, `itens`, `cotacoes`, `moedas`, `conversoes`, `agendador`, `dashboard`); `dependencias.py` tem o que é injetado nas rotas (sessão de banco, usuário autenticado); `schemas.py` define os formatos de entrada/saída.
- **`src/infra/`** — suporte comum a tudo: configuração central (`config.py`), logging de três níveis, preparação de ambiente, política de retry, captura de evidências e o catálogo de XPaths do scraping.
- **`frontend/`** — a interface (ver [Como rodar o frontend](#como-rodar-o-frontend)).

## Estrutura de pastas

```
btime-case-cambio/
├── run_backend.py            # sobe a API (FastAPI/Uvicorn)
├── run_frontend.py           # serve o frontend estático
├── criar_usuario.py          # cria uma conta de acesso (ação administrativa)
├── run_scraping.py           # fluxo legado: coleta via Selenium -> CSV
├── run_api.py                # fluxo legado: coleta via API PTAX -> CSV
├── requirements.txt
├── README.md
├── frontend/
│   ├── index.html            # shell da SPA (login, dashboard, itens, detalhe,
│   │                          #   consulta livre, comparar moedas, conversão)
│   ├── app.js                # roteamento, cliente da API, gráficos SVG, seletor de data
│   ├── styles.css             # design system btime + estilos do app
│   └── config.js              # URL base da API
├── src/
│   ├── api/
│   │   ├── main.py            # app FastAPI, lifespan, handlers de erro
│   │   ├── schemas.py          # modelos Pydantic de entrada/saída
│   │   ├── dependencias.py     # get_db, obter_usuario_atual
│   │   └── routers/
│   │       ├── auth.py          # POST /auth/login
│   │       ├── itens.py         # /items (cadastro, listagem, coleta...)
│   │       ├── cotacoes.py      # GET /cotacoes (consulta livre)
│   │       ├── moedas.py        # GET /moedas
│   │       ├── conversoes.py    # POST/GET /conversoes (conversão + histórico)
│   │       ├── agendador.py     # GET /agendador/proxima-coleta (relógio do menu lateral)
│   │       └── dashboard.py     # GET /dashboard/* (resumo, ranking, mercado, conversões)
│   ├── auth/
│   │   └── seguranca.py        # hash de senha (bcrypt) + JWT
│   ├── agendador/
│   │   └── scheduler.py        # coleta periódica (APScheduler)
│   ├── persistencia/
│   │   ├── database.py         # engine/sessão SQLAlchemy
│   │   ├── modelos.py           # Item, Coleta, Usuario
│   │   └── repositorio.py       # única camada que fala com o banco
│   ├── dominio/                 # (fluxo legado de CSV)
│   │   ├── cotacao.py
│   │   ├── validacao.py
│   │   └── periodo.py
│   ├── coletores/
│   │   ├── ptax_cliente.py      # cliente HTTP compartilhado com a PTAX
│   │   ├── coletor_item.py       # cotação mais recente de 1 moeda (backend)
│   │   ├── coletor_api.py        # coleta do mês anterior (fluxo CSV)
│   │   ├── coletor_scraping.py   # fluxo Selenium (fluxo CSV)
│   │   └── xpaths_bcb.py         # catálogo central de seletores do site
│   ├── saida/
│   │   └── escritor_csv.py       # (fluxo legado de CSV)
│   └── infra/
│       ├── config.py             # toda a parametrização
│       ├── logger.py             # LogProcesso, LogErro, LogException
│       ├── ambiente.py           # cria as pastas se não existirem
│       ├── retry.py              # repetição com espera crescente
│       └── evidencia.py          # screenshot / resposta crua no erro
├── tests/
│   ├── conftest.py               # fixtures (banco isolado, bypass de auth)
│   ├── test_api_itens.py         # itens, cotações, moedas, conversões, agendador
│   ├── test_api_dashboard.py     # resumo, ranking, mercado, conversões-resumo
│   └── test_auth.py              # login e proteção por token
├── dados/                        # gerado em runtime (monitor.db)
├── logs/                         # gerado em runtime
├── evidencias/                   # gerado em runtime (prints e respostas cruas)
├── saida_csv/                    # CSVs finais (fluxo legado)
└── docs/
    └── xpath_imagens/            # prints de documentação dos elementos
```

## Pré-requisitos

- **Python 3.10 ou superior**
- **Google Chrome** instalado — só necessário para o fluxo legado de scraping (`run_scraping.py`); o backend e o frontend não precisam
- Acesso à internet (todas as fontes de dado vêm da API pública da PTAX)

## Instalação

```bash
git clone <url-do-repositorio>
cd btime-case-cambio

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
```

## Como rodar o backend

```bash
python criar_usuario.py seu@email.com suasenha   # só na primeira vez (ver decisões abaixo)
python run_backend.py
# ou: uvicorn src.api.main:app --reload
```

Depois, abrir **http://127.0.0.1:8000/docs** (Swagger). No cadeado "Authorize", cole o `access_token` devolvido por `POST /auth/login` — as demais rotas exigem esse token.

Ao iniciar, o backend garante que as pastas/tabelas necessárias existam (`dados/monitor.db`, criado sozinho), sobe o agendador de coleta automática, e nunca deixa uma exceção crua chegar ao cliente.

## Como rodar o frontend

Backend e frontend rodam em processos/portas separados (o frontend chama a API via `fetch`, então precisa dos dois no ar):

```bash
# terminal 1
python run_backend.py

# terminal 2
python run_frontend.py
```

Depois, abrir **http://127.0.0.1:5500**. Abrir `frontend/index.html` direto como arquivo (`file://`) não funciona — o navegador bloqueia o `fetch` por CORS nesse esquema; por isso existe o `run_frontend.py`. Se o backend rodar em outra porta/host, ajustar `API_BASE_URL` em `frontend/config.js`.

**Telas** (menu lateral com ícones, a conta logada — e-mail decodificado do próprio JWT —, um relógio de contagem regressiva até a próxima coleta automática, e "Sair" no rodapé; em telas estreitas vira um menu retrátil):

- **Login** (`#/login`) — e-mail + senha reais contra `/auth/login`. Sem cadastro na tela (ver [decisões](#decisões-técnicas-e-por-quê)) — é a porta de entrada obrigatória: sem token válido, o roteador manda qualquer outra rota de volta pra cá. O token JWT fica em `localStorage`; qualquer resposta `401` limpa o token e volta pro login automaticamente, e o botão "Sair" faz o mesmo na hora.
- **Dashboard** (`#/dashboard`) — primeira tela após o login (e primeiro item do menu). Cards de resumo (itens monitorados, quantos com alerta de variação hoje, conversões feitas); ranking das maiores altas e baixas dos últimos 3 meses e a maior volatilidade (maior salto diário) num recorte de moedas relevantes (`config.MOEDAS_DASHBOARD_RANKING`); variação média por dia da semana; o par de moedas mais convertido pelo usuário; e a evolução (normalizada em %) de todas as moedas que ele já monitora no mês corrente.
- **Itens** (`#/items`) — grid dos itens cadastrados, cada card com a última cotação e, se a variação passou do limiar, um selo ▲/▼ de alerta. Botão "+ Novo item" abre um modal de cadastro, com um seletor de moeda populado via `GET /moedas` (qualquer moeda aceita pela PTAX) — sugere o nome do item automaticamente ao escolher a moeda.
- **Detalhe do item** (`#/items/{id}`) — estatísticas da última coleta (com o mesmo selo de alerta ao lado do nome), botão "Coletar agora", e abas Gráfico/Tabela de **monitoramento em tempo real**: em vez de só reaproveitar o log de coletas do agendador, busca ao vivo no `GET /cotacoes` o mês corrente inteiro (do dia 1 até hoje); nos 3 primeiros dias do mês, estende pra trás até o início do mês anterior, pra nunca mostrar um gráfico praticamente vazio. O gráfico é SVG desenhado à mão (sem biblioteca externa): duas séries (compra/venda), crosshair com tooltip no hover, marcador de fim de linha e grade horizontal discreta.
- **Consulta livre** (`#/consulta`) — seletor de moeda (qualquer uma da PTAX, vindo de `GET /moedas`) + período, batendo direto no `GET /cotacoes` ao vivo. Um período maior que `config.JANELA_MAXIMA_CONSULTA_DIAS` é barrado no próprio frontend com um aviso informativo (não um erro), antes de chamar a API. A última consulta feita (moeda, período e resultado) fica salva em `localStorage` e reaparece sozinha ao voltar nessa tela — inclusive depois de recarregar a página.
- **Comparar moedas** (`#/comparar`) — escolhe até 6 moedas quaisquer da PTAX (não só as cadastradas) + período (mesmo aviso de janela máxima da Consulta livre), e compara num único gráfico. Como as escalas são muito diferentes entre si (ex: Iene ~0,03 vs Libra ~6,5), o gráfico normaliza cada série em % de variação desde o primeiro ponto do período, em vez de plotar os valores absolutos; a tabela ao lado traz os valores reais (compra/venda atuais e variação % no período).
- **Conversão** (`#/conversao`) — converte um valor entre duas moedas quaisquer (ou BRL) pela cotação PTAX mais recente, batendo em `POST /conversoes`. Cada conversão feita é gravada e aparece no histórico da tela (`GET /conversoes`) — é só um cálculo registrado, não uma transação financeira real.

## Endpoints da API

| Método | Rota | Descrição | Autenticação |
|---|---|---|---|
| POST | `/auth/login` | Autentica (e-mail + senha) e devolve um JWT | Não |
| POST | `/items` | Cadastra um item (moeda) e já grava a primeira coleta | Sim |
| GET | `/items` | Lista os itens, com última coleta e variação % embutidas | Sim |
| GET | `/items/{id}/latest` | Última cotação coletada do item | Sim |
| GET | `/items/{id}/history` | Série histórica de coletas do item (gráfico) | Sim |
| POST | `/items/{id}/collect` | Força uma coleta manual imediata | Sim |
| GET | `/cotacoes?moeda=&data_inicio=&data_fim=` | Consulta livre na PTAX, sem item cadastrado | Sim |
| GET | `/moedas` | Lista as moedas que a PTAX aceita (código + nome) | Sim |
| POST | `/conversoes` | Converte um valor entre duas moedas (ou BRL) pela cotação mais recente e grava no histórico | Sim |
| GET | `/conversoes` | Histórico de conversões do usuário logado | Sim |
| GET | `/agendador/proxima-coleta` | Segundos até a próxima coleta automática (relógio do menu lateral) | Sim |
| GET | `/dashboard/resumo` | Total de itens, quantos com alerta ativo hoje e total de conversões feitas | Sim |
| GET | `/dashboard/ranking-variacao?dias=` | Maiores altas/baixas num recorte de moedas relevantes, do início ao fim do período (padrão: 90 dias) | Sim |
| GET | `/dashboard/mercado?dias=` | Volatilidade (maior variação diária de cada moeda) e variação média por dia da semana | Sim |
| GET | `/dashboard/conversoes-resumo` | Pares de moeda mais convertidos pelo usuário, com quantidade e percentual | Sim |

## Decisões técnicas e por quê

- **Só a API PTAX, sem scraping, no backend novo.** O backend reaproveita a mesma API oficial do BCB que o fluxo de CSV já usava — o scraping (Selenium) resolve o mesmo dado de um jeito mais frágil e mais lento, sem necessidade aqui. O scraping continua existindo só no script legado (`run_scraping.py`), como demonstração da segunda técnica.
- **Item = qualquer moeda aceita pela PTAX**, não só USD/EUR/GBP. Como há uma única fonte de dados, o item guarda só o código da moeda; não há uma camada de "tipos de fonte plugáveis" porque o projeto não precisa disso agora — adicionar isso sem uma segunda fonte real seria complexidade especulativa.
- **Um item por moeda.** `POST /items` não cria um segundo item para uma moeda já cadastrada — devolve `409` com o item existente e quantos segundos faltam para a próxima coleta automática (`segundos_ate_proxima_coleta`, calculado a partir do `next_run_time` do job do agendador). O frontend usa isso para avisar o usuário e oferecer "coletar agora mesmo assim" no item já existente, em vez de duplicar.
- **Cadastro de item já faz a primeira coleta.** `POST /items` usa a mesma chamada tanto para validar que a moeda existe na PTAX quanto para gravar a primeira leitura — evita duas idas à API para o mesmo propósito.
- **SQLite.** Sem servidor externo, roda numa máquina limpa sem preparação manual — o arquivo fica em `dados/monitor.db`, criado sozinho no primeiro start. Não reflete uma preferência de arquitetura: nos projetos reais da btime o banco é Supabase, mas provisionar isso custaria dinheiro por um projeto de ambientação, então o desenho (tabelas, relações, hash de senha, JWT) foi feito para ser o mesmo que valeria com Supabase.
- **Autenticação real, não um login fake.** Tabela `usuarios` de verdade (senha com hash bcrypt, nunca texto puro) + JWT — a mesma estrutura de um sistema multiusuário, mesmo que só exista uma conta cadastrada hoje. Todas as rotas de negócio (`/items`, `/cotacoes`, `/moedas`, `/conversoes`, `/agendador`, `/dashboard`) exigem `Authorization: Bearer <token>`; só `/auth/login` fica aberto (sem token ainda não tem como autenticar).
- **Sem cadastro público.** Uma API que vai pro cliente não deveria ter uma tela de "criar conta" livre — conceder acesso é uma ação administrativa. Contas são criadas com `python criar_usuario.py <email> <senha>`, rodado localmente por quem administra o sistema (o equivalente, aqui, a criar o usuário direto no painel do Supabase num projeto real).
- **Alerta de variação brusca.** Em vez do endpoint de regra configurável que o desafio original sugere como bônus (`POST /items/{id}/alerts`), cada item cadastrado já vem com `variacao_percentual` calculada (compra: coleta mais recente vs. a anterior) em `GET /items`. O frontend acende um selo quando o módulo passa de `config.ALERTA_VARIACAO_PERCENTUAL` (padrão: 2%) — limiar pensado pra filtrar ruído normal do dia a dia sem deixar passar um movimento fora do comum, e em percentual (não R$) porque um valor fixo não faz sentido comparando moedas de escalas tão diferentes (Iene vs. Libra, por exemplo).
- **Consulta livre (`GET /cotacoes`).** Além do agendador e da coleta manual por item, dá pra consultar qualquer moeda + período direto na PTAX sem precisar de um item já ter sido coletado nesse intervalo — pensado pra uma tela interativa onde a pessoa escolhe moeda e datas. O seletor de moeda do frontend lista todas as moedas da PTAX (`GET /moedas`), não só as já cadastradas como item.
- **Mapeamento de erros:** `404` quando o item não existe; `400` quando o payload é inválido ou (só na criação) a moeda não existe na PTAX; `409` quando a moeda já está cadastrada; `502` quando a PTAX está fora do ar ou não responde a tempo (a coleta falhou, não o pedido do usuário); `401` quando falta token válido. Nenhuma exceção do Python chega crua ao cliente — um handler global converte qualquer erro não previsto em `500` com mensagem genérica, registrando o detalhe no log.
- **Conversão pela taxa média (compra+venda)/2.** `POST /conversoes` não escolhe a ponta de compra ou de venda do banco — usaria uma direção arbitrária num conversor genérico. Moedas estrangeiras sempre passam pelo Real como ponte (`valor_origem_em_reais / taxa_destino`); BRL entra como taxa fixa 1.0, sem chamar a PTAX (que só lista moedas estrangeiras).
- **Dashboard com um recorte de moedas, não a lista inteira da PTAX.** `GET /dashboard/ranking-variacao` e `GET /dashboard/mercado` fazem uma chamada à PTAX por moeda — rodar isso pras ~200 moedas da PTAX deixaria o dashboard lento e misturaria moeda exótica/pouco negociada (com histórico incompleto) no meio do resultado. `config.MOEDAS_DASHBOARD_RANKING` fixa um recorte de ~15 moedas relevantes; uma moeda que falhar na PTAX (ou não tiver boletim suficiente) é simplesmente omitida do resultado, sem derrubar o dashboard inteiro.
- **Limite de período avisado no frontend antes de chamar a API.** `config.JANELA_MAXIMA_CONSULTA_DIAS` é validado no backend (`400`) e também checado no frontend antes do `fetch`, em Consulta livre e Comparar moedas — evita a viagem à API só pra devolver um erro previsível, e a mensagem aparece como aviso informativo, não como "Erro".
- **Seletor de data próprio, não o `<input type="date">` nativo.** O calendário nativo do navegador não dá pra estilizar (some do tema escuro do design system). O componente em `app.js` guarda o valor num `<input type="hidden">` com o mesmo id de sempre — o resto do código continua só lendo `.value` — e desenha um calendário próprio (mês, grade de dias, dia atual/selecionado) com os tokens `--bt-*`.
- **Frontend estático, sem build.** HTML/CSS/JS puro em `frontend/`, seguindo o design system btime (tokens `--bt-*` em `styles.css`). Publicação futura no Lovable é só hospedagem — por isso não há passo de build nem framework, e a URL do backend fica num único lugar (`frontend/config.js`).
- **Gráfico sem biblioteca externa.** O histórico é desenhado como SVG à mão (duas séries, crosshair, tooltip no hover) em vez de importar uma lib de gráficos via CDN — mantém o frontend sem dependência externa nenhuma.
- **Coletores e domínio do fluxo legado, intocados.** `src/dominio/` normaliza os valores pra string com vírgula e 4 casas (pensado pro CSV abrir certo no Excel brasileiro); o backend guarda `float` puro (o consumidor é JSON/gráfico, não uma planilha) — por isso o backend não reaproveita o modelo `Cotacao`, só o cliente HTTP da PTAX (`ptax_cliente.py`).

## Sistema de logs

O backend e os scripts de CSV compartilham o mesmo sistema de logging, com **três trilhas** em `logs/`:

- **`LogProcesso.log`** — trilha completa e cronológica de tudo que foi feito (a "fita" da execução, do início ao fim). Registra também os erros, para manter a história inteira em ordem.
- **`LogErro.log`** — recorte só dos **erros de negócio esperados** (moeda sem cotação, site fora do ar, API com status inválido). Situações previstas e tratadas de forma controlada.
- **`LogException.log`** — recorte só das **exceções inesperadas**, não previstas, que precisam de investigação.

Essa separação acelera o diagnóstico: o `LogProcesso` conta a história completa, e os outros dois são atalhos direto para o problema.

## Tratamento de erros e resiliência

- **Retry com espera crescente** — falhas transitórias (rede, PTAX momentaneamente fora do ar) disparam novas tentativas com intervalo crescente, em vez de derrubar a execução na primeira falha. Usado tanto pelo backend quanto pelos scripts de CSV.
- **Evidência no erro** — no scraping, um screenshot da tela é salvo em `evidencias/` no momento da falha; na API, salva-se a resposta crua recebida. Ambos nomeados com etapa + timestamp.
- **Validação antes de salvar** — o fluxo de CSV nunca gera um arquivo vazio ou quebrado em silêncio; um lote inválido é registrado como erro de negócio. O backend, do mesmo jeito, nunca cria um item ou uma coleta a partir de um resultado vazio/inválido da PTAX.
- **Encerramento garantido** — no scraping, o navegador é sempre fechado ao fim, mesmo em caso de erro, evitando processos órfãos.

## Testes automatizados

```bash
pytest -v
```

Cada teste ganha um banco SQLite temporário isolado (não toca em `dados/monitor.db`) e mocka a chamada à PTAX — não faz requisição de rede. Dois grupos de fixtures em `tests/conftest.py`:

- `client` — autenticação "bypassada" (usuário fake injetado via `dependency_overrides`), usada pelos testes de regra de negócio (`test_api_itens.py`, `test_api_dashboard.py`), que não são sobre autenticação em si.
- `client_real_auth` / `criar_usuario_teste` — sem bypass, usadas por `test_auth.py` pra exercitar o fluxo real de login e a proteção das rotas por token.

## O que faria diferente com mais tempo

- `GET /items` faz uma query por item para achar a última coleta e a variação (N+1) — aceitável no volume de um projeto de ambientação, mas viraria uma query única (subquery/window function) num cenário com muitos itens.
- `JWT_SECRET_KEY` tem um valor padrão de desenvolvimento no `config.py` — precisa vir de variável de ambiente antes de qualquer deploy real.
- Sem refresh token — o JWT expira em 24h (`JWT_EXPIRACAO_HORAS`) e a pessoa só loga de novo; suficiente pra um usuário só, não pra produção.
- Endpoint de alertas configuráveis por regra (`POST /items/{id}/alerts`, o bônus original do desafio) e Dockerfile/docker-compose ficaram fora do escopo até agora.
- Paginação em `GET /items/{id}/history` para itens com histórico muito longo.
- Migrations (Alembic) em vez de `create_all()`, se o schema evoluir depois do primeiro deploy real (com Supabase, por exemplo).
- `GET /dashboard/ranking-variacao` e `/mercado` chamam a PTAX uma moeda por vez, em sequência — pra ~15 moedas ainda responde em poucos segundos, mas paralelizar essas chamadas (ex.: `ThreadPoolExecutor`, já que `requests` é síncrono) deixaria o dashboard mais rápido.

## Os scripts originais de coleta em CSV

`run_scraping.py` e `run_api.py` são os dois scripts independentes do case de RPA original: resolvem o mesmo problema (cotação PTAX de USD/EUR/GBP do mês civil anterior) por caminhos diferentes, e produzem um CSV de estrutura idêntica.

```bash
# Coleta via web scraping (abre o Chrome e opera o site do BCB)
python run_scraping.py

# Coleta via API PTAX
python run_api.py
```

> **Dica:** para acompanhar o Selenium visualmente, abra `src/infra/config.py` e altere `SELENIUM_HEADLESS = True` para `False`.

Os arquivos são gravados em `saida_csv/`, com o mês dos dados no nome (`AAAA-MM_cotacoes_scraping.csv` / `AAAA-MM_cotacoes_api.csv`), separados por `;` e em UTF-8 com BOM (abrem certo no Excel brasileiro):

| Coluna | Descrição |
|---|---|
| Moeda | Código da moeda (USD, EUR, GBP) |
| Data da Cotacao | Data a que a cotação se refere (DD/MM/AAAA) |
| Tipo | Tipo do boletim PTAX (fechamento) |
| Compra | Cotação de compra em Real |
| Venda | Cotação de venda em Real |
| Data da Coleta | Quando o robô coletou |
| Fonte | `scraping` ou `api` |

**Consistência numérica entre as fontes:** a API PTAX usa ponto decimal e omite zeros à direita (ex.: `5.195`), enquanto o site usa vírgula e quatro casas (ex.: `5,1950`). O modelo de domínio (`src/dominio/cotacao.py`) normaliza ambos para vírgula com quatro casas decimais, de modo que os dois CSVs fiquem idênticos em formato.

**Detalhes técnicos do scraping:** o formulário da página de histórico de cotações do BCB está dentro de um `iframe` (`ptax_internet`) — o robô troca de contexto antes de interagir com qualquer campo. Os campos de data têm máscara automática, então o valor é definido via JavaScript (evitando a máscara embaralhar o texto digitado caractere a caractere). A tabela de resultado varia de 4 colunas (dólar) a 6 colunas (demais moedas, com Taxa e Paridade); o robô sempre lê as 4 primeiras, que têm o mesmo significado nos dois formatos.

**Manutenção dos seletores (XPath):** todos ficam centralizados em `src/coletores/xpaths_bcb.py`. Quando o site do BCB mudar de layout, a correção é feita nesse único arquivo. Cada elemento traz o XPath, uma descrição e uma imagem de documentação em `docs/xpath_imagens/` com a área destacada.
