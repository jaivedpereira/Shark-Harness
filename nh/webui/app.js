/* ══════════ Shark Harness — front ══════════ */
const $ = (s) => document.querySelector(s);
const el = (t, c, h) => { const n = document.createElement(t); if (c) n.className = c; if (h !== undefined) n.innerHTML = h; return n; };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));

const RISK = {
  safe:   { cls: "r-safe",   label: "leitura" },
  write:  { cls: "r-write",  label: "escreve" },
  exec:   { cls: "r-exec",   label: "executa" },
  danger: { cls: "r-danger", label: "apaga" },
};

let STATE = { tools: [], jobs: [], audit: [] };
let CONFIG = null;
let filtroRisco = "all";

async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  return r.json();
}

/* ───────────────── estado geral ───────────────── */
async function loadState() {
  try {
    STATE = await api("/api/state");
  } catch (e) {
    $("#llmText").textContent = "sem conexão com o servidor";
    return;
  }
  const p = STATE.platform || {};
  $("#pillPlat").textContent = `${p.name || "?"}`;
  $("#pillTools").textContent = `${STATE.tools.length} ferramentas · risco ≤ ${STATE.max_risk}`;

  const llm = STATE.llm || {};
  $("#llmState").className = "dot " + (llm.configured ? "ok" : "err");
  const mdot = $("#mDot");
  if (mdot) mdot.className = "dot " + (llm.configured ? "ok" : "err");
  // nome curto do modelo para não quebrar linha na barra lateral
  const bruto = String(llm.model || "").split("/").pop().replace(/:free$/, "");
  const curto = bruto.length > 18 ? bruto.slice(0, 17) + "…" : bruto;
  $("#llmText").textContent = llm.configured ? `IA ligada · ${curto}` : "IA desligada";
  $("#llmLine").title = llm.model || "";
  $("#llmText").title = llm.configured ? llm.model : "abra Configurações para colar a chave";

  renderTools();
  renderJobs();
  renderAudit();
  $("#sysInfo").textContent = STATE.sysinfo || "(vazio)";
}

/* ───────────────── navegação ───────────────── */
function irPara(view) {
  // a barra lateral (PC) e a tabbar (celular) mostram a MESMA view
  document.querySelectorAll(".nav-item, .tab").forEach((n) => {
    n.classList.toggle("active", n.dataset.view === view);
  });
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  const alvo = $("#view-" + view);
  if (alvo) alvo.classList.add("active");
  const rolagem = $(".main");
  if (rolagem) rolagem.scrollTop = 0;
  window.scrollTo(0, 0);

  if (view === "config") carregarConfig();
  else if (view === "tools") carregarLoja();
  else if (view === "audit" || view === "cron") loadState();
}

document.addEventListener("click", (e) => {
  const b = e.target.closest(".nav-item, .tab");
  if (b && b.dataset.view) irPara(b.dataset.view);
});

/* ───────────────── ferramentas ───────────────── */
function renderTools() {
  const grid = $("#toolGrid");
  const q = $("#toolSearch").value.toLowerCase().trim();
  grid.innerHTML = "";
  const lista = STATE.tools.filter((t) => {
    if (filtroRisco !== "all" && t.risk !== filtroRisco) return false;
    if (!q) return true;
    return (t.name + " " + t.description + " " + t.plugin).toLowerCase().includes(q);
  });
  if (!lista.length) { grid.append(el("p", "hint", "nenhuma ferramenta bate com o filtro")); return; }
  lista.forEach((t) => {
    const r = RISK[t.risk] || RISK.safe;
    const card = el("article", "tool");
    card.innerHTML = `
      <h4><span>${esc(t.name)}</span><span class="tag ${r.cls}">${r.label}</span></h4>
      <p>${esc(t.description)}</p>
      <div class="plugin">${esc(t.plugin)}</div>`;
    card.addEventListener("click", () => openTool(t));
    grid.append(card);
  });
}
$("#toolSearch").addEventListener("input", renderTools);
$("#riskChips").addEventListener("click", (e) => {
  const c = e.target.closest(".chip");
  if (!c) return;
  document.querySelectorAll("#riskChips .chip").forEach((x) => x.classList.remove("active"));
  c.classList.add("active");
  filtroRisco = c.dataset.risk;
  renderTools();
});

/* ── modal: formulário gerado do JSON Schema ── */
let toolAtual = null;
function openTool(t) {
  toolAtual = t;
  const r = RISK[t.risk] || RISK.safe;
  $("#mTitle").textContent = t.name;
  $("#mDesc").textContent = t.description;
  $("#mRisk").innerHTML = `risco: <span class="tag ${r.cls}">${r.label}</span>`;
  $("#mOut").textContent = "(sem saída ainda)";

  const form = $("#mForm");
  form.innerHTML = "";
  const props = (t.schema && t.schema.properties) || {};
  const req = new Set((t.schema && t.schema.required) || []);
  const nomes = Object.keys(props);
  if (!nomes.length) form.append(el("p", "mdesc", "esta ferramenta não precisa de argumentos"));

  nomes.forEach((k) => {
    const s = props[k] || {};
    const lab = el("label");
    lab.innerHTML = `<span>${esc(k)}${req.has(k) ? " <b>*</b>" : ""}</span>`;
    if (s.type === "boolean") {
      const inp = el("input"); inp.type = "checkbox"; inp.id = "f_" + k;
      lab.append(inp);
    } else {
      const inp = el("input");
      inp.id = "f_" + k;
      inp.type = (s.type === "integer" || s.type === "number") ? "number" : "text";
      inp.placeholder = s.description || (req.has(k) ? "obrigatório" : "opcional");
      lab.append(inp);
      if (s.description) lab.append(el("small", "hint", esc(s.description)));
    }
    form.append(lab);
  });
  $("#modal").classList.add("open");
}
$("#mClose").addEventListener("click", () => $("#modal").classList.remove("open"));
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") $("#modal").classList.remove("open"); });

$("#mRun").addEventListener("click", async () => {
  if (!toolAtual) return;
  const props = (toolAtual.schema && toolAtual.schema.properties) || {};
  const args = {};
  for (const k of Object.keys(props)) {
    const inp = $("#f_" + k);
    if (!inp) continue;
    if (inp.type === "checkbox") args[k] = inp.checked;
    else if (inp.value !== "") args[k] = inp.type === "number" ? Number(inp.value) : inp.value;
  }
  const out = $("#mOut");
  out.textContent = "executando…";
  $("#mRun").disabled = true;
  try {
    const r = await api("/api/tool", { method: "POST", body: { name: toolAtual.name, args } });
    out.textContent = r.result ?? JSON.stringify(r);
  } catch (e) {
    out.textContent = "erro de rede: " + e;
  }
  $("#mRun").disabled = false;
});

/* ───────────────── agente ───────────────── */
const chat = $("#chat");

/* preferências de exibição (ficam no navegador) */
const PREF = {
  get ocultar() {
    return localStorage.getItem("nh_ocultar_passos");
  },
  set ocultar(v) {
    localStorage.setItem("nh_ocultar_passos", v ? "1" : "0");
  },
  // padrão: mostra o raciocínio; esconde só se o usuário pediu
  get escondido() {
    return localStorage.getItem("nh_ocultar_passos") === "1";
  },
};

function fmtNum(n) {
  return n >= 1000 ? (n / 1000).toFixed(1).replace(".", ",") + "k" : String(n);
}

function addMsg(quem, texto) {
  const m = el("div", "msg " + (quem === "user" ? "user" : "bot"));
  m.append(el("div", "bubble", `<strong>${quem === "user" ? "você" : "shark"}</strong><p>${esc(texto)}</p>`));
  chat.append(m);
  chat.scrollTop = chat.scrollHeight;
  return m;
}

/* Um "turno" = cabeçalho (resumo + botão) + passos + resposta.
   Assim os passos podem ser escondidos sem perder a resposta. */
function addTurn() {
  const t = el("div", "turn" + (PREF.escondido ? " closed" : ""));
  const head = el("div", "turn-head");
  const btn = el("button", "turn-toggle");
  btn.innerHTML = '<span class="chev"></span><span class="ttxt">pensando…</span>';
  head.append(btn);
  const steps = el("div", "steps");
  const meta = el("div", "turn-meta");
  const body = el("div", "turn-body");
  t.append(head, steps, body, meta);
  btn.addEventListener("click", () => {
    t.classList.toggle("closed");
    PREF.ocultar = t.classList.contains("closed");
  });
  chat.append(t);
  chat.scrollTop = chat.scrollHeight;
  return { t, steps, body, meta, btn };
}

function resumirTurno(turno, dados) {
  const t = turno.t;
  const n = t.querySelectorAll(".step").length;
  const d = dados || {};
  const txt = t.querySelector(".ttxt");
  const partes = [];
  if (n) partes.push(`${n} passo${n > 1 ? "s" : ""}`);
  if (d.ferramentas && d.ferramentas.length) {
    partes.push(`${d.ferramentas.length} ${d.ferramentas.length === 1 ? "ferramenta" : "ferramentas"}`);
  }
  if (d.total_tokens) partes.push(`${fmtNum(d.total_tokens)} tokens`);
  if (txt) txt.textContent = partes.length ? partes.join(" · ") : "resposta";
  if (d.total_tokens) {
    const nomeModelo = String(d.modelo || "").split("/").pop().replace(/:free$/, "");
    const curto = nomeModelo.length > 20 ? nomeModelo.slice(0, 19) + "…" : nomeModelo;
    turno.meta.innerHTML =
      `<span title="tokens enviados ao modelo">↑ ${fmtNum(d.prompt_tokens || 0)}</span>` +
      `<span title="tokens gerados pelo modelo">↓ ${fmtNum(d.completion_tokens || 0)}</span>` +
      `<span title="chamadas ao modelo">${d.rodadas || 1} rodada(s)</span>` +
      `<span title="${esc(nomeModelo)}">${esc(curto)}</span>`;
  }
  if (d.ferramentas && d.ferramentas.length) {
    turno.t.appendChild(el("div", "turn-tools", d.ferramentas.join(" · ")));
  }
}

function addStep(box, tipo, nome, detalhe) {
  if (tipo === "info") {
    box.append(el("div", "step", `<div class="sname">${esc(nome)}</div><div class="sarg">${esc(detalhe)}</div>`));
  } else if (tipo === "chamada") {
    box.append(el("div", "step", `<div class="sname">→ ${esc(nome)}</div><div class="sarg">${esc(detalhe)}</div>`));
  } else if (tipo === "resultado") {
    const s = el("div", "step", `<div class="sname">✓ ${esc(nome)}</div><div class="sarg">clique para ver a saída</div>`);
    s.append(el("pre", "", esc(detalhe)));
    s.addEventListener("click", () => s.classList.toggle("open"));
    box.append(s);
  } else if (tipo === "erro") {
    box.append(el("div", "step err", `<div class="sname">erro</div><div class="sarg">${esc(detalhe)}</div>`));
  }
  chat.scrollTop = chat.scrollHeight;
}

$("#formAgent").addEventListener("submit", async (e) => {
  e.preventDefault();
  const ta = $("#prompt");
  const texto = ta.value.trim();
  if (!texto) return;
  ta.value = "";
  ta.style.height = "auto";
  addMsg("user", texto);

  const turno = addTurn();
  const sp = el("div", "spinner", "<i></i><i></i><i></i>");
  turno.steps.append(sp);
  chat.scrollTop = chat.scrollHeight;
  const btn = $("#formAgent").querySelector(".primary");
  btn.disabled = true;

  try {
    const r = await api("/api/agent", { method: "POST", body: { prompt: texto } });
    sp.remove();
    let tokens = null;
    (r.steps || []).forEach((s) => {
      if (s.tipo === "resposta") return;
      if (s.tipo === "tokens") {
        try {
          tokens = JSON.parse(s.detalhe);
        } catch (_) {
          tokens = null;
        }
        return;
      }
      addStep(turno.steps, s.tipo, s.nome, s.detalhe);
    });
    turno.body.append(el("div", "bubble", `<strong>shark</strong><p>${esc(r.answer || "(sem resposta)")}</p>`));
    resumirTurno(turno, tokens);
  } catch (err) {
    sp.remove();
    addStep(turno.steps, "erro", "rede", String(err));
    resumirTurno(turno, null);
  }
  btn.disabled = false;
  loadState();
});

$("#suggest").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  $("#prompt").value = b.textContent;
  $("#formAgent").dispatchEvent(new Event("submit"));
});

const ta = $("#prompt");
ta.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("#formAgent").dispatchEvent(new Event("submit"));
  }
});
ta.addEventListener("input", () => {
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 150) + "px";
});

/* ───────────────── agendador ───────────────── */
function renderJobs() {
  const wrap = $("#jobList");
  wrap.innerHTML = "";
  if (!STATE.jobs.length) { wrap.append(el("p", "hint", "nenhuma tarefa agendada ainda")); return; }
  STATE.jobs.forEach((j) => {
    const card = el("article", "job" + (j.enabled ? "" : " off"));
    card.innerHTML = `
      <div>
        <h4>${j.enabled ? "▶" : "❚❚"} ${esc(j.name)} <code>[${esc(j.id)}]</code></h4>
        <div class="meta">quando: <code>${esc(j.cron)}</code> — ${esc(j.human || "")}</div>
        <div class="meta">o quê: <code>${esc(j.kind)} → ${esc(j.payload)}</code></div>
        <div class="meta">execuções: ${j.runs} · último: ${esc(j.last_run || "nunca")} ${j.last_status ? "(" + esc(j.last_status) + ")" : ""}</div>
      </div>
      <div class="acts">
        <button class="act" data-a="run" data-id="${esc(j.id)}">rodar agora</button>
        <button class="act" data-a="pause" data-id="${esc(j.id)}">${j.enabled ? "pausar" : "ativar"}</button>
        <button class="act red" data-a="rm" data-id="${esc(j.id)}">remover</button>
      </div>`;
    wrap.append(card);
  });
}

$("#jobList").addEventListener("click", async (e) => {
  const b = e.target.closest(".act");
  if (!b) return;
  b.disabled = true;
  await api("/api/cron", { method: "POST", body: { action: b.dataset.a, id: b.dataset.id } });
  const eraRun = b.dataset.a === "run";
  await loadState();
  if (eraRun) {
    const j = STATE.jobs.find((x) => x.id === b.dataset.id);
    if (j) addMsg("bot", `tarefa "${j.name}" executada: ${j.last_status || "ok"}`);
  }
});

$("#cKind").addEventListener("change", (e) => {
  const shell = e.target.value === "shell";
  $("#wrapPayload").querySelector("input").placeholder = shell
    ? "tar -czf ~/bkp.tgz ~/shark-workspace" : "sysinfo_report";
  $("#wrapArgs").style.display = shell ? "none" : "flex";
});
$("#wrapArgs").style.display = "none";

$("#cExplain").addEventListener("click", async () => {
  const cron = $("#cCron").value.trim();
  if (!cron) { $("#cHint").textContent = "digite a expressão cron primeiro"; return; }
  const r = await api("/api/cron", { method: "POST", body: { action: "explain", cron } });
  $("#cHint").textContent = r.result || "";
});

$("#cAdd").addEventListener("click", async () => {
  const body = {
    action: "add",
    name: $("#cName").value.trim(),
    cron: $("#cCron").value.trim(),
    kind: $("#cKind").value,
    payload: $("#cPayload").value.trim(),
    args: $("#cArgs").value.trim(),
  };
  if (!body.name || !body.cron || !body.payload) {
    $("#cHint").textContent = "preencha nome, cron e o comando/ferramenta";
    return;
  }
  const r = await api("/api/cron", { method: "POST", body });
  $("#cHint").textContent = r.result || "";
  $("#cName").value = $("#cCron").value = $("#cPayload").value = $("#cArgs").value = "";
  await loadState();
});

/* ───────────────── auditoria ───────────────── */
function renderAudit() {
  const tb = $("#auditTable").querySelector("tbody");
  tb.innerHTML = "";
  if (!STATE.audit.length) {
    tb.append(el("tr", "", '<td colspan="4" class="t">log vazio — nada executado ainda</td>'));
    return;
  }
  STATE.audit.slice().reverse().forEach((a) => {
    const cls = a.status === "ok" ? "b-ok" : a.status === "blocked" ? "b-blocked" : "b-error";
    tb.append(el("tr", "",
      `<td class="t">${esc(a.ts)}</td><td><span class="badge ${cls}">${esc(a.status)}</span></td>
       <td class="n">${esc(a.tool)}</td><td>${esc(a.detail)}</td>`));
  });
}

/* ───────────────── configurações (provedor + chave) ───────────────── */
async function carregarConfig() {
  const st = $("#cfgStatus");
  st.className = "status";
  st.textContent = "carregando…";
  try {
    CONFIG = await api("/api/config");
  } catch (e) {
    st.className = "status err";
    st.textContent = "não consegui ler a configuração";
    return;
  }
  const sel = $("#cfgProvider");
  sel.innerHTML = "";
  (CONFIG.providers || []).forEach((p) => {
    const o = el("option", "", esc(p.label));
    o.value = p.id;
    sel.append(o);
  });

  const a = CONFIG.atual || {};
  sel.value = a.provider || "openrouter";
  $("#cfgUrl").value = a.url || "";
  $("#cfgModel").value = a.model || "";
  $("#cfgRisk").value = a.max_risk || "exec";
  $("#cfgRounds").value = a.max_rounds || 14;
  $("#cfgWhere").textContent = CONFIG.arquivo || "—";
  atualizarDatalist(a.provider);

  $("#cfgKey").value = "";
  $("#cfgKey").placeholder = a.tem_chave
    ? `chave salva (${a.chave_dica}) — digite outra para trocar`
    : "cole sua chave aqui";

  st.textContent = a.tem_chave
    ? `IA ligada · ${a.label}${a.origem === "ambiente" ? " (chave vinda do ambiente)" : ""}`
    : "IA desligada — cole a chave e salve";
  st.className = "status" + (a.tem_chave ? " ok" : "");
}

function atualizarDatalist(pid) {
  const dl = $("#cfgModels");
  dl.innerHTML = "";
  const p = (CONFIG.providers || []).find((x) => x.id === pid);
  (p && p.models ? p.models : []).forEach((m) => {
    const o = el("option"); o.value = m; dl.append(o);
  });
  $("#cfgHint").innerHTML = p && p.hint
    ? esc(p.hint) + (p.key_url ? ` — <a href="${esc(p.key_url)}" target="_blank" rel="noopener">pegar chave</a>` : "")
    : "";
}

$("#cfgProvider").addEventListener("change", (e) => {
  const pid = e.target.value;
  const p = (CONFIG.providers || []).find((x) => x.id === pid);
  if (p && p.url) $("#cfgUrl").value = p.url;
  if (p && p.models && p.models.length) $("#cfgModel").value = p.models[0];
  atualizarDatalist(pid);
});

$("#cfgSave").addEventListener("click", async () => {
  const st = $("#cfgStatus");
  st.className = "status";
  st.textContent = "salvando…";
  const r = await api("/api/config", {
    method: "POST",
    body: {
      provider: $("#cfgProvider").value,
      url: $("#cfgUrl").value.trim(),
      model: $("#cfgModel").value.trim(),
      api_key: $("#cfgKey").value.trim(),
      max_risk: $("#cfgRisk").value,
      max_rounds: $("#cfgRounds").value,
    },
  });
  if (!r.ok) {
    st.className = "status err";
    st.textContent = r.erro || "não deu para salvar";
    return;
  }
  st.className = "status ok";
  st.textContent = (r.msg || "salvo") + (r.aviso ? " · " + r.aviso : "");
  await carregarConfig();
  await loadState();
});

$("#cfgTest").addEventListener("click", async () => {
  const st = $("#cfgStatus");
  const b = $("#cfgTest");
  st.className = "status";
  st.textContent = "testando…";
  b.disabled = true;
  try {
    const r = await api("/api/config/testar", { method: "POST", body: {} });
    st.className = "status " + (r.ok ? "ok" : "err");
    st.textContent = r.ok ? r.msg : (r.erro || "falhou");
  } catch (e) {
    st.className = "status err";
    st.textContent = "erro de rede: " + e;
  }
  b.disabled = false;
});

$("#cfgRemoveKey").addEventListener("click", async () => {
  const st = $("#cfgStatus");
  st.className = "status";
  st.textContent = "removendo…";
  const r = await api("/api/config", {
    method: "POST",
    body: {
      provider: $("#cfgProvider").value,
      url: $("#cfgUrl").value.trim(),
      model: $("#cfgModel").value.trim(),
      max_risk: $("#cfgRisk").value,
      api_key: "remover",
    },
  });
  st.className = "status" + (r.ok ? " ok" : " err");
  st.textContent = r.ok ? "chave removida" : (r.erro || "não deu");
  await carregarConfig();
  await loadState();
});

/* ═══════════════════════ loja / marketplace ═══════════════════════ */
const RISCO_META = {
  safe: { icone: "🟢", rotulo: "só leitura", cor: "r-safe" },
  write: { icone: "🟡", rotulo: "escreve", cor: "r-write" },
  exec: { icone: "🟠", rotulo: "executa comando", cor: "r-exec" },
  danger: { icone: "🔴", rotulo: "apaga/perigoso", cor: "r-danger" },
};
let LOJA = { instalados: [], catalogo: [], kits: [] };

function riscoTag(r) {
  const m = RISCO_META[r] || RISCO_META.safe;
  return `<span class="rtag ${m.cor}">${m.icone} ${m.rotulo}</span>`;
}

async function carregarLoja() {
  try {
    LOJA = await api("/api/plugins");
  } catch (e) {
    LOJA = { instalados: [], catalogo: [], kits: [], erro: String(e) };
  }
  const badge = $("#lojaBadge");
  badge.textContent = (LOJA.catalogo || []).length;
  badge.style.display = (LOJA.catalogo || []).length ? "" : "none";
  renderLoja();
  renderPlugins();
}

function renderLoja() {
  /* kits */
  const kl = $("#kitList");
  kl.innerHTML = "";
  (LOJA.kits || []).forEach((k) => {
    const ja = (LOJA.instalados || []).map((x) => x.id);
    const faltam = (k.plugins || []).filter((p) => !ja.includes(p));
    const row = el("div", "kit");
    row.innerHTML =
      `<div class="kit-info"><strong>${esc(k.nome)}</strong><span>${esc(k.descricao || "")}</span>` +
      `<em>${(k.plugins || []).map(esc).join(" · ")}</em></div>`;
    const b = el("button", "primary small", faltam.length ? `instalar ${faltam.length}` : "instalado");
    b.disabled = !faltam.length;
    b.addEventListener("click", async () => {
      b.disabled = true;
      b.textContent = "instalando…";
      const r = await api("/api/plugins", { method: "POST", body: { acao: "kit", id: k.id } });
      toast(r.msg || r.erro || "pronto");
      await carregarLoja();
      await loadState();
    });
    row.append(b);
    kl.append(row);
  });

  /* catálogo */
  const g = $("#lojaGrid");
  g.innerHTML = "";
  const cat = LOJA.catalogo || [];
  if (!cat.length) {
    g.append(el("p", "hint", "Tudo do catálogo já está instalado. 🎉"));
    return;
  }
  cat.forEach((p) => {
    const c = el("div", "tcard loja-card");
    c.innerHTML =
      `<div class="tc-head"><span class="tname">${esc(p.nome)}</span>${riscoTag(p.risco_max)}</div>` +
      `<p class="tdesc">${esc(p.descricao || "")}</p>` +
      `<div class="tmeta">${(p.ferramentas || []).length} ferramentas · v${esc(p.versao || "?")} · ${esc(p.categoria || "")}</div>` +
      (p.requer && p.requer.length ? `<div class="tmeta aviso">precisa de: ${p.requer.map(esc).join(", ")}</div>` : "");
    const b = el("button", "primary small", "instalar");
    b.addEventListener("click", async () => {
      b.disabled = true;
      b.textContent = "instalando…";
      let r = await api("/api/plugins", { method: "POST", body: { acao: "instalar", id: p.id } });
      if (r.precisa_confiar) {
        const ok = confirm(
          `"${p.nome}" executa comandos no seu dispositivo (risco ${p.risco_max}).\n\n` +
          `Ele vai rodar com o MESMO poder que você. Leia o código antes de confiar.\n\n` +
          `Instalar assim mesmo?`
        );
        if (ok) r = await api("/api/plugins", { method: "POST", body: { acao: "instalar", id: p.id, confiar: true } });
        else {
          b.disabled = false;
          b.textContent = "instalar";
          return;
        }
      }
      toast(r.msg || r.erro || "pronto");
      await carregarLoja();
      await loadState();
    });
    c.append(b);
    g.append(c);
  });
}

function renderPlugins() {
  const box = $("#pluginList");
  box.innerHTML = "";
  const inst = LOJA.instalados || [];
  const todos = STATE.plugins || [];

  const linha = (m) => {
    const row = el("div", "prow");
    const ativo = m.ativo !== false;
    row.innerHTML =
      `<div class="prow-info"><strong>${esc(m.nome || m.id)}</strong>` +
      `<span>${esc(m.descricao || "")}</span>` +
      `<em>${m.id} · ${m.origem || "—"} · risco ${m.risco_max || "—"}` +
      `${m.ferramentas && m.ferramentas.length ? " · " + m.ferramentas.length + " ferramentas" : ""}` +
      `${m.quebrado ? " · ❌ quebrado" : ""}</em></div>`;
    if (m.origem === "instalado") {
      const apagar = el("button", "ghost small", "remover");
      apagar.addEventListener("click", async () => {
        if (!confirm(`Remover o plugin "${m.nome || m.id}"?`)) return;
        const r = await api("/api/plugins", { method: "POST", body: { acao: "remover", id: m.id } });
        toast(r.msg || r.erro || "pronto");
        await carregarLoja();
        await loadState();
      });
      row.append(apagar);
    }
    const sw = el("button", "switch" + (ativo ? " on" : ""), `<i></i>`);
    sw.title = ativo ? "desativar (não apaga)" : "ativar";
    sw.addEventListener("click", async () => {
      const r = await api("/api/plugins", {
        method: "POST",
        body: { acao: ativo ? "desativar" : "ativar", id: m.id },
      });
      toast(r.msg || r.erro || "pronto");
      await carregarLoja();
      await loadState();
    });
    row.append(sw);
    return row;
  };

  /* instalados pelo usuário primeiro */
  inst.forEach((m) => box.append(linha(m)));
  if (inst.length) box.append(el("div", "sep"));

  const embutidos = todos.filter((p) => !(p.origem === "instalado"));
  if (embutidos.length) {
    box.append(el("h4", "pgroup", "Vêm com o harness"));
    embutidos.sort((a, b) => String(a.id).localeCompare(String(b.id)));
    embutidos.forEach((m) => box.append(linha(m)));
  }
}

/* troca de aba dentro de Ferramentas */
$("#toolsSeg").addEventListener("click", (e) => {
  const b = e.target.closest(".seg-item");
  if (!b) return;
  document.querySelectorAll("#toolsSeg .seg-item").forEach((x) => x.classList.toggle("active", x === b));
  const alvo = "seg-" + b.dataset.seg;
  document.querySelectorAll("#view-tools .seg-view").forEach((v) => v.classList.toggle("active", v.id === alvo));
  const subs = {
    list: "Clique numa ferramenta para montar os argumentos e executar de verdade.",
    loja: "Instale plugins e kits. Tudo é conferido por hash antes de entrar, e vem com o risco declarado.",
    plugins: "Cada plugin pode ser ligado ou desligado sem apagar nada.",
  };
  $("#toolsSub").textContent = subs[b.dataset.seg] || "";
  if (b.dataset.seg === "loja" || b.dataset.seg === "plugins") carregarLoja();
});

/* aviso flutuante */
let toastTimer = null;
function toast(msg) {
  let t = $("#toast");
  if (!t) {
    t = el("div", "toast", "");
    t.id = "toast";
    document.body.append(t);
  }
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 5200);
}

/* mostrar/esconder raciocínio em todas as conversas */
function aplicarPrefPassos() {
  const esconder = PREF.escondido;
  const b = $("#btnRaciocinio");
  b.classList.toggle("off", esconder);
  b.title = esconder ? "mostrar o raciocínio e as ferramentas usadas" : "esconder o raciocínio e as ferramentas";
  b.querySelector(".rlabel").textContent = esconder ? "raciocínio: oculto" : "raciocínio: visível";
  document.querySelectorAll("#chat .turn").forEach((t) => t.classList.toggle("closed", esconder));
}
$("#btnRaciocinio").addEventListener("click", () => {
  PREF.ocultar = !PREF.escondido;
  aplicarPrefPassos();
});
aplicarPrefPassos();

/* ───────────────── init ───────────────── */
loadState();
carregarLoja();
setInterval(loadState, 20000);
