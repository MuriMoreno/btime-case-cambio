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
  registrar: (email, senha) => apiRequest("/auth/registrar", { method: "POST", body: JSON.stringify({ email, senha }) }),
};

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
  const hash = window.location.hash || "#/items";

  // Guarda de autenticação: sem token, só a tela de login é alcançável.
  if (hash !== "#/login" && !estaAutenticado()) {
    window.location.hash = "#/login";
    return;
  }
  if (hash === "#/login" && estaAutenticado()) {
    window.location.hash = "#/items";
    return;
  }

  document.getElementById("navbar-links").classList.toggle("app-hidden", hash === "#/login");

  document.querySelectorAll("[data-nav]").forEach((botao) => {
    const rotaAtiva = hash.startsWith("#/items") ? "#/items" : hash;
    botao.setAttribute("aria-current", botao.dataset.route === rotaAtiva ? "page" : "false");
  });

  ["view-login", "view-items", "view-detail", "view-consulta"].forEach((id) => {
    document.getElementById(id).classList.add("app-hidden");
  });

  if (hash === "#/login") {
    document.getElementById("view-login").classList.remove("app-hidden");
  } else if (hash.startsWith("#/items/")) {
    const id = hash.split("/")[2];
    document.getElementById("view-detail").classList.remove("app-hidden");
    carregarDetalheItem(id);
  } else if (hash === "#/consulta") {
    document.getElementById("view-consulta").classList.remove("app-hidden");
    carregarMoedasConsultaSelect();
  } else {
    document.getElementById("view-items").classList.remove("app-hidden");
    carregarListaItens();
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

  try {
    const historico = await api.historico(id);
    renderizarTabelaHistorico(historico);
    renderChart(document.getElementById("chart-container"), historico, document.getElementById("chart-empty"));
  } catch (erro) {
    renderAlert(alertaBox, erro.message);
  }
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

function renderizarTabelaHistorico(historico) {
  const tbody = document.getElementById("history-table-body");
  tbody.innerHTML = "";

  if (historico.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 4;
    td.textContent = "Sem coletas ainda.";
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }

  [...historico].reverse().forEach((coleta) => {
    const tr = document.createElement("tr");
    preencherLinha(tr, formatDataCurta(coleta.data_cotacao));
    preencherLinha(tr, formatMoeda(coleta.valor_compra), true);
    preencherLinha(tr, formatMoeda(coleta.valor_venda), true);
    preencherLinha(tr, formatDataHora(coleta.coletado_em));
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

async function carregarMoedasConsultaSelect() {
  const select = document.getElementById("consulta-moeda");
  const dica = document.getElementById("consulta-moeda-hint");

  select.disabled = true;
  select.innerHTML = '<option value="" disabled selected>Carregando…</option>';
  dica.textContent = "";

  let itens;
  try {
    itens = await api.listarItens();
    itemsCache = itens; // mantém o cache das outras views atualizado também
  } catch (erro) {
    select.innerHTML = '<option value="" disabled selected>Não foi possível carregar as moedas</option>';
    dica.textContent = erro.message;
    return;
  }

  select.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.disabled = true;
  placeholder.selected = true;

  if (itens.length === 0) {
    placeholder.textContent = "Nenhuma moeda cadastrada ainda";
    select.appendChild(placeholder);
    dica.textContent = "Cadastre um item na tela de Itens para poder consultá-lo aqui.";
    return;
  }

  placeholder.textContent = "Selecione a moeda";
  select.appendChild(placeholder);

  itens.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.moeda;
    option.textContent = `${item.moeda} — ${item.nome}`;
    select.appendChild(option);
  });
  select.disabled = false;
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
  botao.setAttribute("aria-busy", "true");
  botao.disabled = true;

  try {
    const dados = await api.consultaLivre(moeda, dataInicio, dataFim);
    if (dados.length === 0) {
      vazio.classList.remove("app-hidden");
    } else {
      renderizarTabelaConsulta(dados);
      renderChart(document.getElementById("consulta-chart-container"), dados, null);
      resultado.classList.remove("app-hidden");
    }
  } catch (erro) {
    renderAlert(alertaBox, erro.message);
  } finally {
    botao.removeAttribute("aria-busy");
    botao.disabled = false;
  }
}

function renderizarTabelaConsulta(dados) {
  const tbody = document.getElementById("consulta-table-body");
  tbody.innerHTML = "";
  [...dados].reverse().forEach((c) => {
    const tr = document.createElement("tr");
    preencherLinha(tr, formatDataCurta(c.data_cotacao));
    preencherLinha(tr, formatMoeda(c.valor_compra), true);
    preencherLinha(tr, formatMoeda(c.valor_venda), true);
    tbody.appendChild(tr);
  });
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
   View: login
   ========================================================================== */

let modoLogin = "entrar";

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
    if (modoLogin === "criar") {
      await api.registrar(email, senha);
    }
    const resultado = await api.login(email, senha);
    salvarToken(resultado.access_token);
    document.getElementById("form-login").reset();
    window.location.hash = "#/items";
  } catch (erro) {
    renderAlert(alertaBox, erro.message);
  } finally {
    botao.removeAttribute("aria-busy");
    botao.disabled = false;
  }
}

function aoTrocarModoLogin(tab) {
  modoLogin = tab.dataset.loginTab === "criar" ? "criar" : "entrar";
  document.querySelectorAll("[data-login-tab]").forEach((t) => t.setAttribute("aria-selected", "false"));
  tab.setAttribute("aria-selected", "true");
  document.getElementById("btn-login-submit").textContent =
    modoLogin === "criar" ? "Criar conta e entrar" : "Entrar";
  clearAlert(document.getElementById("login-alert"));
}

function aoClicarSair() {
  limparToken();
  itemsCache = [];
  moedasCache = null;
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
  document.getElementById("consulta-fim").value = paraIso(hoje);
  document.getElementById("consulta-inicio").value = paraIso(seteDiasAtras);
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

  document.getElementById("form-login").addEventListener("submit", aoSubmeterLogin);
  document.querySelectorAll("[data-login-tab]").forEach((tab) => {
    tab.addEventListener("click", () => aoTrocarModoLogin(tab));
  });
  document.getElementById("btn-logout").addEventListener("click", aoClicarSair);

  window.addEventListener("hashchange", router);
}

document.addEventListener("DOMContentLoaded", () => {
  wireEventos();
  definirDatasPadraoConsulta();
  router();
  if (estaAutenticado()) carregarMoedas(); // pré-carrega, pro modal abrir já populado
});
