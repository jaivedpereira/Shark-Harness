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
  const curto = String(llm.model || "").split("/").pop().replace(/:free$/, "").slice(0, 20);
  $("#llmText").textContent = llm.configured ? `IA ligada · ${curto}` : "IA desligada";
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

function addMsg(quem, texto) {
  const m = el("div", "msg " + (quem === "user" ? "user" : "bot"));
  m.append(el("div", "bubble", `<strong>${quem === "user" ? "você" : "shark"}</strong><p>${esc(texto)}</p>`));
  chat.append(m);
  chat.scrollTop = chat.scrollHeight;
  return m;
}
function addSteps() {
  const box = el("div", "steps");
  chat.append(box);
  chat.scrollTop = chat.scrollHeight;
  return box;
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

  const box = addSteps();
  const sp = el("div", "spinner", "<i></i><i></i><i></i>");
  box.append(sp);
  chat.scrollTop = chat.scrollHeight;
  const btn = $("#formAgent").querySelector(".primary");
  btn.disabled = true;

  try {
    const r = await api("/api/agent", { method: "POST", body: { prompt: texto } });
    sp.remove();
    (r.steps || []).forEach((s) => { if (s.tipo !== "resposta") addStep(box, s.tipo, s.nome, s.detalhe); });
    addMsg("bot", r.answer || "(sem resposta)");
  } catch (err) {
    sp.remove();
    addStep(box, "erro", "rede", String(err));
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

/* ───────────────── init ───────────────── */
loadState();
setInterval(loadState, 20000);
