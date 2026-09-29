/* ══ Shark Harness — front ══ */
const $ = (s) => document.querySelector(s);
const el = (t, c, h) => { const n = document.createElement(t); if (c) n.className = c; if (h !== undefined) n.innerHTML = h; return n; };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));

const RISK = {
  safe:   { icon: "🟢", cls: "r-safe",   label: "leitura" },
  write:  { icon: "🟡", cls: "r-write",  label: "escreve" },
  exec:   { icon: "🟠", cls: "r-exec",   label: "executa" },
  danger: { icon: "🔴", cls: "r-danger", label: "apaga" },
};

let STATE = { tools: [], jobs: [], audit: [] };
let filtroRisco = "all";

async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  return r.json();
}

/* ─────────────────────────── estado ─────────────────────────── */
async function loadState() {
  try {
    STATE = await api("/api/state");
  } catch (e) {
    $("#llmText").textContent = "falha ao falar com o servidor";
    return;
  }
  const p = STATE.platform || {};
  $("#pillPlat").textContent = `${p.icon || "🖥️"} ${p.name || "?"}`;
  $("#pillTools").textContent = `${STATE.tools.length} ferramentas`;
  $("#pillRisk").textContent = `risco ≤ ${STATE.max_risk}`;

  const llm = STATE.llm || {};
  const dot = $("#llmState");
  if (llm.configured) {
    dot.className = "dot ok";
    $("#llmText").textContent = `${llm.model}`;
  } else {
    dot.className = "dot err";
    $("#llmText").textContent = "LLM sem chave — exporte NH_LLM_KEY";
  }

  renderTools();
  renderJobs();
  renderAudit();
  $("#sysInfo").textContent = STATE.sysinfo || "(vazio)";
}

/* ─────────────────────────── navegação ─────────────────────────── */
$("#nav").addEventListener("click", (e) => {
  const b = e.target.closest(".nav-item");
  if (!b) return;
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  b.classList.add("active");
  const v = $("#view-" + b.dataset.view);
  if (v) v.classList.add("active");
  if (b.dataset.view === "audit" || b.dataset.view === "cron") loadState();
});

/* ─────────────────────────── ferramentas ─────────────────────────── */
function renderTools() {
  const grid = $("#toolGrid");
  const q = $("#toolSearch").value.toLowerCase().trim();
  grid.innerHTML = "";
  const lista = STATE.tools.filter((t) => {
    if (filtroRisco !== "all" && t.risk !== filtroRisco) return false;
    if (!q) return true;
    return (t.name + " " + t.description + " " + t.plugin).toLowerCase().includes(q);
  });
  if (!lista.length) {
    grid.append(el("p", "hint", "nenhuma ferramenta bate com o filtro"));
    return;
  }
  lista.forEach((t, i) => {
    const r = RISK[t.risk] || RISK.safe;
    const card = el("article", "tool");
    card.style.animationDelay = Math.min(i * 22, 300) + "ms";
    card.innerHTML = `
      <h4>${esc(t.name)} <span class="tag ${r.cls}">${r.icon} ${r.label}</span></h4>
      <p>${esc(t.description)}</p>
      <div class="plugin" style="margin-top:9px">${esc(t.plugin)}</div>`;
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

/* ── modal de execução, com formulário gerado do JSON Schema ── */
let toolAtual = null;
function openTool(t) {
  toolAtual = t;
  const r = RISK[t.risk] || RISK.safe;
  $("#mTitle").textContent = t.name;
  $("#mDesc").textContent = t.description;
  $("#mRisk").innerHTML = `risco: <span class="tag ${r.cls}">${r.icon} ${r.label}</span>`;
  $("#mOut").textContent = "(sem saída ainda)";

  const form = $("#mForm");
  form.innerHTML = "";
  const props = (t.schema && t.schema.properties) || {};
  const req = new Set((t.schema && t.schema.required) || []);
  const nomes = Object.keys(props);

  if (!nomes.length) {
    form.append(el("p", "mdesc", "esta ferramenta não precisa de argumentos"));
  }
  nomes.forEach((k) => {
    const s = props[k] || {};
    const lab = el("label");
    const tipo = s.type === "integer" || s.type === "number" ? "number" : s.type === "boolean" ? "checkbox" : "text";
    lab.innerHTML = `<span>${k}${req.has(k) ? ' <b>*</b>' : ""}</span>`;
    if (tipo === "checkbox") {
      const inp = el("input");
      inp.type = "checkbox";
      inp.id = "f_" + k;
      lab.append(inp);
    } else {
      const inp = el("input");
      inp.id = "f_" + k;
      inp.type = tipo;
      inp.placeholder = s.description || (req.has(k) ? "obrigatório" : "opcional");
      if (k === "code" || k === "conteudo" || k === "command") inp.placeholder = "…";
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

/* ─────────────────────────── agente (chat) ─────────────────────────── */
const chat = $("#chat");

function addMsg(quem, texto) {
  const wm = $("#wm");
  if (wm) wm.classList.add("off");
  const m = el("div", "msg " + (quem === "user" ? "user" : "bot"));
  m.append(el("div", "bubble", `<strong>${quem === "user" ? "você" : "🦈 shark"}</strong><p>${esc(texto)}</p>`));
  chat.append(m);
  chat.scrollTop = chat.scrollHeight;
  return m;
}
function addStepsBox() {
  const box = el("div", "steps");
  chat.append(box);
  chat.scrollTop = chat.scrollHeight;
  return box;
}
function addStep(box, tipo, nome, detalhe) {
  if (tipo === "info") {
    box.append(el("div", "step", `<span>🦈</span><div><span class="sname">${esc(nome)}</span><div class="sarg">${esc(detalhe)}</div></div>`));
  } else if (tipo === "chamada") {
    box.append(el("div", "step",
      `<span>🔧</span><div><span class="sname">${esc(nome)}</span><div class="sarg">${esc(detalhe)}</div></div>`));
  } else if (tipo === "resultado") {
    const s = el("div", "step ok",
      `<span>✅</span><div><span class="sname">${esc(nome)}</span><div class="sarg">clique para ver a saída</div></div>`);
    s.append(el("pre", "", esc(detalhe)));
    s.addEventListener("click", () => s.classList.toggle("open"));
    box.append(s);
  } else if (tipo === "erro") {
    box.append(el("div", "step err", `<span>⚠️</span><div><span class="sname">erro</span><div class="sarg">${esc(detalhe)}</div></div>`));
  }
  chat.scrollTop = chat.scrollHeight;
}

$("#formAgent").addEventListener("submit", async (e) => {
  e.preventDefault();
  const ta = $("#prompt");
  const texto = ta.value.trim();
  if (!texto) return;
  ta.value = "";
  addMsg("user", texto);

  const box = addStepsBox();
  const dig = el("div", "typing", "<i></i><i></i><i></i>");
  box.append(dig);
  chat.scrollTop = chat.scrollHeight;
  $("#formAgent").querySelector(".send").disabled = true;

  try {
    const r = await api("/api/agent", { method: "POST", body: { prompt: texto } });
    dig.remove();
    (r.steps || []).forEach((s) => { if (s.tipo !== "resposta") addStep(box, s.tipo, s.nome, s.detalhe); });
    addMsg("bot", r.answer || "(sem resposta)");
  } catch (err) {
    dig.remove();
    addStep(box, "erro", "rede", String(err));
  }
  $("#formAgent").querySelector(".send").disabled = false;
  loadState();
});

$("#suggest").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  $("#prompt").value = b.textContent;
  $("#formAgent").dispatchEvent(new Event("submit"));
});

// Enter envia, Shift+Enter quebra linha; a caixa cresce com o texto
const ta = $("#prompt");
ta.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("#formAgent").dispatchEvent(new Event("submit"));
  }
});
ta.addEventListener("input", () => {
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
});

/* ─────────────────────────── agendador ─────────────────────────── */
function renderJobs() {
  const wrap = $("#jobList");
  wrap.innerHTML = "";
  if (!STATE.jobs.length) {
    wrap.append(el("p", "hint", "📭 nenhuma tarefa agendada ainda"));
    return;
  }
  STATE.jobs.forEach((j, i) => {
    const card = el("article", "job" + (j.enabled ? "" : " off"));
    card.style.animationDelay = Math.min(i * 25, 250) + "ms";
    card.innerHTML = `
      <div>
        <h4>${j.enabled ? "▶️" : "⏸️"} ${esc(j.name)} <code>[${esc(j.id)}]</code></h4>
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
  await loadState();
  if (b.dataset.a === "run") {
    const jobs = await api("/api/state");
    const j = jobs.jobs.find((x) => x.id === b.dataset.id);
    if (j) addMsg("bot", `job "${j.name}" executado: ${j.last_status || "ok"}`);
  }
});

$("#cKind").addEventListener("change", (e) => {
  const shell = e.target.value === "shell";
  $("#wrapPayload").querySelector("input").placeholder = shell ? "tar -czf ~/bkp.tgz ~/shark-workspace" : "sysinfo_report";
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
    $("#cHint").textContent = "⚠️ preencha nome, cron e o comando/ferramenta";
    return;
  }
  const r = await api("/api/cron", { method: "POST", body });
  $("#cHint").textContent = r.result || "";
  $("#cName").value = $("#cCron").value = $("#cPayload").value = $("#cArgs").value = "";
  await loadState();
});

/* ─────────────────────────── auditoria ─────────────────────────── */
function renderAudit() {
  const tb = $("#auditTable").querySelector("tbody");
  tb.innerHTML = "";
  if (!STATE.audit.length) {
    tb.append(el("tr", "", '<td colspan="4" class="t">log vazio — nada executado ainda</td>'));
    return;
  }
  STATE.audit.slice().reverse().forEach((a) => {
    const cls = a.status === "ok" ? "b-ok" : a.status === "blocked" ? "b-blocked" : "b-error";
    const tr = el("tr", "");
    tr.innerHTML = `<td class="t">${esc(a.ts)}</td>
      <td><span class="badge ${cls}">${esc(a.status)}</span></td>
      <td class="n">${esc(a.tool)}</td>
      <td>${esc(a.detail)}</td>`;
    tb.append(tr);
  });
}

/* ─────────────────────────── init ─────────────────────────── */
loadState();
setInterval(loadState, 20000);
