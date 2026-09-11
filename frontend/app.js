"use strict";

/* ==========================================================================
   Cliente da API
   ========================================================================== */

// Erro de API: guarda o status e o "detail" cru (string ou objeto), pra
// quem chamou decidir como tratar - por exemplo, o 409 de moeda duplicada
// vem com um objeto estruturado, não só uma mensagem.
class ApiError extends Error {
  constructor(mensagem, status, detalhe) {
    super(mensagem);
    this.status = status;
    this.detalhe = detalhe;
  }
}

const CHAVE_TOKEN = "btime_monitor_token";

function obterToken() {
  return localStorage.getItem(CHAVE_TOKEN);
}
function salvarToken(token) {
  localStorage.setItem(CHAVE_TOKEN, token);
}
function limparToken() {
  localStorage.removeItem(CHAVE_TOKEN);
}
function estaAutenticado() {
  return !!obterToken();
}

async function apiRequest(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = obterToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const resposta = await fetch(`${API_BASE_URL}${path}`, { headers, ...options });

  let corpo = null;
  try {
    corpo = await resposta.json();
  } catch (erro) {
    corpo = null;
  }

  if (!resposta.ok) {
    // Sessão expirou ou token inválido: só faz sentido "deslogar" pra rotas
    // protegidas - login/registrar já devolvem 401 pra credencial errada,
    // e isso não é sessão expirando.
    if (resposta.status === 401 && !path.startsWith("/auth/")) {
      limparToken();
      window.location.hash = "#/login";
    }

    const detalhe = corpo && corpo.detail !== undefined ? corpo.detail : `Erro ${resposta.status} ao falar com a API.`;
    const mensagem = typeof detalhe === "string" ? detalhe : (detalhe && detalhe.mensagem) || `Erro ${resposta.status}`;
    throw new ApiError(mensagem, resposta.status, detalhe);
  }
  return corpo;
}

const api = {
  listarItens: () => apiRequest("/items"),
  criarItem: (payload) => apiRequest("/items", { method: "POST", body: JSON.stringify(payload) }),
  ultimaCotacao: (id) => apiRequest(`/items/${id}/latest`),
  historico: (id) => apiRequest(`/items/${id}/history`),
  coletarAgora: (id) => apiRequest(`/items/${id}/collect`, { method: "POST" }),
  consultaLivre: (moeda, dataInicio, dataFim) =>
    apiRequest(`/cotacoes?moeda=${encodeURIComponent(moeda)}&data_inicio=${dataInicio}&data_fim=${dataFim}`),
  listarMoedas: () => apiRequest("/moedas"),
  login: (email, senha) => apiRequest("/auth/login", { method: "POST", body: JSON.stringify({ email, senha }) }),
  criarConversao: (payload) => apiRequest("/conversoes", { method: "POST", body: JSON.stringify(payload) }),
  listarConversoes: () => apiRequest("/conversoes"),
  proximaColeta: () => apiRequest("/agendador/proxima-coleta"),
  dashboardResumo: () => apiRequest("/dashboard/resumo"),
  dashboardRanking: (dias) => apiRequest(`/dashboard/ranking-variacao?dias=${dias}`),
  dashboardMercado: (dias) => apiRequest(`/dashboard/mercado?dias=${dias}`),
  dashboardConversoesResumo: () => apiRequest("/dashboard/conversoes-resumo"),
};

/* ==========================================================================
   Relógio de contagem regressiva até a próxima coleta automática (agendador)
   ========================================================================== */

let segundosAteProximaColeta = null;
let intervaloRelogioColeta = null;

function renderRelogioProximaColeta() {
  const el = document.getElementById("sidebar-proxima-coleta");
  if (!el) return;

  if (segundosAteProximaColeta === null) {
    el.textContent = "—";
    return;
  }

  const minutos = Math.floor(segundosAteProximaColeta / 60);
  const segundos = segundosAteProximaColeta % 60;
  el.textContent = `${String(minutos).padStart(2, "0")}:${String(segundos).padStart(2, "0")}`;
}

async function sincronizarProximaColeta() {
  try {
    const info = await api.proximaColeta();
    segundosAteProximaColeta = info.segundos_ate_proxima_coleta;
  } catch (erro) {
    segundosAteProximaColeta = null;
  }
  renderRelogioProximaColeta();
}

function iniciarRelogioProximaColeta() {
  if (intervaloRelogioColeta) return; // já iniciado

  sincronizarProximaColeta();
  intervaloRelogioColeta = setInterval(() => {
    if (segundosAteProximaColeta === null || segundosAteProximaColeta <= 0) {
      sincronizarProximaColeta(); // reconsulta o servidor (a coleta deve ter rodado)
      return;
    }
    segundosAteProximaColeta -= 1;
    renderRelogioProximaColeta();
  }, 1000);
}

function pararRelogioProximaColeta() {
  if (intervaloRelogioColeta) {
    clearInterval(intervaloRelogioColeta);
    intervaloRelogioColeta = null;
  }
  segundosAteProximaColeta = null;
  renderRelogioProximaColeta();
}

/* ==========================================================================
   Conta logada (decodificada do JWT já salvo - sem round-trip extra à API)
   ========================================================================== */

function decodificarPayloadToken(token) {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join("")
    );
    return JSON.parse(json);
  } catch (erro) {
    return null;
  }
}

function atualizarContaLogada() {
  const emailEl = document.getElementById("sidebar-conta-email");
  const inicialEl = document.getElementById("sidebar-conta-inicial");
  const token = obterToken();
  const payload = token ? decodificarPayloadToken(token) : null;
  const email = payload && payload.email ? payload.email : null;

  emailEl.textContent = email || "—";
  emailEl.title = email || "";
  inicialEl.textContent = email ? email.charAt(0).toUpperCase() : "?";
}

/* ==========================================================================
   Formatação
   ========================================================================== */

function formatMoeda(valor) {
  return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 4, maximumFractionDigits: 4 }).format(valor);
}

function formatDataCurta(dataIso) {
  const [ano, mes, dia] = dataIso.split("-");
  return `${dia}/${mes}/${ano}`;
}

function formatDataHora(dataHoraIso) {
  return new Date(dataHoraIso).toLocaleString("pt-BR");
}

function diferencaEmDias(dataInicioIso, dataFimIso) {
  const inicio = new Date(`${dataInicioIso}T00:00:00`);
  const fim = new Date(`${dataFimIso}T00:00:00`);
  return Math.round((fim - inicio) / 86400000);
}

/* ==========================================================================
   Seletor de data (substitui o <input type="date"> nativo)
   O calendário nativo do navegador não dá pra estilizar - foge do tema
   escuro do design system. Este componente guarda o valor num
   <input type="hidden"> (mesmo id de sempre, então o resto do código só lê
   ".value" normalmente) e desenha um calendário próprio, com os tokens
   --bt-* do design system, num painel posicionado sob o campo.
   ========================================================================== */

const NOMES_MES = [
  "janeiro", "fevereiro", "março", "abril", "maio", "junho",
  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
];
const NOMES_DIA_SEMANA = ["D", "S", "T", "Q", "Q", "S", "S"];

function paraIsoData(ano, mes, dia) {
  return `${ano}-${String(mes + 1).padStart(2, "0")}-${String(dia).padStart(2, "0")}`;
}

function mesmoDia(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function criarSeletorData(idBase) {
  const wrap = document.getElementById(`${idBase}-wrap`);
  const trigger = document.getElementById(`${idBase}-trigger`);
  const display = document.getElementById(`${idBase}-display`);
  const hidden = document.getElementById(idBase);
  const panel = document.getElementById(`${idBase}-panel`);

  let mesVisivel = new Date();

  function valorAtual() {
    return hidden.value ? new Date(`${hidden.value}T00:00:00`) : null;
  }

  function atualizarDisplay() {
    if (hidden.value) {
      display.textContent = formatDataCurta(hidden.value);
      display.removeAttribute("data-empty");
    } else {
      display.textContent = "Selecione";
      display.setAttribute("data-empty", "true");
    }
  }

  function selecionar(ano, mes, dia) {
    hidden.value = paraIsoData(ano, mes, dia);
    hidden.dispatchEvent(new Event("change", { bubbles: true }));
    mesVisivel = new Date(ano, mes, 1);
    atualizarDisplay();
    fechar();
  }

  function renderizarCalendario() {
    const ano = mesVisivel.getFullYear();
    const mes = mesVisivel.getMonth();
    const selecionado = valorAtual();
    const hoje = new Date();

    panel.innerHTML = "";

    const header = document.createElement("div");
    header.className = "bt-datepicker__header";

    const btnAnterior = document.createElement("button");
    btnAnterior.type = "button";
    btnAnterior.className = "bt-datepicker__nav";
    btnAnterior.setAttribute("aria-label", "Mês anterior");
    btnAnterior.textContent = "‹";
    btnAnterior.addEventListener("click", (evento) => {
      evento.stopPropagation();
      mesVisivel = new Date(ano, mes - 1, 1);
      renderizarCalendario();
    });

    const titulo = document.createElement("span");
    titulo.className = "bt-datepicker__month";
    titulo.textContent = `${NOMES_MES[mes]} de ${ano}`;

    const btnProximo = document.createElement("button");
    btnProximo.type = "button";
    btnProximo.className = "bt-datepicker__nav";
    btnProximo.setAttribute("aria-label", "Próximo mês");
    btnProximo.textContent = "›";
    btnProximo.addEventListener("click", (evento) => {
      evento.stopPropagation();
      mesVisivel = new Date(ano, mes + 1, 1);
      renderizarCalendario();
    });

    header.appendChild(btnAnterior);
    header.appendChild(titulo);
    header.appendChild(btnProximo);
    panel.appendChild(header);

    const semana = document.createElement("div");
    semana.className = "bt-datepicker__weekdays";
    NOMES_DIA_SEMANA.forEach((letra) => {
      const el = document.createElement("span");
      el.className = "bt-datepicker__weekday";
      el.textContent = letra;
      semana.appendChild(el);
    });
    panel.appendChild(semana);

    const dias = document.createElement("div");
    dias.className = "bt-datepicker__days";

    const primeiroDiaSemana = new Date(ano, mes, 1).getDay();
    const diasNoMes = new Date(ano, mes + 1, 0).getDate();
    const diasNoMesAnterior = new Date(ano, mes, 0).getDate();

    const celulas = [];
    for (let i = primeiroDiaSemana - 1; i >= 0; i--) {
      celulas.push({ dia: diasNoMesAnterior - i, mesOffset: -1 });
    }
    for (let d = 1; d <= diasNoMes; d++) {
      celulas.push({ dia: d, mesOffset: 0 });
    }
    let diaProximoMes = 1;
    while (celulas.length < 42) {
      celulas.push({ dia: diaProximoMes, mesOffset: 1 });
      diaProximoMes += 1;
    }

    celulas.forEach(({ dia, mesOffset }) => {
      const dataCelula = new Date(ano, mes + mesOffset, dia);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "bt-datepicker__day";
      btn.textContent = String(dia);
      if (mesOffset !== 0) btn.setAttribute("data-outside", "true");
      if (mesmoDia(dataCelula, hoje)) btn.setAttribute("data-today", "true");
      if (selecionado && mesmoDia(dataCelula, selecionado)) btn.setAttribute("data-selected", "true");
      btn.addEventListener("click", (evento) => {
        evento.stopPropagation();
        selecionar(dataCelula.getFullYear(), dataCelula.getMonth(), dataCelula.getDate());
      });
      dias.appendChild(btn);
    });

    panel.appendChild(dias);
  }

  function aoClicarFora(evento) {
    if (!wrap.contains(evento.target)) fechar();
  }

  function abrir() {
    if (hidden.value) mesVisivel = new Date(`${hidden.value}T00:00:00`);
    renderizarCalendario();
    panel.classList.remove("app-hidden");
    trigger.setAttribute("aria-expanded", "true");
    document.addEventListener("click", aoClicarFora);
  }

  function fechar() {
    panel.classList.add("app-hidden");
    trigger.setAttribute("aria-expanded", "false");
    document.removeEventListener("click", aoClicarFora);
  }

  trigger.addEventListener("click", (evento) => {
    evento.stopPropagation();
    if (panel.classList.contains("app-hidden")) abrir();
    else fechar();
  });

  atualizarDisplay();

  return {
    definirValor(isoValue) {
      hidden.value = isoValue || "";
      atualizarDisplay();
    },
  };
}

// Instâncias criadas uma vez, no boot (ver DOMContentLoaded) - guardadas
// aqui pra qualquer função poder ajustar o valor programaticamente
// (padrões iniciais, restaurar última consulta) mantendo o display do
// campo sincronizado com o <input type="hidden">.
const seletoresData = {};

/* ==========================================================================
   Alertas (bt-alert construído via DOM, textContent — dado de API é não confiável)
   ========================================================================== */

function renderAlert(container, mensagem, tipo = "danger") {
  container.className = `bt-alert bt-alert--${tipo}`;
  container.innerHTML = "";

  const icone = document.createElement("span");
  icone.className = "bt-alert__icon";
  icone.textContent = tipo === "danger" ? "⚠" : "ℹ";

  const corpo = document.createElement("div");
  const titulo = document.createElement("p");
  titulo.className = "bt-alert__title";
  titulo.textContent = tipo === "danger" ? "Erro" : "Aviso";
  const texto = document.createElement("p");
  texto.className = "bt-alert__body";
  texto.textContent = mensagem;

  corpo.appendChild(titulo);
  corpo.appendChild(texto);
  container.appendChild(icone);
  container.appendChild(corpo);
  container.classList.remove("app-hidden");
}

function clearAlert(container) {
  container.classList.add("app-hidden");
  container.innerHTML = "";
}

/* ==========================================================================
   Roteamento (hash)
   ========================================================================== */

let itemsCache = [];
let idItemAtual = null;

function router() {
  const hash = window.location.hash || "#/dashboard";

  // Guarda de autenticação: sem token, só a tela de login é alcançável.
  if (hash !== "#/login" && !estaAutenticado()) {
    window.location.hash = "#/login";
    return;
  }
  if (hash === "#/login" && estaAutenticado()) {
    window.location.hash = "#/dashboard";
    return;
  }

  const logado = estaAutenticado();
  document.getElementById("navbar-links").classList.toggle("app-hidden", !logado);
  document.getElementById("sidebar-footer").classList.toggle("app-hidden", !logado);
  if (logado) {
    atualizarContaLogada();
    iniciarRelogioProximaColeta();
  }

  document.querySelectorAll("[data-nav]").forEach((botao) => {
    const rotaAtiva = hash.startsWith("#/items") ? "#/items" : hash;
    botao.setAttribute("aria-current", botao.dataset.route === rotaAtiva ? "page" : "false");
  });

  [
    "view-login",
    "view-dashboard",
    "view-items",
    "view-detail",
    "view-consulta",
    "view-comparar",
    "view-conversao",
  ].forEach((id) => {
    document.getElementById(id).classList.add("app-hidden");
  });

  if (hash === "#/login") {
    document.getElementById("view-login").classList.remove("app-hidden");
  } else if (hash === "#/items") {
    document.getElementById("view-items").classList.remove("app-hidden");
    carregarListaItens();
  } else if (hash.startsWith("#/items/")) {
    const id = hash.split("/")[2];
    document.getElementById("view-detail").classList.remove("app-hidden");
    carregarDetalheItem(id);
  } else if (hash === "#/consulta") {
    document.getElementById("view-consulta").classList.remove("app-hidden");
    carregarMoedasConsultaSelect();
  } else if (hash === "#/comparar") {
    document.getElementById("view-comparar").classList.remove("app-hidden");
    abrirComparar();
  } else if (hash === "#/conversao") {
    document.getElementById("view-conversao").classList.remove("app-hidden");
    abrirConversao();
  } else {
    document.getElementById("view-dashboard").classList.remove("app-hidden");
    carregarDashboard();
  }
}

/* ==========================================================================
   View: dashboard
   Tela inicial após o login: resumo rápido (itens, alertas, conversões),
   ranking de maiores altas/baixas num recorte de moedas relevantes, e a
   evolução das moedas que o usuário já monitora no mês corrente.
   ========================================================================== */

const DASHBOARD_RANKING_DIAS = 90;
const DASHBOARD_RANKING_MAX_POR_LADO = 5;

async function carregarDashboard() {
  const alertaBox = document.getElementById("dashboard-alert");
  clearAlert(alertaBox);

  carregarResumoDashboard(alertaBox);
  carregarRankingDashboard();
  carregarMercadoDashboard();
  carregarConversoesResumoDashboard();
  carregarItensDashboard();
}

async function carregarResumoDashboard(alertaBox) {
  try {
    const resumo = await api.dashboardResumo();
    document.getElementById("dash-total-itens").textContent = String(resumo.total_itens);
    document.getElementById("dash-itens-alerta").textContent = String(resumo.itens_com_alerta);
    document.getElementById("dash-total-conversoes").textContent = String(resumo.total_conversoes);
  } catch (erro) {
    renderAlert(alertaBox, erro.message);
  }
}

async function carregarRankingDashboard() {
  const loading = document.getElementById("dash-ranking-loading");
  const vazio = document.getElementById("dash-ranking-vazio");
  const cols = document.getElementById("dash-ranking-cols");

  loading.classList.remove("app-hidden");
  vazio.classList.add("app-hidden");
  cols.classList.add("app-hidden");

  try {
    const ranking = await api.dashboardRanking(DASHBOARD_RANKING_DIAS);
    loading.classList.add("app-hidden");

    if (ranking.length === 0) {
      vazio.classList.remove("app-hidden");
      return;
    }

    const altas = ranking.slice(0, DASHBOARD_RANKING_MAX_POR_LADO);
    const restantes = ranking.slice(altas.length);
    const baixas = restantes.slice(-DASHBOARD_RANKING_MAX_POR_LADO).reverse();

    renderizarRankingDashboard("dash-ranking-altas", altas, "alta");
    renderizarRankingDashboard("dash-ranking-baixas", baixas, "baixa");
    cols.classList.remove("app-hidden");
  } catch (erro) {
    loading.classList.add("app-hidden");
    vazio.classList.remove("app-hidden");
  }
}

async function carregarMercadoDashboard() {
  const volatilidadeLoading = document.getElementById("dash-volatilidade-loading");
  const volatilidadeVazio = document.getElementById("dash-volatilidade-vazio");
  const volatilidadeLista = document.getElementById("dash-volatilidade-lista");

  const diaSemanaLoading = document.getElementById("dash-diasemana-loading");
  const diaSemanaVazio = document.getElementById("dash-diasemana-vazio");
  const diaSemanaLista = document.getElementById("dash-diasemana-lista");

  volatilidadeLoading.classList.remove("app-hidden");
  volatilidadeVazio.classList.add("app-hidden");
  volatilidadeLista.classList.add("app-hidden");
  diaSemanaLoading.classList.remove("app-hidden");
  diaSemanaVazio.classList.add("app-hidden");
  diaSemanaLista.classList.add("app-hidden");

  try {
    const mercado = await api.dashboardMercado(DASHBOARD_RANKING_DIAS);

    volatilidadeLoading.classList.add("app-hidden");
    if (mercado.volatilidade.length === 0) {
      volatilidadeVazio.classList.remove("app-hidden");
    } else {
      renderizarVolatilidadeDashboard(mercado.volatilidade.slice(0, DASHBOARD_RANKING_MAX_POR_LADO));
      volatilidadeLista.classList.remove("app-hidden");
    }

    diaSemanaLoading.classList.add("app-hidden");
    if (mercado.variacao_por_dia_semana.length === 0) {
      diaSemanaVazio.classList.remove("app-hidden");
    } else {
      renderizarDiaSemanaDashboard(mercado.variacao_por_dia_semana);
      diaSemanaLista.classList.remove("app-hidden");
    }
  } catch (erro) {
    volatilidadeLoading.classList.add("app-hidden");
    volatilidadeVazio.classList.remove("app-hidden");
    diaSemanaLoading.classList.add("app-hidden");
    diaSemanaVazio.classList.remove("app-hidden");
  }
}

function renderizarVolatilidadeDashboard(itens) {
  const container = document.getElementById("dash-volatilidade-lista");
  container.innerHTML = "";

  const maiorAbs = Math.max(...itens.map((item) => Math.abs(item.maior_variacao_diaria_percentual)), 0.01);

  itens.forEach((item) => {
    const tipo = item.maior_variacao_diaria_percentual >= 0 ? "alta" : "baixa";

    const row = document.createElement("div");
    row.className = "app-bar-row";

    const label = document.createElement("span");
    label.className = "app-bar-row__label";
    label.textContent = item.codigo;
    const sublabel = document.createElement("span");
    sublabel.className = "app-bar-row__sublabel";
    sublabel.textContent = formatDataCurta(item.data_ocorrencia);
    label.appendChild(sublabel);

    const track = document.createElement("div");
    track.className = "app-bar-row__track";
    const fill = document.createElement("div");
    fill.className = `app-bar-row__fill app-bar-row__fill--${tipo}`;
    fill.style.width = `${(Math.abs(item.maior_variacao_diaria_percentual) / maiorAbs) * 100}%`;
    track.appendChild(fill);

    const valor = document.createElement("span");
    valor.className = `app-bar-row__value app-bar-row__value--${tipo}`;
    valor.textContent = `${item.maior_variacao_diaria_percentual >= 0 ? "+" : ""}${item.maior_variacao_diaria_percentual.toFixed(2)}%`;

    row.appendChild(label);
    row.appendChild(track);
    row.appendChild(valor);
    container.appendChild(row);
  });
}

function renderizarDiaSemanaDashboard(itens) {
  const container = document.getElementById("dash-diasemana-lista");
  container.innerHTML = "";

  const maior = Math.max(...itens.map((item) => item.variacao_media_percentual), 0.01);

  itens.forEach((item) => {
    const row = document.createElement("div");
    row.className = "app-bar-row";

    const label = document.createElement("span");
    label.className = "app-bar-row__label";
    label.style.minWidth = "88px";
    label.textContent = item.dia_semana;

    const track = document.createElement("div");
    track.className = "app-bar-row__track";
    const fill = document.createElement("div");
    fill.className = "app-bar-row__fill app-bar-row__fill--neutra";
    fill.style.width = `${(item.variacao_media_percentual / maior) * 100}%`;
    track.appendChild(fill);

    const valor = document.createElement("span");
    valor.className = "app-bar-row__value";
    valor.textContent = `${item.variacao_media_percentual.toFixed(2)}%`;

    row.appendChild(label);
    row.appendChild(track);
    row.appendChild(valor);
    container.appendChild(row);
  });
}

async function carregarConversoesResumoDashboard() {
  const vazio = document.getElementById("dash-conversoes-vazio");
  const lista = document.getElementById("dash-conversoes-lista");
  vazio.classList.add("app-hidden");
  lista.classList.add("app-hidden");

  try {
    const resumo = await api.dashboardConversoesResumo();
    if (resumo.pares.length === 0) {
      vazio.classList.remove("app-hidden");
      return;
    }
    renderizarConversoesResumoDashboard(resumo.pares.slice(0, DASHBOARD_RANKING_MAX_POR_LADO));
    lista.classList.remove("app-hidden");
  } catch (erro) {
    vazio.classList.remove("app-hidden");
  }
}

function renderizarConversoesResumoDashboard(pares) {
  const container = document.getElementById("dash-conversoes-lista");
  container.innerHTML = "";

  pares.forEach((par) => {
    const row = document.createElement("div");
    row.className = "app-bar-row";

    const label = document.createElement("span");
    label.className = "app-bar-row__label";
    label.style.minWidth = "120px";
    label.textContent = `${par.moeda_origem} → ${par.moeda_destino}`;

    const track = document.createElement("div");
    track.className = "app-bar-row__track";
    const fill = document.createElement("div");
    fill.className = "app-bar-row__fill app-bar-row__fill--neutra";
    fill.style.width = `${par.percentual}%`;
    track.appendChild(fill);

    const valor = document.createElement("span");
    valor.className = "app-bar-row__value";
    valor.textContent = `${par.quantidade}x (${par.percentual.toFixed(0)}%)`;

    row.appendChild(label);
    row.appendChild(track);
    row.appendChild(valor);
    container.appendChild(row);
  });
}

function renderizarRankingDashboard(containerId, itens, tipo) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";

  if (itens.length === 0) {
    const vazio = document.createElement("span");
    vazio.className = "bt-body-sm";
    vazio.textContent = "Sem dados suficientes.";
    container.appendChild(vazio);
    return;
  }

  const maiorAbs = Math.max(...itens.map((item) => Math.abs(item.variacao_percentual)), 0.01);

  itens.forEach((item) => {
    const row = document.createElement("div");
    row.className = "app-bar-row";

    const label = document.createElement("span");
    label.className = "app-bar-row__label";
    label.textContent = item.codigo;

    const track = document.createElement("div");
    track.className = "app-bar-row__track";
    const fill = document.createElement("div");
    fill.className = `app-bar-row__fill app-bar-row__fill--${tipo}`;
    fill.style.width = `${(Math.abs(item.variacao_percentual) / maiorAbs) * 100}%`;
    track.appendChild(fill);

    const valor = document.createElement("span");
    valor.className = `app-bar-row__value app-bar-row__value--${tipo}`;
    valor.textContent = `${item.variacao_percentual >= 0 ? "+" : ""}${item.variacao_percentual.toFixed(2)}%`;

    row.appendChild(label);
    row.appendChild(track);
    row.appendChild(valor);
    container.appendChild(row);
  });
}

async function carregarItensDashboard() {
  const vazio = document.getElementById("dash-itens-vazio");
  const wrap = document.getElementById("dash-itens-chart-wrap");
  vazio.classList.add("app-hidden");
  wrap.classList.add("app-hidden");

  let itens;
  try {
    itens = await api.listarItens();
    itemsCache = itens;
  } catch (erro) {
    vazio.classList.remove("app-hidden");
    return;
  }

  if (itens.length === 0) {
    vazio.classList.remove("app-hidden");
    return;
  }

  const periodo = calcularPeriodoMonitoramento();

  try {
    const resultados = await Promise.all(
      itens.map(async (item) => {
        const pontos = await api.consultaLivre(item.moeda, periodo.dataInicio, periodo.dataFim);
        return {
          moeda: item.moeda,
          pontos: [...pontos].sort((a, b) => a.data_cotacao.localeCompare(b.data_cotacao)),
        };
      })
    );

    const comDados = resultados.filter((r) => r.pontos.length > 0);
    if (comDados.length === 0) {
      vazio.classList.remove("app-hidden");
      return;
    }

    renderChartComparativo(
      document.getElementById("dash-itens-chart-container"),
      document.getElementById("dash-itens-chart-legend"),
      comDados
    );
    wrap.classList.remove("app-hidden");
  } catch (erro) {
    vazio.classList.remove("app-hidden");
  }
}

/* ==========================================================================
   View: lista de itens
   ========================================================================== */

async function carregarListaItens() {
  const loading = document.getElementById("items-loading");
  const vazio = document.getElementById("items-empty");
  const grid = document.getElementById("items-grid");
  const alertaGlobal = document.getElementById("global-alert");

  clearAlert(alertaGlobal);
  grid.classList.add("app-hidden");
  vazio.classList.add("app-hidden");
  loading.classList.remove("app-hidden");

  try {
    const itens = await api.listarItens();
    itemsCache = itens;
    loading.classList.add("app-hidden");

    if (itens.length === 0) {
      vazio.classList.remove("app-hidden");
      return;
    }

    grid.innerHTML = "";
    itens.forEach((item) => grid.appendChild(criarCardItem(item)));
    grid.classList.remove("app-hidden");
  } catch (erro) {
    loading.classList.add("app-hidden");
    renderAlert(alertaGlobal, erro.message);
  }
}

function criarBadgeVariacao(variacaoPercentual) {
  if (variacaoPercentual === null || variacaoPercentual === undefined) return null;
  if (Math.abs(variacaoPercentual) < ALERTA_VARIACAO_PERCENTUAL) return null;

  const subiu = variacaoPercentual > 0;
  const badge = document.createElement("span");
  badge.className = `bt-badge ${subiu ? "bt-badge--success" : "bt-badge--danger"}`;
  badge.title = "Variação desde a coleta anterior";
  badge.textContent = `${subiu ? "▲" : "▼"} ${Math.abs(variacaoPercentual).toFixed(1)}%`;
  return badge;
}

function criarCardItem(item) {
  const card = document.createElement("article");
  card.className = "bt-card bt-card--interactive bt-focusable";
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  const irParaDetalhe = () => { window.location.hash = `#/items/${item.id}`; };
  card.addEventListener("click", irParaDetalhe);
  card.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" || evento.key === " ") { evento.preventDefault(); irParaDetalhe(); }
  });

  const head = document.createElement("div");
  head.className = "app-item-card__head";
  const titulo = document.createElement("h3");
  titulo.className = "bt-card__title";
  titulo.textContent = item.nome;

  const selos = document.createElement("div");
  selos.style.display = "flex";
  selos.style.gap = "var(--bt-space-2)";
  const badgeMoeda = document.createElement("span");
  badgeMoeda.className = "bt-badge bt-badge--brand";
  badgeMoeda.textContent = item.moeda;
  selos.appendChild(badgeMoeda);
  const badgeVariacao = criarBadgeVariacao(item.variacao_percentual);
  if (badgeVariacao) selos.appendChild(badgeVariacao);

  head.appendChild(titulo);
  head.appendChild(selos);
  card.appendChild(head);

  if (item.ultima_coleta) {
    const valor = document.createElement("div");
    valor.className = "app-item-card__value";
    valor.textContent = `R$ ${formatMoeda(item.ultima_coleta.valor_compra)}`;
    card.appendChild(valor);

    const linha = document.createElement("div");
    linha.className = "app-item-card__row";
    const venda = document.createElement("span");
    venda.textContent = `Venda: R$ ${formatMoeda(item.ultima_coleta.valor_venda)}`;
    const data = document.createElement("span");
    data.textContent = formatDataCurta(item.ultima_coleta.data_cotacao);
    linha.appendChild(venda);
    linha.appendChild(data);
    card.appendChild(linha);
  } else {
    const semDados = document.createElement("p");
    semDados.className = "bt-body-sm";
    semDados.textContent = "Sem coleta ainda.";
    card.appendChild(semDados);
  }

  return card;
}

/* ==========================================================================
   Modal: cadastrar item
   ========================================================================== */

let moedasCache = null;

async function carregarMoedas() {
  if (moedasCache) return moedasCache;
  try {
    moedasCache = await api.listarMoedas();
  } catch (erro) {
    moedasCache = [];
    console.error("Falha ao carregar lista de moedas:", erro.message);
  }
  return moedasCache;
}

function popularSelectMoedas(moedas) {
  const select = document.getElementById("create-moeda");
  select.innerHTML = "";

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.disabled = true;
  placeholder.selected = true;
  placeholder.textContent = moedas.length > 0 ? "Selecione a moeda" : "Não foi possível carregar as moedas";
  select.appendChild(placeholder);

  moedas.forEach((m) => {
    const option = document.createElement("option");
    option.value = m.codigo;
    option.dataset.nome = m.nome;
    option.textContent = `${m.codigo} — ${m.nome}`;
    select.appendChild(option);
  });

  select.disabled = moedas.length === 0;
}

async function abrirModalCriar() {
  document.getElementById("modal-create").classList.remove("app-hidden");
  document.getElementById("create-nome").focus();

  const select = document.getElementById("create-moeda");
  select.disabled = true;
  select.innerHTML = '<option value="" disabled selected>Carregando moedas…</option>';

  const moedas = await carregarMoedas();
  popularSelectMoedas(moedas);
}

function fecharModalCriar() {
  document.getElementById("modal-create").classList.add("app-hidden");
  document.getElementById("form-create").reset();
  clearAlert(document.getElementById("create-alert"));
}

async function aoSubmeterCriacao(evento) {
  evento.preventDefault();
  const nome = document.getElementById("create-nome").value.trim();
  const moeda = document.getElementById("create-moeda").value.trim();
  const alertaBox = document.getElementById("create-alert");
  const botao = document.getElementById("btn-submit-create");

  clearAlert(alertaBox);
  botao.setAttribute("aria-busy", "true");
  botao.disabled = true;

  try {
    await api.criarItem({ nome, moeda });
    fecharModalCriar();
    await carregarListaItens();
  } catch (erro) {
    if (erro.status === 409 && erro.detalhe && typeof erro.detalhe === "object") {
      renderAvisoMoedaDuplicada(erro.detalhe);
    } else {
      renderAlert(alertaBox, erro.message);
    }
  } finally {
    botao.removeAttribute("aria-busy");
    botao.disabled = false;
  }
}

function formatarTempoRestante(segundos) {
  if (segundos === null || segundos === undefined) {
    return "Não foi possível calcular quando será a próxima coleta automática.";
  }
  if (segundos <= 0) {
    return "A próxima coleta automática deve acontecer a qualquer momento.";
  }
  const minutos = Math.floor(segundos / 60);
  const resto = segundos % 60;
  if (minutos === 0) return `Faltam ${resto}s para a próxima coleta automática.`;
  return `Faltam ${minutos} min para a próxima coleta automática.`;
}

function renderAvisoMoedaDuplicada(detalhe) {
  const container = document.getElementById("create-alert");
  container.className = "bt-alert bt-alert--warning";
  container.innerHTML = "";

  const icone = document.createElement("span");
  icone.className = "bt-alert__icon";
  icone.textContent = "ℹ";

  const corpo = document.createElement("div");
  corpo.style.display = "flex";
  corpo.style.flexDirection = "column";
  corpo.style.gap = "var(--bt-space-3)";

  const titulo = document.createElement("p");
  titulo.className = "bt-alert__title";
  titulo.textContent = "Moeda já cadastrada";

  const texto = document.createElement("p");
  texto.className = "bt-alert__body";
  texto.textContent = `${detalhe.nome} (${detalhe.moeda}) já está sendo monitorada. ${formatarTempoRestante(detalhe.segundos_ate_proxima_coleta)} Quer coletar agora mesmo assim?`;

  const botaoColetar = document.createElement("button");
  botaoColetar.type = "button";
  botaoColetar.className = "bt-btn bt-btn--secondary bt-btn--sm";
  botaoColetar.textContent = "Coletar agora mesmo assim";
  botaoColetar.addEventListener("click", async () => {
    botaoColetar.setAttribute("aria-busy", "true");
    botaoColetar.disabled = true;
    try {
      await api.coletarAgora(detalhe.item_id);
      fecharModalCriar();
      await carregarListaItens();
    } catch (erro) {
      renderAlert(container, erro.message);
    } finally {
      botaoColetar.removeAttribute("aria-busy");
      botaoColetar.disabled = false;
    }
  });

  corpo.appendChild(titulo);
  corpo.appendChild(texto);
  corpo.appendChild(botaoColetar);
  container.appendChild(icone);
  container.appendChild(corpo);
  container.classList.remove("app-hidden");
}

/* ==========================================================================
   View: detalhe do item
   ========================================================================== */

async function carregarDetalheItem(id) {
  idItemAtual = id;
  const alertaBox = document.getElementById("detail-alert");
  clearAlert(alertaBox);

  let item = itemsCache.find((i) => String(i.id) === String(id));
  if (!item) {
    try {
      itemsCache = await api.listarItens();
      item = itemsCache.find((i) => String(i.id) === String(id));
    } catch (erro) {
      renderAlert(alertaBox, erro.message);
      return;
    }
  }
  if (!item) {
    renderAlert(alertaBox, "Item não encontrado.");
    return;
  }

  document.getElementById("detail-nome").textContent = item.nome;
  document.getElementById("detail-moeda-label").textContent = item.moeda;
  atualizarStatsDetalhe(item.ultima_coleta);

  const containerBadge = document.getElementById("detail-alerta-variacao");
  containerBadge.innerHTML = "";
  const badgeVariacao = criarBadgeVariacao(item.variacao_percentual);
  if (badgeVariacao) {
    badgeVariacao.style.fontSize = "var(--bt-text-sm)";
    containerBadge.appendChild(badgeVariacao);
  }

  const periodo = calcularPeriodoMonitoramento();
  document.getElementById("monitor-periodo-label").textContent =
    `${formatDataCurta(periodo.dataInicio)} a ${formatDataCurta(periodo.dataFim)}`;

  try {
    const cotacoes = await api.consultaLivre(item.moeda, periodo.dataInicio, periodo.dataFim);
    renderizarTabelaCotacoes("history-table-body", cotacoes);
    renderChart(document.getElementById("chart-container"), cotacoes, document.getElementById("chart-empty"));
  } catch (erro) {
    renderAlert(alertaBox, erro.message);
  }
}

/* ==========================================================================
   Período do monitoramento em tempo real: mês corrente até hoje. Nos
   primeiros 3 dias do mês há pouquíssimos boletins publicados ainda, então
   o período é estendido pra trás até o início do mês anterior, garantindo
   um gráfico/tabela com dados úteis mesmo no começo do mês.
   ========================================================================== */

function calcularPeriodoMonitoramento() {
  const hoje = new Date();
  const ano = hoje.getFullYear();
  const mes = hoje.getMonth();
  const dia = hoje.getDate();

  const inicio = dia <= 3 ? new Date(ano, mes - 1, 1) : new Date(ano, mes, 1);
  const paraIso = (d) => d.toISOString().slice(0, 10);

  return { dataInicio: paraIso(inicio), dataFim: paraIso(hoje) };
}

function atualizarStatsDetalhe(coleta) {
  document.getElementById("stat-compra").textContent = coleta ? `R$ ${formatMoeda(coleta.valor_compra)}` : "—";
  document.getElementById("stat-venda").textContent = coleta ? `R$ ${formatMoeda(coleta.valor_venda)}` : "—";
  document.getElementById("stat-data").textContent = coleta ? formatDataCurta(coleta.data_cotacao) : "—";
  document.getElementById("stat-coletado").textContent = coleta ? formatDataHora(coleta.coletado_em) : "—";
}

function preencherLinha(tr, texto, numerico) {
  const td = document.createElement("td");
  if (numerico) td.setAttribute("data-numeric", "");
  td.textContent = texto;
  tr.appendChild(td);
}

function renderizarTabelaCotacoes(idTbody, cotacoes) {
  const tbody = document.getElementById(idTbody);
  tbody.innerHTML = "";

  if (!cotacoes || cotacoes.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 3;
    td.textContent = "Sem cotações nesse período.";
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }

  [...cotacoes].reverse().forEach((c) => {
    const tr = document.createElement("tr");
    preencherLinha(tr, formatDataCurta(c.data_cotacao));
    preencherLinha(tr, formatMoeda(c.valor_compra), true);
    preencherLinha(tr, formatMoeda(c.valor_venda), true);
    tbody.appendChild(tr);
  });
}

async function aoClicarColetar() {
  if (!idItemAtual) return;
  const botao = document.getElementById("btn-collect");
  const alertaBox = document.getElementById("detail-alert");
  clearAlert(alertaBox);
  botao.setAttribute("aria-busy", "true");
  botao.disabled = true;

  try {
    await api.coletarAgora(idItemAtual);
    itemsCache = []; // força recarregar a lista com o dado novo quando o usuário voltar
    await carregarDetalheItem(idItemAtual);
  } catch (erro) {
    renderAlert(alertaBox, erro.message);
  } finally {
    botao.removeAttribute("aria-busy");
    botao.disabled = false;
  }
}

/* ==========================================================================
   View: consulta livre
   ========================================================================== */

// Guarda a última consulta feita (moeda, período e resultado) pra
// reaparecer sozinha ao voltar nessa tela - inclusive depois de recarregar
// a página, já que é só uma consulta salva, não dado sensível.
const CHAVE_ULTIMA_CONSULTA = "btime_ultima_consulta_livre";

function salvarUltimaConsulta(moeda, dataInicio, dataFim, dados) {
  try {
    localStorage.setItem(CHAVE_ULTIMA_CONSULTA, JSON.stringify({ moeda, dataInicio, dataFim, dados }));
  } catch (erro) {
    // localStorage indisponível (modo privado, quota etc.) - não é crítico.
  }
}

function carregarUltimaConsulta() {
  try {
    const bruto = localStorage.getItem(CHAVE_ULTIMA_CONSULTA);
    return bruto ? JSON.parse(bruto) : null;
  } catch (erro) {
    return null;
  }
}

async function carregarMoedasConsultaSelect() {
  const select = document.getElementById("consulta-moeda");
  const dica = document.getElementById("consulta-moeda-hint");

  select.disabled = true;
  select.innerHTML = '<option value="" disabled selected>Carregando…</option>';
  dica.textContent = "";

  const moedas = await carregarMoedas();

  select.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.disabled = true;
  placeholder.selected = true;

  if (moedas.length === 0) {
    placeholder.textContent = "Não foi possível carregar as moedas";
    select.appendChild(placeholder);
    dica.textContent = "Falha ao consultar a lista de moedas da PTAX. Tente recarregar a página.";
    return;
  }

  placeholder.textContent = "Selecione a moeda";
  select.appendChild(placeholder);

  moedas.forEach((m) => {
    const option = document.createElement("option");
    option.value = m.codigo;
    option.textContent = `${m.codigo} — ${m.nome}`;
    select.appendChild(option);
  });
  select.disabled = false;

  const ultima = carregarUltimaConsulta();
  if (ultima) {
    select.value = ultima.moeda;
    seletoresData.consultaInicio.definirValor(ultima.dataInicio);
    seletoresData.consultaFim.definirValor(ultima.dataFim);

    if (ultima.dados.length === 0) {
      document.getElementById("consulta-empty").classList.remove("app-hidden");
    } else {
      renderizarTabelaCotacoes("consulta-table-body", ultima.dados);
      renderChart(document.getElementById("consulta-chart-container"), ultima.dados, null);
      document.getElementById("consulta-resultado").classList.remove("app-hidden");
    }
  }
}

async function aoSubmeterConsulta(evento) {
  evento.preventDefault();
  const moeda = document.getElementById("consulta-moeda").value.trim();
  const dataInicio = document.getElementById("consulta-inicio").value;
  const dataFim = document.getElementById("consulta-fim").value;
  const alertaBox = document.getElementById("consulta-alert");
  const resultado = document.getElementById("consulta-resultado");
  const vazio = document.getElementById("consulta-empty");
  const botao = document.getElementById("btn-consultar");

  clearAlert(alertaBox);
  resultado.classList.add("app-hidden");
  vazio.classList.add("app-hidden");

  const dias = diferencaEmDias(dataInicio, dataFim);
  if (dias > JANELA_MAXIMA_CONSULTA_DIAS) {
    renderAlert(
      alertaBox,
      `O período selecionado tem ${dias} dias — o máximo permitido é ${JANELA_MAXIMA_CONSULTA_DIAS}. Ajuste as datas para uma janela menor.`,
      "warning"
    );
    return;
  }

  botao.setAttribute("aria-busy", "true");
  botao.disabled = true;

  try {
    const dados = await api.consultaLivre(moeda, dataInicio, dataFim);
    if (dados.length === 0) {
      vazio.classList.remove("app-hidden");
    } else {
      renderizarTabelaCotacoes("consulta-table-body", dados);
      renderChart(document.getElementById("consulta-chart-container"), dados, null);
      resultado.classList.remove("app-hidden");
    }
    salvarUltimaConsulta(moeda, dataInicio, dataFim, dados);
  } catch (erro) {
    renderAlert(alertaBox, erro.message);
  } finally {
    botao.removeAttribute("aria-busy");
    botao.disabled = false;
  }
}

/* ==========================================================================
   Gráfico (SVG, sem dependência externa)
   Duas séries (compra/venda), crosshair + tooltip no hover, eixo Y com
   gridlines hairline, rótulo de valor no fim de cada linha.
   ========================================================================== */

const SVG_NS = "http://www.w3.org/2000/svg";

function renderChart(container, dados, elementoVazio) {
  container.innerHTML = "";

  if (!dados || dados.length === 0) {
    if (elementoVazio) elementoVazio.classList.remove("app-hidden");
    return;
  }
  if (elementoVazio) elementoVazio.classList.add("app-hidden");

  const pontos = [...dados].sort((a, b) => a.data_cotacao.localeCompare(b.data_cotacao));

  const W = 700;
  const H = 260;
  const margin = { top: 16, right: 16, bottom: 28, left: 56 };
  const innerW = W - margin.left - margin.right;
  const innerH = H - margin.top - margin.bottom;

  const valores = pontos.flatMap((p) => [p.valor_compra, p.valor_venda]);
  const minVal = Math.min(...valores);
  const maxVal = Math.max(...valores);
  const pad = (maxVal - minVal) * 0.15 || Math.max(minVal * 0.01, 0.01);
  const yMin = minVal - pad;
  const yMax = maxVal + pad;

  const xFor = (i) => margin.left + (pontos.length === 1 ? innerW / 2 : (i / (pontos.length - 1)) * innerW);
  const yFor = (v) => margin.top + innerH - ((v - yMin) / (yMax - yMin)) * innerH;

  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("width", "100%");
  svg.style.display = "block";

  // Gridlines hairline + rótulos do eixo Y
  const NUM_TICKS = 4;
  for (let t = 0; t <= NUM_TICKS; t++) {
    const v = yMin + ((yMax - yMin) * t) / NUM_TICKS;
    const y = yFor(v);

    const linha = document.createElementNS(SVG_NS, "line");
    linha.setAttribute("x1", String(margin.left));
    linha.setAttribute("x2", String(W - margin.right));
    linha.setAttribute("y1", String(y));
    linha.setAttribute("y2", String(y));
    linha.setAttribute("stroke", "var(--bt-border)");
    linha.setAttribute("stroke-width", "1");
    svg.appendChild(linha);

    const rotulo = document.createElementNS(SVG_NS, "text");
    rotulo.setAttribute("x", String(margin.left - 8));
    rotulo.setAttribute("y", String(y + 3));
    rotulo.setAttribute("text-anchor", "end");
    rotulo.setAttribute("font-size", "10");
    rotulo.setAttribute("font-family", "var(--bt-font-mono)");
    rotulo.setAttribute("fill", "var(--bt-text-subtle)");
    rotulo.textContent = v.toFixed(3);
    svg.appendChild(rotulo);
  }

  function desenharSerie(chave, cor) {
    const d = pontos.map((p, i) => `${i === 0 ? "M" : "L"} ${xFor(i)} ${yFor(p[chave])}`).join(" ");
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", cor);
    path.setAttribute("stroke-width", "2");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    svg.appendChild(path);

    const ultimo = pontos.length - 1;
    const cx = xFor(ultimo);
    const cy = yFor(pontos[ultimo][chave]);

    const anel = document.createElementNS(SVG_NS, "circle");
    anel.setAttribute("cx", String(cx));
    anel.setAttribute("cy", String(cy));
    anel.setAttribute("r", "6");
    anel.setAttribute("fill", "var(--bt-surface)");
    svg.appendChild(anel);

    const ponto = document.createElementNS(SVG_NS, "circle");
    ponto.setAttribute("cx", String(cx));
    ponto.setAttribute("cy", String(cy));
    ponto.setAttribute("r", "4");
    ponto.setAttribute("fill", cor);
    svg.appendChild(ponto);
  }

  desenharSerie("valor_venda", "var(--bt-accent)");
  desenharSerie("valor_compra", "var(--bt-brand)");

  // Rótulos do eixo X: primeira e última data
  [0, pontos.length - 1].forEach((i, indice) => {
    if (indice === 1 && pontos.length === 1) return;
    const rotulo = document.createElementNS(SVG_NS, "text");
    rotulo.setAttribute("x", String(xFor(i)));
    rotulo.setAttribute("y", String(H - 8));
    rotulo.setAttribute("text-anchor", i === 0 ? "start" : "end");
    rotulo.setAttribute("font-size", "10");
    rotulo.setAttribute("font-family", "var(--bt-font-mono)");
    rotulo.setAttribute("fill", "var(--bt-text-subtle)");
    rotulo.textContent = formatDataCurta(pontos[i].data_cotacao);
    svg.appendChild(rotulo);
  });

  // Crosshair + pontos de hover
  const crosshair = document.createElementNS(SVG_NS, "line");
  crosshair.setAttribute("y1", String(margin.top));
  crosshair.setAttribute("y2", String(H - margin.bottom));
  crosshair.setAttribute("stroke", "var(--bt-border-strong)");
  crosshair.setAttribute("stroke-width", "1");
  crosshair.setAttribute("opacity", "0");
  svg.appendChild(crosshair);

  const hoverCompra = document.createElementNS(SVG_NS, "circle");
  hoverCompra.setAttribute("r", "4");
  hoverCompra.setAttribute("fill", "var(--bt-brand)");
  hoverCompra.setAttribute("opacity", "0");
  svg.appendChild(hoverCompra);

  const hoverVenda = document.createElementNS(SVG_NS, "circle");
  hoverVenda.setAttribute("r", "4");
  hoverVenda.setAttribute("fill", "var(--bt-accent)");
  hoverVenda.setAttribute("opacity", "0");
  svg.appendChild(hoverVenda);

  // Hit target cobrindo toda a área do gráfico (maior que as linhas)
  const overlay = document.createElementNS(SVG_NS, "rect");
  overlay.setAttribute("x", String(margin.left));
  overlay.setAttribute("y", String(margin.top));
  overlay.setAttribute("width", String(innerW));
  overlay.setAttribute("height", String(innerH));
  overlay.setAttribute("fill", "transparent");
  svg.appendChild(overlay);

  container.appendChild(svg);

  const tooltip = document.createElement("div");
  tooltip.className = "app-tooltip";
  container.appendChild(tooltip);

  function linhaTooltip(rotulo, cor, valor) {
    const linha = document.createElement("div");
    linha.className = "app-tooltip__row";
    const chave = document.createElement("span");
    chave.className = "app-tooltip__key";
    chave.style.background = cor;
    const texto = document.createElement("span");
    texto.textContent = `${rotulo}:`;
    const valorSpan = document.createElement("span");
    valorSpan.className = "app-tooltip__value";
    valorSpan.textContent = `R$ ${formatMoeda(valor)}`;
    linha.appendChild(chave);
    linha.appendChild(texto);
    linha.appendChild(valorSpan);
    return linha;
  }

  function aoMoverPonteiro(evento) {
    const rect = svg.getBoundingClientRect();
    const escalaX = W / rect.width;
    const xSvg = (evento.clientX - rect.left) * escalaX;
    let indice = Math.round(((xSvg - margin.left) / innerW) * (pontos.length - 1));
    indice = Math.max(0, Math.min(pontos.length - 1, indice));

    const px = xFor(indice);
    crosshair.setAttribute("x1", String(px));
    crosshair.setAttribute("x2", String(px));
    crosshair.setAttribute("opacity", "1");

    hoverCompra.setAttribute("cx", String(px));
    hoverCompra.setAttribute("cy", String(yFor(pontos[indice].valor_compra)));
    hoverCompra.setAttribute("opacity", "1");

    hoverVenda.setAttribute("cx", String(px));
    hoverVenda.setAttribute("cy", String(yFor(pontos[indice].valor_venda)));
    hoverVenda.setAttribute("opacity", "1");

    tooltip.innerHTML = "";
    const dataLinha = document.createElement("div");
    dataLinha.className = "bt-label";
    dataLinha.style.marginBottom = "4px";
    dataLinha.textContent = formatDataCurta(pontos[indice].data_cotacao);
    tooltip.appendChild(dataLinha);
    tooltip.appendChild(linhaTooltip("Compra", "var(--bt-brand)", pontos[indice].valor_compra));
    tooltip.appendChild(linhaTooltip("Venda", "var(--bt-accent)", pontos[indice].valor_venda));

    const larguraRelativa = px / W;
    const offsetPx = larguraRelativa * rect.width;
    const viraDaDireita = larguraRelativa > 0.6;
    tooltip.style.left = viraDaDireita ? "auto" : `${offsetPx + 14}px`;
    tooltip.style.right = viraDaDireita ? `${rect.width - offsetPx + 14}px` : "auto";
    tooltip.style.top = "8px";
    tooltip.setAttribute("data-visible", "true");
  }

  function aoSairPonteiro() {
    crosshair.setAttribute("opacity", "0");
    hoverCompra.setAttribute("opacity", "0");
    hoverVenda.setAttribute("opacity", "0");
    tooltip.setAttribute("data-visible", "false");
  }

  overlay.addEventListener("mousemove", aoMoverPonteiro);
  overlay.addEventListener("mouseleave", aoSairPonteiro);
  overlay.addEventListener("focus", () => aoMoverPonteiro({ clientX: svg.getBoundingClientRect().left }));
}

/* ==========================================================================
   View: comparar moedas
   Compara N moedas (qualquer uma da PTAX) num mesmo período. Como as
   escalas são muito diferentes entre si (ex: Iene ~0,03 vs Libra ~6,5), o
   gráfico normaliza cada série em % de variação desde o primeiro ponto do
   período, em vez de plotar os valores absolutos.
   ========================================================================== */

const PALETA_COMPARACAO = [
  "var(--bt-brand)",
  "var(--bt-accent)",
  "var(--bt-cyan-500)",
  "var(--bt-blue-500)",
  "var(--bt-green-500)",
  "var(--bt-amber-500)",
];
const MAX_MOEDAS_COMPARAR = 6;

let compararSelecionadas = new Set(["USD", "EUR", "GBP"]);

async function abrirComparar() {
  const periodo = calcularPeriodoMonitoramento();
  if (!document.getElementById("comparar-inicio").value) {
    seletoresData.compararInicio.definirValor(periodo.dataInicio);
  }
  if (!document.getElementById("comparar-fim").value) {
    seletoresData.compararFim.definirValor(periodo.dataFim);
  }

  atualizarContadorComparar();

  const lista = document.getElementById("comparar-lista-moedas");
  lista.innerHTML = '<span class="bt-body-sm">Carregando moedas…</span>';

  const moedas = await carregarMoedas();
  if (moedas.length === 0) {
    lista.innerHTML = '<span class="bt-body-sm">Não foi possível carregar a lista de moedas.</span>';
    return;
  }
  renderizarListaComparar(moedas);
}

function renderizarListaComparar(moedas) {
  const filtro = document.getElementById("comparar-filtro").value.trim().toLowerCase();
  const container = document.getElementById("comparar-lista-moedas");
  container.innerHTML = "";

  const filtradas = moedas.filter(
    (m) => !filtro || m.codigo.toLowerCase().includes(filtro) || m.nome.toLowerCase().includes(filtro)
  );

  if (filtradas.length === 0) {
    container.innerHTML = '<span class="bt-body-sm">Nenhuma moeda encontrada.</span>';
    return;
  }

  filtradas.forEach((m) => {
    const label = document.createElement("label");
    label.className = "app-checkbox-item";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = m.codigo;
    input.checked = compararSelecionadas.has(m.codigo);
    input.disabled = !input.checked && compararSelecionadas.size >= MAX_MOEDAS_COMPARAR;
    input.addEventListener("change", () => {
      if (input.checked) compararSelecionadas.add(m.codigo);
      else compararSelecionadas.delete(m.codigo);
      atualizarContadorComparar();
      container.querySelectorAll("input[type=checkbox]").forEach((cb) => {
        if (!cb.checked) cb.disabled = compararSelecionadas.size >= MAX_MOEDAS_COMPARAR;
      });
    });

    const span = document.createElement("span");
    span.textContent = `${m.codigo} — ${m.nome}`;

    label.appendChild(input);
    label.appendChild(span);
    container.appendChild(label);
  });
}

function atualizarContadorComparar() {
  document.getElementById("comparar-selecionadas-hint").textContent =
    `${compararSelecionadas.size} de ${MAX_MOEDAS_COMPARAR} selecionadas`;
}

async function aoSubmeterComparar(evento) {
  evento.preventDefault();
  const moedas = [...compararSelecionadas];
  const alertaBox = document.getElementById("comparar-alert");
  const resultado = document.getElementById("comparar-resultado");
  const vazio = document.getElementById("comparar-empty");
  const botao = document.getElementById("btn-comparar");

  clearAlert(alertaBox);
  resultado.classList.add("app-hidden");
  vazio.classList.add("app-hidden");

  if (moedas.length === 0) {
    renderAlert(alertaBox, "Selecione ao menos uma moeda para comparar.");
    return;
  }

  const dataInicio = document.getElementById("comparar-inicio").value;
  const dataFim = document.getElementById("comparar-fim").value;

  const dias = diferencaEmDias(dataInicio, dataFim);
  if (dias > JANELA_MAXIMA_CONSULTA_DIAS) {
    renderAlert(
      alertaBox,
      `O período selecionado tem ${dias} dias — o máximo permitido é ${JANELA_MAXIMA_CONSULTA_DIAS}. Ajuste as datas para uma janela menor.`,
      "warning"
    );
    return;
  }

  botao.setAttribute("aria-busy", "true");
  botao.disabled = true;

  try {
    const resultados = await Promise.all(
      moedas.map(async (moeda) => {
        const pontos = await api.consultaLivre(moeda, dataInicio, dataFim);
        return {
          moeda,
          pontos: [...pontos].sort((a, b) => a.data_cotacao.localeCompare(b.data_cotacao)),
        };
      })
    );

    const comDados = resultados.filter((r) => r.pontos.length > 0);
    if (comDados.length === 0) {
      vazio.classList.remove("app-hidden");
      return;
    }

    renderChartComparativo(
      document.getElementById("comparar-chart-container"),
      document.getElementById("comparar-chart-legend"),
      comDados
    );
    renderizarTabelaComparar(comDados);
    resultado.classList.remove("app-hidden");
  } catch (erro) {
    renderAlert(alertaBox, erro.message);
  } finally {
    botao.removeAttribute("aria-busy");
    botao.disabled = false;
  }
}

function renderizarTabelaComparar(comDados) {
  const tbody = document.getElementById("comparar-table-body");
  tbody.innerHTML = "";
  const nomePorCodigo = Object.fromEntries((moedasCache || []).map((m) => [m.codigo, m.nome]));

  comDados.forEach(({ moeda, pontos }) => {
    const primeiro = pontos[0];
    const ultimo = pontos[pontos.length - 1];
    const variacao = primeiro.valor_compra
      ? ((ultimo.valor_compra - primeiro.valor_compra) / primeiro.valor_compra) * 100
      : 0;

    const tr = document.createElement("tr");
    const tdMoeda = document.createElement("td");
    tdMoeda.textContent = nomePorCodigo[moeda] ? `${moeda} — ${nomePorCodigo[moeda]}` : moeda;
    tr.appendChild(tdMoeda);

    preencherLinha(tr, formatMoeda(ultimo.valor_compra), true);
    preencherLinha(tr, formatMoeda(ultimo.valor_venda), true);

    const tdVariacao = document.createElement("td");
    tdVariacao.setAttribute("data-numeric", "");
    tdVariacao.textContent = `${variacao >= 0 ? "▲" : "▼"} ${Math.abs(variacao).toFixed(2)}%`;
    tdVariacao.style.color = variacao >= 0 ? "var(--bt-success)" : "var(--bt-danger)";
    tr.appendChild(tdVariacao);

    tbody.appendChild(tr);
  });
}

function renderChartComparativo(container, legendContainer, series) {
  container.innerHTML = "";
  legendContainer.innerHTML = "";

  const W = 700;
  const H = 280;
  const margin = { top: 16, right: 16, bottom: 28, left: 56 };
  const innerW = W - margin.left - margin.right;
  const innerH = H - margin.top - margin.bottom;

  const normalizadas = series.map((s) => {
    const base = s.pontos[0].valor_compra;
    return {
      moeda: s.moeda,
      pontos: s.pontos.map((p) => ({
        data_cotacao: p.data_cotacao,
        variacao: base ? ((p.valor_compra - base) / base) * 100 : 0,
      })),
    };
  });

  const todasVariacoes = normalizadas.flatMap((s) => s.pontos.map((p) => p.variacao));
  const minVal = Math.min(0, ...todasVariacoes);
  const maxVal = Math.max(0, ...todasVariacoes);
  const pad = (maxVal - minVal) * 0.15 || 1;
  const yMin = minVal - pad;
  const yMax = maxVal + pad;

  const xFor = (i, total) => margin.left + (total <= 1 ? innerW / 2 : (i / (total - 1)) * innerW);
  const yFor = (v) => margin.top + innerH - ((v - yMin) / (yMax - yMin)) * innerH;

  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("width", "100%");
  svg.style.display = "block";

  const NUM_TICKS = 4;
  for (let t = 0; t <= NUM_TICKS; t++) {
    const v = yMin + ((yMax - yMin) * t) / NUM_TICKS;
    const y = yFor(v);

    const linha = document.createElementNS(SVG_NS, "line");
    linha.setAttribute("x1", String(margin.left));
    linha.setAttribute("x2", String(W - margin.right));
    linha.setAttribute("y1", String(y));
    linha.setAttribute("y2", String(y));
    linha.setAttribute("stroke", "var(--bt-border)");
    linha.setAttribute("stroke-width", "1");
    svg.appendChild(linha);

    const rotulo = document.createElementNS(SVG_NS, "text");
    rotulo.setAttribute("x", String(margin.left - 8));
    rotulo.setAttribute("y", String(y + 3));
    rotulo.setAttribute("text-anchor", "end");
    rotulo.setAttribute("font-size", "10");
    rotulo.setAttribute("font-family", "var(--bt-font-mono)");
    rotulo.setAttribute("fill", "var(--bt-text-subtle)");
    rotulo.textContent = `${v.toFixed(1)}%`;
    svg.appendChild(rotulo);
  }

  let referencia = normalizadas[0];
  normalizadas.forEach((s, indice) => {
    if (s.pontos.length > referencia.pontos.length) referencia = s;

    const cor = PALETA_COMPARACAO[indice % PALETA_COMPARACAO.length];
    const total = s.pontos.length;
    const d = s.pontos.map((p, i) => `${i === 0 ? "M" : "L"} ${xFor(i, total)} ${yFor(p.variacao)}`).join(" ");

    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", cor);
    path.setAttribute("stroke-width", "2");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    svg.appendChild(path);

    const ultimo = total - 1;
    const ponto = document.createElementNS(SVG_NS, "circle");
    ponto.setAttribute("cx", String(xFor(ultimo, total)));
    ponto.setAttribute("cy", String(yFor(s.pontos[ultimo].variacao)));
    ponto.setAttribute("r", "3.5");
    ponto.setAttribute("fill", cor);
    svg.appendChild(ponto);

    const item = document.createElement("span");
    item.className = "app-chart-legend__item";
    const chave = document.createElement("span");
    chave.className = "app-chart-legend__key";
    chave.style.background = cor;
    item.appendChild(chave);
    item.appendChild(document.createTextNode(s.moeda));
    legendContainer.appendChild(item);
  });

  [0, referencia.pontos.length - 1].forEach((i, indice) => {
    if (indice === 1 && referencia.pontos.length === 1) return;
    const rotulo = document.createElementNS(SVG_NS, "text");
    rotulo.setAttribute("x", String(xFor(i, referencia.pontos.length)));
    rotulo.setAttribute("y", String(H - 8));
    rotulo.setAttribute("text-anchor", i === 0 ? "start" : "end");
    rotulo.setAttribute("font-size", "10");
    rotulo.setAttribute("font-family", "var(--bt-font-mono)");
    rotulo.setAttribute("fill", "var(--bt-text-subtle)");
    rotulo.textContent = formatDataCurta(referencia.pontos[i].data_cotacao);
    svg.appendChild(rotulo);
  });

  container.appendChild(svg);
}

/* ==========================================================================
   View: conversão de moedas
   Calculadora simples (taxa média compra/venda, via BRL como ponte) que
   grava cada conversão feita no histórico do usuário.
   ========================================================================== */

async function popularSelectsConversao() {
  const origem = document.getElementById("conversao-origem");
  const destino = document.getElementById("conversao-destino");

  [origem, destino].forEach((select) => {
    select.innerHTML = "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.disabled = true;
    placeholder.selected = true;
    placeholder.textContent = "Selecione";
    select.appendChild(placeholder);

    const optBRL = document.createElement("option");
    optBRL.value = "BRL";
    optBRL.textContent = "BRL — Real brasileiro";
    select.appendChild(optBRL);
  });

  const moedas = await carregarMoedas();
  moedas.forEach((m) => {
    [origem, destino].forEach((select) => {
      const option = document.createElement("option");
      option.value = m.codigo;
      option.textContent = `${m.codigo} — ${m.nome}`;
      select.appendChild(option);
    });
  });

  origem.value = "USD";
  destino.value = "BRL";
}

async function carregarHistoricoConversoes() {
  const tbody = document.getElementById("conversao-historico-body");
  tbody.innerHTML = "";

  try {
    const historico = await api.listarConversoes();
    if (historico.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 6;
      td.textContent = "Nenhuma conversão feita ainda.";
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    historico.forEach((c) => {
      const tr = document.createElement("tr");
      preencherLinha(tr, formatDataHora(c.criado_em));
      preencherLinha(tr, c.moeda_origem);
      preencherLinha(tr, c.moeda_destino);
      preencherLinha(tr, formatMoeda(c.valor_origem), true);
      preencherLinha(tr, formatMoeda(c.valor_destino), true);
      preencherLinha(tr, formatMoeda(c.taxa_aplicada), true);
      tbody.appendChild(tr);
    });
  } catch (erro) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 6;
    td.textContent = erro.message;
    tr.appendChild(td);
    tbody.appendChild(tr);
  }
}

async function aoSubmeterConversao(evento) {
  evento.preventDefault();
  const valor = parseFloat(document.getElementById("conversao-valor").value);
  const moedaOrigem = document.getElementById("conversao-origem").value;
  const moedaDestino = document.getElementById("conversao-destino").value;
  const alertaBox = document.getElementById("conversao-alert");
  const resultadoBox = document.getElementById("conversao-resultado");
  const botao = document.getElementById("btn-converter");

  clearAlert(alertaBox);
  resultadoBox.classList.add("app-hidden");

  if (moedaOrigem === moedaDestino) {
    renderAlert(alertaBox, "Escolha duas moedas diferentes para converter.");
    return;
  }

  botao.setAttribute("aria-busy", "true");
  botao.disabled = true;

  try {
    const conversao = await api.criarConversao({
      moeda_origem: moedaOrigem,
      moeda_destino: moedaDestino,
      valor,
    });

    document.getElementById("conversao-resultado-valor").textContent =
      `${formatMoeda(conversao.valor_origem)} ${conversao.moeda_origem} = ${formatMoeda(conversao.valor_destino)} ${conversao.moeda_destino}`;
    document.getElementById("conversao-resultado-taxa").textContent =
      `Taxa aplicada: 1 ${conversao.moeda_origem} = ${formatMoeda(conversao.taxa_aplicada)} ${conversao.moeda_destino}`;
    resultadoBox.classList.remove("app-hidden");

    await carregarHistoricoConversoes();
  } catch (erro) {
    renderAlert(alertaBox, erro.message);
  } finally {
    botao.removeAttribute("aria-busy");
    botao.disabled = false;
  }
}

async function abrirConversao() {
  await popularSelectsConversao();
  await carregarHistoricoConversoes();
}

/* ==========================================================================
   View: login
   ========================================================================== */

async function aoSubmeterLogin(evento) {
  evento.preventDefault();
  const email = document.getElementById("login-email").value.trim();
  const senha = document.getElementById("login-senha").value;
  const alertaBox = document.getElementById("login-alert");
  const botao = document.getElementById("btn-login-submit");

  clearAlert(alertaBox);
  botao.setAttribute("aria-busy", "true");
  botao.disabled = true;

  try {
    const resultado = await api.login(email, senha);
    salvarToken(resultado.access_token);
    document.getElementById("form-login").reset();
    window.location.hash = "#/dashboard";
  } catch (erro) {
    renderAlert(alertaBox, erro.message);
  } finally {
    botao.removeAttribute("aria-busy");
    botao.disabled = false;
  }
}

function aoClicarSair() {
  limparToken();
  itemsCache = [];
  moedasCache = null;
  pararRelogioProximaColeta();
  window.location.hash = "#/login";
}

/* ==========================================================================
   Inicialização e wiring de eventos
   ========================================================================== */

function definirDatasPadraoConsulta() {
  const hoje = new Date();
  const seteDiasAtras = new Date(hoje);
  seteDiasAtras.setDate(hoje.getDate() - 7);
  const paraIso = (d) => d.toISOString().slice(0, 10);
  seletoresData.consultaFim.definirValor(paraIso(hoje));
  seletoresData.consultaInicio.definirValor(paraIso(seteDiasAtras));
}

function wireEventos() {
  document.querySelectorAll("[data-route]").forEach((botao) => {
    botao.addEventListener("click", () => { window.location.hash = botao.dataset.route; });
  });

  document.getElementById("btn-open-create").addEventListener("click", abrirModalCriar);
  document.querySelectorAll("[data-open-create]").forEach((el) => el.addEventListener("click", abrirModalCriar));
  document.querySelectorAll("[data-close-modal]").forEach((el) => el.addEventListener("click", fecharModalCriar));
  document.getElementById("form-create").addEventListener("submit", aoSubmeterCriacao);

  // Sugere o nome da moeda escolhida, se o usuário ainda não digitou nada.
  document.getElementById("create-moeda").addEventListener("change", (evento) => {
    const campoNome = document.getElementById("create-nome");
    const opcao = evento.target.selectedOptions[0];
    if (!campoNome.value.trim() && opcao && opcao.dataset.nome) {
      campoNome.value = opcao.dataset.nome;
    }
  });

  document.getElementById("btn-collect").addEventListener("click", aoClicarColetar);

  // Abas Gráfico/Tabela (só as do detalhe do item - as de login usam
  // data-login-tab e têm wiring próprio, não essa alternância genérica).
  document.querySelectorAll("#view-detail .bt-tab[data-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#view-detail .bt-tab[data-tab]").forEach((t) => t.setAttribute("aria-selected", "false"));
      tab.setAttribute("aria-selected", "true");
      const alvo = tab.dataset.tab;
      document.querySelectorAll("[data-tab-panel]").forEach((painel) => {
        painel.classList.toggle("app-hidden", painel.dataset.tabPanel !== alvo);
      });
    });
  });

  document.getElementById("form-consulta").addEventListener("submit", aoSubmeterConsulta);

  document.getElementById("form-comparar").addEventListener("submit", aoSubmeterComparar);
  document.getElementById("comparar-filtro").addEventListener("input", () => {
    carregarMoedas().then(renderizarListaComparar);
  });

  document.getElementById("form-conversao").addEventListener("submit", aoSubmeterConversao);

  document.getElementById("form-login").addEventListener("submit", aoSubmeterLogin);
  document.getElementById("btn-logout").addEventListener("click", aoClicarSair);

  window.addEventListener("hashchange", router);

  wireSidebar();
}

function wireSidebar() {
  const toggle = document.getElementById("btn-toggle-sidebar");
  const sidebar = document.getElementById("app-sidebar");
  const scrim = document.getElementById("sidebar-scrim");

  function fechar() {
    sidebar.removeAttribute("data-open");
    scrim.removeAttribute("data-open");
    toggle.setAttribute("aria-expanded", "false");
  }
  function abrir() {
    sidebar.setAttribute("data-open", "true");
    scrim.setAttribute("data-open", "true");
    toggle.setAttribute("aria-expanded", "true");
  }

  toggle.addEventListener("click", () => {
    if (sidebar.getAttribute("data-open") === "true") fechar();
    else abrir();
  });
  scrim.addEventListener("click", fechar);
  document.querySelectorAll("#app-sidebar [data-route]").forEach((el) => el.addEventListener("click", fechar));
  window.addEventListener("hashchange", fechar);
}

document.addEventListener("DOMContentLoaded", () => {
  seletoresData.consultaInicio = criarSeletorData("consulta-inicio");
  seletoresData.consultaFim = criarSeletorData("consulta-fim");
  seletoresData.compararInicio = criarSeletorData("comparar-inicio");
  seletoresData.compararFim = criarSeletorData("comparar-fim");

  wireEventos();
  definirDatasPadraoConsulta();
  router();
  if (estaAutenticado()) carregarMoedas(); // pré-carrega, pro modal e as abas de moeda abrirem já populados
});
