// Configuração do frontend. Único lugar que muda ao trocar de ambiente
// (dev local -> produção): a URL base do backend FastAPI.
const API_BASE_URL = "http://127.0.0.1:8000";

// Variação (compra) entre a coleta mais recente e a anterior que acende o
// selo de alta/queda no card e no detalhe do item. Tem que ficar igual ao
// config.ALERTA_VARIACAO_PERCENTUAL do backend (src/infra/config.py) - é só
// um limiar de exibição, o backend já manda o valor calculado pronto.
const ALERTA_VARIACAO_PERCENTUAL = 2.0;

// Maior período (em dias) aceito nas consultas por intervalo (consulta livre
// e comparar moedas). Tem que ficar igual ao config.JANELA_MAXIMA_CONSULTA_DIAS
// do backend (src/infra/config.py) - usado aqui só pra avisar o usuário antes
// de bater na API, em vez de deixar o backend devolver erro.
const JANELA_MAXIMA_CONSULTA_DIAS = 90;
