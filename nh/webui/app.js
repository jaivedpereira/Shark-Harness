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
  // blindagem: um elemento que mude de nome não pode derrubar o resto da interface
  try {
    pintarEstado();
  } catch (e) {
    console.error("loadState: falhou ao pintar o estado —", e);
  }
}

function pintarEstado() {
  const p = STATE.platform || {};
  $("#pillPlat").textContent = `${p.name || "?"}`;
  $("#pillTools").textContent = `${STATE.tools.length} ferramentas · risco ≤ ${STATE.max_risk}`;

  const llm = STATE.llm || {};
  // quem manda é o modelo ATIVO (do catálogo, se houver) — uma fonte de verdade só,
  // senão a barra lateral e o topo do chat mostram modelos diferentes
  const ativo = STATE.modelo_ativo || null;
  const nomeMostrado = ativo ? (ativo.apelido || ativo.modelo) : (llm.model || "");
  const configurado = ativo ? !!ativo.tem_chave : !!llm.configured;
  $("#llmState").className = "dot " + (configurado ? "ok" : "err");
  const mdot = $("#mDot");
  if (mdot) mdot.className = "dot " + (configurado ? "ok" : "err");
  const bruto = String(nomeMostrado || "").split("/").pop().replace(/:free$/, "");
  const curto = bruto.length > 18 ? bruto.slice(0, 17) + "…" : bruto;
  $("#llmText").textContent = configurado ? `IA ligada · ${curto}` : "IA desligada";
  $("#llmLine").title = ativo ? `${ativo.apelido} · ${ativo.modelo}\n${ativo.url}` : (llm.model || "");
  $("#llmText").title = configurado
    ? (ativo ? `${ativo.apelido} — ${ativo.modelo} (nível ${ativo.nivel_nome})` : llm.model)
    : "abra Configurações para colar a chave";

  renderTools();
  renderJobs();
  renderAudit();
  $("#sysInfo").textContent = STATE.sysinfo || "(vazio)";
  atualizarBtnModelo();
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
  else if (view === "sessoes") carregarSessoes();
  else if (view === "sys") carregarUso();
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
  if (!lista.length) { grid.innerHTML = vazio("🔍", "Nada encontrado", "Nenhuma ferramenta bate com esse filtro de risco. Tente limpar a busca."); return; }
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

/* ───────────────── markdown mínimo (sem dependência) ─────────────────
   As respostas do modelo vêm em markdown; antes eram mostradas cruas.
   Cobre: ```blocos```, `inline`, **negrito**, *itálico*, títulos, listas e links. */
function md(texto) {
  const blocos = [];
  // 1) guarda os blocos de código antes de escapar (senão o escape estraga o código)
  let s = String(texto ?? "").replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, codigo) => {
    blocos.push({ lang: lang || "", codigo });
    return `\u0000BLOCO${blocos.length - 1}\u0000`;
  });

  s = esc(s);

  // 2) títulos
  s = s.replace(/^#{4,6}\s+(.+)$/gm, '<h6>$1</h6>')
       .replace(/^###\s+(.+)$/gm, "<h5>$1</h5>")
       .replace(/^##\s+(.+)$/gm, "<h4>$1</h4>")
       .replace(/^#\s+(.+)$/gm, "<h3>$1</h3>");

  // 3) listas
  s = s.replace(/^\s*[-*+]\s+(.+)$/gm, "<li>$1</li>")
       .replace(/^\s*\d+[.)]\s+(.+)$/gm, "<li>$1</li>")
       .replace(/(<li>[\s\S]*?<\/li>)(?!\s*<li>)/g, "<ul>$1</ul>");

  // 4) tabelas simples (| a | b |) — só as linhas de dados viram texto alinhado
  s = s.replace(/^\|(.+)\|$/gm, (linha) => {
    if (/^\|[\s:|-]+\|$/.test(linha)) return "";
    const cels = linha.slice(1, -1).split("|").map((c) => c.trim());
    return "— " + cels.join(" · ");
  });

  // 5) inline
  s = s.replace(/`([^`\n]+)`/g, "<code>$1</code>")
       .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
       .replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, "<em>$1</em>")
       .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g,
                '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // 6) parágrafos por linha dupla — blocos de código e listas ficam fora
  s = s.split(/\n{2,}/).map((p) => {
    const t = p.trim();
    if (!t) return "";
    // já é um bloco pronto: não embrulha em <p> nem transforma as quebras em <br/>
    if (/^<(h3|h4|h5|h6|ul|ol)/.test(t)) return t.replace(/\n/g, "");
    if (/^\u0000BLOCO\d+\u0000$/.test(t)) return t;
    return `<p>${t.replace(/\n/g, "<br/>")}</p>`;
  }).join("");

  // 7) devolve os blocos de código, com botão de copiar
  s = s.replace(/\u0000BLOCO(\d+)\u0000/g, (_, i) => {
    const b = blocos[Number(i)];
    return `<div class="codeblk"><div class="codehd"><span>${esc(b.lang || "código")}</span>` +
           `<button class="copy" type="button">copiar</button></div>` +
           `<pre>${esc(b.codigo.replace(/\n$/, ""))}</pre></div>`;
  });

  // 8) limpeza: <br/> sobrando colado em bloco
  s = s.replace(/<\/li><br\/><li>/g, "</li><li>")
       .replace(/<br\/><(ul|div|h3|h4|h5|h6)/g, "<$1")
       .replace(/<\/(ul|div)><br\/>/g, "</$1>")
       .replace(/<br\/><\/p>/g, "</p>")
       .replace(/<p><\/p>/g, "");
  return s;
}

/* copiar (delegação: vale para código e para a resposta inteira) */
document.addEventListener("click", async (e) => {
  const b = e.target.closest(".copy");
  if (!b) return;
  const bloco = b.closest(".codeblk");
  const alvo = b.dataset.alvo ? document.querySelector(b.dataset.alvo) : null;
  const texto = bloco ? bloco.querySelector("pre").textContent
                      : alvo ? alvo.innerText
                      : "";
  try {
    await navigator.clipboard.writeText(texto);
    const antes = b.textContent;
    b.textContent = "copiado!";
    setTimeout(() => { b.textContent = antes; }, 1400);
  } catch (_) {
    b.textContent = "não deu";
  }
});

function addMsg(quem, texto, opts) {
  const m = el("div", "msg " + (quem === "user" ? "user" : "bot"));
  const corpo = quem === "user" ? `<p>${esc(texto)}</p>` : md(texto);
  m.append(el("div", "bubble",
    `<strong>${quem === "user" ? "você" : "shark"}</strong>${corpo}` +
    `<span class="hora">${hora()}</span>`));
  if (opts && opts.copiar) {
    const b = el("button", "copy mini", "copiar");
    b.dataset.alvo = opts.alvo;
    m.querySelector(".bubble").append(b);
  }
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
    partes.push(plural(d.ferramentas.length, "ferramenta", "ferramentas"));
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

/* ícone e rótulo de cada tipo de passo, na linha do tempo */
const PASSO_ICO = { chamada: "→", resultado: "✓", erro: "✕", info: "i", raciocinio: "✦" };

function addStep(box, tipo, nome, detalhe) {
  const ico = PASSO_ICO[tipo] || "•";
  let extra = "";

  // mede quanto a ferramenta demorou (do "chamada" até o "resultado")
  if (tipo === "chamada") box._inicio = Date.now();
  if (tipo === "resultado" && box._inicio) {
    extra = `<span class="dur">${((Date.now() - box._inicio) / 1000).toFixed(1)}s</span>`;
    box._inicio = null;
  }

  const s = el("div", "step s-" + tipo);
  const dot = el("div", "sdot", ico);
  const corpo = el("div", "scorpo");
  const titulo = el("div", "sname");
  titulo.innerHTML = esc(nome) + extra;
  corpo.append(titulo);

  if (tipo === "resultado") {
    corpo.append(el("div", "sarg", "clique para ver a saída"));
    corpo.append(el("pre", "", esc(detalhe)));
    s.addEventListener("click", () => s.classList.toggle("open"));
  } else {
    corpo.append(el("div", "sarg", esc(detalhe)));
  }

  s.append(dot, corpo);
  box.append(s);
  chat.scrollTop = chat.scrollHeight;
}

/* ───────────────── envio: sessão, parar e repetir ───────────────── */
let ENVIANDO = null; // AbortController da requisição em andamento

/* hora curta para o rodapé da mensagem */
function hora() {
  return new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function bolhaResposta(turno, texto) {
  const id = "r" + Math.random().toString(36).slice(2, 9);
  const div = el("div", "bubble");
  div.id = id;
  div.innerHTML = `<strong>shark</strong>${md(texto)}<span class="hora">${hora()}</span>`;
  const b = el("button", "copy mini", "copiar");
  b.dataset.alvo = "#" + id;
  div.append(b);
  turno.body.append(div);
  return div;
}

/* lê um stream SSE e chama aoEvento(nome, dados) a cada evento */
async function lerSSE(resp, aoEvento) {
  const leitor = resp.body.getReader();
  const dec = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await leitor.read();
    if (done) break;
    buffer += dec.decode(value, { stream: true });
    let corte;
    while ((corte = buffer.indexOf("\n\n")) !== -1) {
      const bloco = buffer.slice(0, corte);
      buffer = buffer.slice(corte + 2);
      let nome = "message";
      let dados = "";
      bloco.split("\n").forEach((l) => {
        if (l.startsWith("event:")) nome = l.slice(6).trim();
        else if (l.startsWith("data:")) dados += l.slice(5).trim();
      });
      if (!dados) continue;
      try {
        aoEvento(nome, JSON.parse(dados));
      } catch (_) { /* evento torto: ignora */ }
    }
  }
}

/* área onde o texto aparece sendo escrito ao vivo */
function liveBox(turno) {
  if (!turno.live) {
    turno.live = el("div", "live");
    turno.live.append(el("div", "live-txt"), el("i", "cursor"));
    turno.body.append(turno.live);
  }
  return turno.live;
}

async function enviar(texto, repetir) {
  const limpo = String(texto || "").trim();
  if (!limpo || ENVIANDO) return;

  if (!repetir) addMsg("user", limpo);
  const turno = addTurn();
  const sp = el("div", "spinner", "<i></i><i></i><i></i>");
  turno.steps.append(sp);
  chat.scrollTop = chat.scrollHeight;

  ENVIANDO = new AbortController();
  const btnEnviar = $("#btnEnviar");
  const btnParar = $("#btnParar");
  btnEnviar.disabled = true;
  btnParar.style.display = "";
  let tokens = null;
  let respostaFinal = "";

  const aoPasso = (p) => {
    // quando uma ferramenta vai rodar, o texto já escrito era raciocínio
    if (p.tipo === "chamada" && turno.live) {
      const t = turno.live.querySelector(".live-txt").textContent.trim();
      turno.live.remove();
      turno.live = null;
      if (t) addStep(turno.steps, "raciocinio", "raciocínio", t);
    }
    if (p.tipo === "resposta") return;
    if (p.tipo === "tokens") {
      try { tokens = JSON.parse(p.detalhe); } catch (_) { tokens = null; }
      return;
    }
    if (sp.parentNode) sp.remove();
    addStep(turno.steps, p.tipo, p.nome, p.detalhe);
    chat.scrollTop = chat.scrollHeight;
  };

  try {
    const resp = await fetch("/api/agente/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: limpo, sessao: SESSAO_ATUAL ? SESSAO_ATUAL.id : "" }),
      signal: ENVIANDO.signal,
    });
    if (!resp.ok) throw new Error("o servidor respondeu HTTP " + resp.status);

    await lerSSE(resp, (nome, dados) => {
      if (nome === "passo") aoPasso(dados);
      else if (nome === "delta") {
        if (sp.parentNode) sp.remove();
        const box = liveBox(turno);
        box.querySelector(".live-txt").textContent += dados.texto || "";
        chat.scrollTop = chat.scrollHeight;
      } else if (nome === "erro") {
        if (sp.parentNode) sp.remove();
        addStep(turno.steps, "erro", "erro", dados.mensagem || "erro");
      } else if (nome === "fim") {
        respostaFinal = dados.answer || "";
        if (dados.sessao) SESSAO_ATUAL = { ...(SESSAO_ATUAL || {}), ...dados.sessao };
      }
    });

    if (sp.parentNode) sp.remove();
    if (turno.live) turno.live.remove();
    bolhaResposta(turno, respostaFinal || "(sem resposta)");
    resumirTurno(turno, tokens);
    if (SESSAO_ATUAL) carregarSessoes();
  } catch (err) {
    if (sp.parentNode) sp.remove();
    if (turno.live) turno.live.remove();
    const parou = err && err.name === "AbortError";
    addStep(turno.steps, "erro", parou ? "cancelado" : "rede",
            parou ? "você parou a execução." : String(err));
    const t = el("button", "ghost small", "tentar de novo");
    t.addEventListener("click", () => enviar(limpo, true));
    turno.body.append(t);
    resumirTurno(turno, null);
  }

  ENVIANDO = null;
  btnEnviar.disabled = false;
  btnParar.style.display = "none";
  loadState();
}

$("#formAgent").addEventListener("submit", (e) => {
  e.preventDefault();
  const ta = $("#prompt");
  const texto = ta.value;
  if (!texto.trim()) return;
  ta.value = "";
  ta.style.height = "auto";
  enviar(texto);
});

$("#btnParar").addEventListener("click", () => {
  if (ENVIANDO) ENVIANDO.abort();
});

/* Enter envia; Shift+Enter quebra linha */
$("#prompt").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("#formAgent").dispatchEvent(new Event("submit"));
  }
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
  if (!STATE.jobs.length) { wrap.innerHTML = vazio("⏰", "Nada agendado", "Aqui aparecem as tarefas que rodam sozinhas. Peça ao agente algo como 'agenda um job a cada 30 min pra checar o disco'."); return; }
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

/* aviso flutuante: empilha, com ícone, cor e barra de tempo */
function toast(msg, tipo) {
  const caixa = $("#toasts");
  const texto = String(msg ?? "");
  const cls = tipo || (/^(❌|erro|não|nao)/i.test(texto) ? "err" : /^✅/.test(texto) ? "ok" : "");
  const ico = cls === "err" ? "✕" : cls === "ok" ? "✓" : "•";
  const t = el("div", "toast " + cls);
  t.innerHTML = `<span class="tico">${ico}</span><span>${esc(texto)}</span><i class="barra"></i>`;
  caixa.append(t);
  // só os últimos 3 ficam na tela
  while (caixa.children.length > 3) caixa.firstChild.remove();
  setTimeout(() => {
    t.classList.add("saindo");
    setTimeout(() => t.remove(), 220);
  }, 4500);
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

/* ═══════════════════════ uso do modelo ═══════════════════════ */
let USO_DIAS = 7;
let USO = null;

function fmtTok(n) {
  n = Number(n || 0);
  if (n >= 1e6) return (n / 1e6).toFixed(2).replace(".", ",") + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1).replace(".", ",") + "k";
  return String(n);
}
function fmtCusto(v, conhecido) {
  if (!conhecido) return "—";
  if (!v) return "US$ 0";
  return "US$ " + (v < 0.01 ? v.toFixed(4) : v.toFixed(2));
}

/* plural sem o feio "1 item(s)" */
function plural(n, um, muitos) {
  return `${n} ${Number(n) === 1 ? um : muitos}`;
}

function statUso(rot, s, destaque) {
  const vazio = !s || !s.execucoes;
  const c = vazio ? "" : `<em>${fmtCusto(s.custo, s.custo_conhecido)}</em>`;
  return `<div class="ustat${destaque ? " on" : ""}">
      <span>${rot}</span>
      <strong>${vazio ? "0" : fmtTok(s.total)}</strong>
      <small>${vazio ? "nenhuma execução" : plural(s.execucoes, "execução", "execuções")}</small>
      ${c}
    </div>`;
}

async function carregarUso(dias) {
  if (dias) USO_DIAS = dias;
  try {
    USO = await api(`/api/usage?dias=${USO_DIAS}`);
  } catch (e) {
    USO = { erro: String(e), por_dia: [], modelos: [], ferramentas: [] };
  }
  renderUso();
}

function renderUso() {
  const d = USO || {};
  if (d.erro) {
    $("#usoTotais").innerHTML = `<span class="status err">não consegui ler o histórico: ${esc(d.erro)}</span>`;
    return;
  }
  $("#usoTotais").innerHTML =
    statUso("hoje", d.hoje, true) + statUso("7 dias", d.semana) + statUso(`total (${d.dias}d)`, d.total);

  /* gráfico de barras dos últimos 14 dias */
  const dias = d.por_dia || [];
  const max = Math.max(1, ...dias.map((x) => Number(x.total || 0)));
  const hoje = new Date().toISOString().slice(0, 10);
  $("#usoGrafico").innerHTML = dias
    .map((x) => {
      const h = Math.round((Number(x.total || 0) / max) * 100);
      const dia = String(x.dia || "").slice(8, 10) + "/" + String(x.dia || "").slice(5, 7);
      return `<div class="ubar${x.dia === hoje ? " hoje" : ""}" title="${dia}: ${fmtTok(x.total)} tokens em ${plural(x.execucoes, "execução", "execuções")}">
        <div class="ufill" style="height:${x.total ? Math.max(4, h) : 0}%"></div>
        <span>${String(x.dia || "").slice(8, 10)}</span>
      </div>`;
    })
    .join("");

  const soma = dias.reduce((a, x) => a + Number(x.total || 0), 0);
  $("#usoLegenda").textContent = soma
    ? `últimos 14 dias: ${fmtTok(soma)} tokens · pico de ${fmtTok(max)} num dia`
    : "nenhuma execução nos últimos 14 dias — converse com o agente que começa a registrar";

  /* tabela por modelo */
  const mods = d.modelos || [];
  if (!mods.length) {
    $("#usoModelos").innerHTML = "";
    return;
  }
  $("#usoModelos").innerHTML =
    `<h4 class="pgroup">Por modelo</h4>` +
    mods
      .map(
        (m) => `<div class="umodel">
        <div class="umodel-info">
          <strong>${esc(String(m.modelo || "?").split("/").pop())}</strong>
          <span>${fmtTok(m.total)} tokens · ↑${fmtTok(m.entrada)} ↓${fmtTok(m.saida)} · ${plural(m.execucoes, "execução", "execuções")}</span>
        </div>
        <div class="umodel-custo">${fmtCusto(m.custo, m.preco_conhecido)}</div>
      </div>`
      )
      .join("");
}

$("#usoDias").addEventListener("click", (e) => {
  const b = e.target.closest(".chip");
  if (!b) return;
  document.querySelectorAll("#usoDias .chip").forEach((x) => x.classList.toggle("active", x === b));
  carregarUso(Number(b.dataset.dias));
});

$("#usoLimpar").addEventListener("click", async () => {
  if (!confirm("Apagar o histórico de uso do modelo? (não mexe em mais nada)")) return;
  try {
    await api("/api/usage", { method: "POST", body: { acao: "limpar" } });
  } catch (_) {
    /* sem endpoint de POST: limpa pelo lado de cá */
  }
  toast("histórico de uso apagado");
  carregarUso();
});

/* ═══════════════════════ tamanho da barra de baixo ═══════════════════════ */
const TAMANHOS_BARRA = ["normal", "compacta", "minima"];

function aplicarBarra() {
  let t = localStorage.getItem("nh_barra") || "normal";
  if (!TAMANHOS_BARRA.includes(t)) t = "normal";
  document.body.classList.remove("barra-normal", "barra-compacta", "barra-minima");
  document.body.classList.add("barra-" + t);
  const sel = $("#cfgBarra");
  if (sel) sel.value = t;
}
$("#cfgBarra").addEventListener("change", (e) => {
  localStorage.setItem("nh_barra", e.target.value);
  aplicarBarra();
  toast(`barra de baixo: ${e.target.value === "normal" ? "normal" : e.target.value === "compacta" ? "compacta" : "mínima"}`);
});
aplicarBarra();

/* ═══════════════════════ sessões (pasta de projeto) ═══════════════════════ */
let SESSAO_ATUAL = null;   // {id, nome, pasta}
let SES_LISTA = [];
let FS_ATUAL = "";
let FS_INICIO = "";

async function carregarSessoes() {
  try {
    const d = await api("/api/sessoes");
    SES_LISTA = d.sessoes || [];
    FS_INICIO = d.inicio || "";
    renderSessoes();
    renderSessaoPick();
  } catch (e) {
    $("#sesLista").innerHTML = `<p class="hint">não consegui falar com o servidor: ${esc(String(e))}</p>`;
  }
}

function renderSessoes() {
  const box = $("#sesLista");
  box.innerHTML = "";
  if (!SES_LISTA.length) {
    box.append(el("p", "hint",
      "Nenhuma sessão ainda. Crie uma acima apontando para a pasta de um projeto — " +
      "por exemplo o repositório que você clonou no celular."));
    return;
  }
  SES_LISTA.forEach((s) => {
    const c = el("div", "sescard" + (SESSAO_ATUAL && SESSAO_ATUAL.id === s.id ? " on" : ""));
    c.innerHTML =
      `<div class="sescard-top"><span class="sescard-ico">📂</span>` +
      `<div class="sescard-nome"><strong>${esc(s.nome)}</strong>` +
      `<code>${esc(s.pasta)}</code></div>` +
      (s.existe ? "" : `<span class="rtag r-danger">pasta sumiu</span>`) + `</div>` +
      `<div class="sescard-meta">${plural(s.mensagens || 0, "mensagem", "mensagens")}` +
      (s.ultima ? ` · última: ${esc(String(s.ultima).slice(0, 70))}` : " · conversa nova") + `</div>`;
    const acoes = el("div", "sescard-acoes");
    const abrir = el("button", "primary small", SESSAO_ATUAL && SESSAO_ATUAL.id === s.id ? "aberta" : "abrir");
    abrir.disabled = !s.existe;
    abrir.addEventListener("click", () => abrirSessao(s.id));
    const ren = el("button", "ghost small", "renomear");
    ren.addEventListener("click", async () => {
      const nome = prompt("Novo nome da sessão:", s.nome);
      if (!nome) return;
      const r = await api("/api/sessoes", { method: "POST", body: { acao: "renomear", id: s.id, nome } });
      toast(r.msg || r.erro || "pronto");
      carregarSessoes();
    });
    const limp = el("button", "ghost small", "limpar conversa");
    limp.addEventListener("click", async () => {
      if (!confirm(`Zerar a conversa da sessão "${s.nome}"? A pasta não é tocada.`)) return;
      const r = await api("/api/sessoes", { method: "POST", body: { acao: "limpar", id: s.id } });
      toast(r.msg || r.erro || "pronto");
      if (SESSAO_ATUAL && SESSAO_ATUAL.id === s.id) abrirSessao(s.id);
    });
    const del = el("button", "ghost small", "apagar");
    del.addEventListener("click", async () => {
      if (!confirm(`Apagar a sessão "${s.nome}"? A pasta do projeto NÃO é tocada.`)) return;
      const r = await api("/api/sessoes", { method: "POST", body: { acao: "apagar", id: s.id } });
      toast(r.msg || r.erro || "pronto");
      if (SESSAO_ATUAL && SESSAO_ATUAL.id === s.id) sairSessao();
      carregarSessoes();
    });
    acoes.append(abrir, ren, limp, del);
    c.append(acoes);
    box.append(c);
  });
}

function renderSessaoBar() {
  const txt = $("#sbarTxt");
  const fechar = $("#sbarClose");
  const arv = $("#sbarArvore");
  if (SESSAO_ATUAL) {
    txt.textContent = `${SESSAO_ATUAL.nome} — ${SESSAO_ATUAL.pasta}`;
    txt.title = SESSAO_ATUAL.pasta;
    $("#sbar").classList.add("on");
    fechar.style.display = "";
    arv.style.display = "";
    $("#mDot").title = "sessão: " + SESSAO_ATUAL.nome;
  } else {
    txt.textContent = "Chat livre — sem pasta de projeto";
    txt.title = "as ferramentas usam o workspace padrão do harness";
    $("#sbar").classList.remove("on");
    fechar.style.display = "none";
    arv.style.display = "none";
    $("#arvoreBox").style.display = "none";
  }
}

async function abrirSessao(id) {
  const r = await api("/api/sessoes", { method: "POST", body: { acao: "abrir", id } });
  if (!r.ok) {
    toast(r.erro || "não consegui abrir a sessão");
    return;
  }
  SESSAO_ATUAL = { id: r.sessao.id, nome: r.sessao.nome, pasta: r.sessao.pasta };
  $("#arvoreBox").textContent = r.arvore || "";
  renderSessaoBar();
  // remonta a conversa da sessão
  chat.innerHTML = "";
  const hist = r.historico || [];
  if (!hist.length) {
    const m = el("div", "msg bot");
    m.append(el("div", "bubble",
      `<strong>shark</strong><p>Sessão <strong>${esc(SESSAO_ATUAL.nome)}</strong> aberta em ` +
      `<code>${esc(SESSAO_ATUAL.pasta)}</code>.<br/>Eu já li a pasta — peça algo como ` +
      `"o que esse projeto faz?", "roda os testes" ou "adiciona um arquivo X".</p>`));
    chat.append(m);
  } else {
    hist.forEach((h) => addMsg(h.role === "user" ? "user" : "bot", h.content));
  }
  irPara("chat");
  fecharSesModal();
  toast(`sessão "${SESSAO_ATUAL.nome}" aberta — trabalhando em ${SESSAO_ATUAL.pasta}`);
  carregarSessoes();
}

function sairSessao() {
  SESSAO_ATUAL = null;
  renderSessaoBar();
  chat.innerHTML = "";
  const m = el("div", "msg bot");
  m.append(el("div", "bubble",
    `<strong>Pronto.</strong><p>Você saiu da sessão — agora as ferramentas usam o workspace padrão. ` +
    `Para voltar a trabalhar num projeto, toque em <strong>📂</strong> acima ou abra a aba Sessões.</p>`));
  chat.append(m);
}

function renderSessaoPick() {
  const box = $("#sesPickLista");
  box.innerHTML = "";
  const livre = el("button", "sespick-item" + (SESSAO_ATUAL ? "" : " on"));
  livre.innerHTML = `<span>💬</span><div><strong>Chat livre</strong>` +
                    `<em>sem pasta de projeto — workspace padrão do harness</em></div>`;
  livre.addEventListener("click", () => { sairSessao(); fecharSesModal(); });
  box.append(livre);
  SES_LISTA.forEach((s) => {
    const b = el("button", "sespick-item" + (SESSAO_ATUAL && SESSAO_ATUAL.id === s.id ? " on" : ""));
    b.innerHTML = `<span>📂</span><div><strong>${esc(s.nome)}</strong>` +
                  `<em>${esc(s.pasta)} · ${plural(s.mensagens || 0, "mensagem", "mensagens")}</em></div>`;
    b.addEventListener("click", () => abrirSessao(s.id));
    box.append(b);
  });
}

function abrirSesModal() { $("#sesModal").classList.add("show"); renderSessaoPick(); }
function fecharSesModal() { $("#sesModal").classList.remove("show"); }

$("#sbarPick").addEventListener("click", abrirSesModal);
$("#sesModalClose").addEventListener("click", fecharSesModal);
$("#sesPickNova").addEventListener("click", () => { fecharSesModal(); irPara("sessoes"); });
$("#sbarClose").addEventListener("click", sairSessao);
$("#sbarArvore").addEventListener("click", () => {
  const a = $("#arvoreBox");
  a.style.display = a.style.display === "none" ? "" : "none";
});

$("#sesCriar").addEventListener("click", async () => {
  const st = $("#sesStatus");
  st.className = "status";
  st.textContent = "criando…";
  const r = await api("/api/sessoes", {
    method: "POST",
    body: { acao: "criar", nome: $("#sesNome").value.trim(), pasta: $("#sesPasta").value.trim() },
  });
  if (!r.ok) {
    st.className = "status err";
    st.textContent = r.erro || "não deu para criar";
    return;
  }
  st.className = "status ok";
  st.textContent = r.msg;
  $("#sesNome").value = "";
  $("#sesPasta").value = "";
  await carregarSessoes();
  if (r.sessao) await abrirSessao(r.sessao.id);
});

$("#sesNavegar").addEventListener("click", () => abrirFS($("#sesPasta").value.trim() || FS_INICIO));

/* navegador de pastas */
async function abrirFS(pasta) {
  const d = await api("/api/fs?pasta=" + encodeURIComponent(pasta || ""));
  if (d.erro) {
    $("#fsStatus").className = "status err";
    $("#fsStatus").textContent = d.erro;
    return;
  }
  FS_ATUAL = d.pasta;
  $("#fsAtual").textContent = d.pasta;
  $("#fsAcima").disabled = !d.acima;
  $("#fsAcima").dataset.alvo = d.acima || "";
  $("#fsStatus").textContent = d.tem_git ? "tem repositório git aqui" : "";
  $("#fsStatus").className = "status";
  const lista = $("#fsLista");
  lista.innerHTML = "";
  if (!d.pastas.length) {
    lista.append(el("p", "hint", "nenhuma subpasta aqui — pode usar esta pasta mesmo."));
  }
  d.pastas.forEach((p) => {
    const b = el("button", "fs-item", `<span>📁</span>${esc(p.nome)}`);
    b.addEventListener("click", () => abrirFS(p.caminho));
    lista.append(b);
  });
  $("#fsModal").classList.add("show");
}
$("#fsClose").addEventListener("click", () => $("#fsModal").classList.remove("show"));
$("#fsAcima").addEventListener("click", (e) => { if (e.target.dataset.alvo) abrirFS(e.target.dataset.alvo); });
$("#fsUsar").addEventListener("click", () => {
  $("#sesPasta").value = FS_ATUAL;
  $("#fsModal").classList.remove("show");
  if (!$("#sesNome").value.trim()) {
    $("#sesNome").value = FS_ATUAL.split("/").filter(Boolean).pop() || "projeto";
  }
});

/* ═══════════════════════ catálogo de modelos ═══════════════════════ */
let MODELOS = { modelos: [], niveis: [], ativo: "", global: {} };
let EDITANDO = "";       // id do modelo em edição (vazio = criando)
let TESTANDO = "";       // id do modelo com teste em andamento
let RESULTADOS = {};     // id -> resultado do teste

function hostDe(url) {
  try {
    return new URL(url).host;
  } catch (_) {
    return url;
  }
}

function atualizarBtnModelo() {
  const m = (STATE && STATE.modelo_ativo) || null;
  const emoji = $("#mBtnEmoji");
  const txt = $("#mBtnTxt");
  const btn = $("#btnModelo");
  if (!m) return;
  emoji.textContent = m.nivel_emoji || "⚙️";
  txt.textContent = String(m.apelido || m.modelo || "modelo").slice(0, 22);
  btn.title = `${m.apelido} · ${m.modelo}\n${m.url}\nnível ${m.nivel_nome}` +
              (m.tem_chave ? "" : "\n⚠️ sem chave configurada");
  btn.classList.toggle("alerta", !m.tem_chave);
}

async function carregarModelos() {
  try {
    MODELOS = await api("/api/modelos");
    renderCatalogo();
    atualizarBtnModelo();
  } catch (e) {
    $("#modelListaCat").innerHTML = `<p class="hint">não consegui carregar: ${esc(String(e))}</p>`;
  }
}

function renderCatalogo() {
  const box = $("#modelListaCat");
  if (!box) return;
  box.innerHTML = "";

  if (!MODELOS.modelos.length) {
    box.innerHTML = vazio("🧠", "Nenhum modelo cadastrado",
      "Você está usando o modelo global do Ajustes. Cadastre modelos aqui para " +
      "ter vários endpoints, níveis diferentes e reservas automáticas.");
  }

  // agrupa por nível (do mais potente para o mais rápido na exibição)
  const niveis = [...(MODELOS.niveis || [])].sort((a, b) => b.nivel - a.nivel);
  niveis.forEach((n) => {
    const doNivel = MODELOS.modelos.filter((m) => Number(m.nivel) === Number(n.nivel));
    if (!doNivel.length) return;
    box.append(el("div", "mcat-grupo", `<span>${n.emoji}</span> ${esc(n.nome)}`));
    doNivel.forEach((m) => box.append(cartaoModelo(m)));
  });

  // o modelo global aparece como uma opção fixa no fim
  const g = MODELOS.global || {};
  const ativoGlobal = !MODELOS.ativo;
  const ficha = el("div", "mcard" + (ativoGlobal ? " on" : ""));
  ficha.innerHTML =
    `<div class="mcard-top">` +
    `<span class="mcard-emoji">⚙️</span>` +
    `<div class="mcard-nome"><strong>Modelo global (Ajustes)</strong>` +
    `<code>${esc(g.modelo || "—")}</code></div>` +
    (ativoGlobal ? `<span class="rtag r-safe">em uso</span>` : "") +
    `</div>` +
    `<div class="mcard-meta">${esc(hostDe(g.url || ""))} · ` +
    `${g.tem_chave ? "com chave" : "⚠️ sem chave"}</div>`;
  const acoes = el("div", "mcard-acoes");
  if (!ativoGlobal) {
    const b = el("button", "primary small", "usar este");
    b.addEventListener("click", () => usarModelo(""));
    acoes.append(b);
  }
  ficha.append(acoes);
  box.append(el("div", "mcat-grupo", "⚙️ Global"));
  box.append(ficha);
}

function cartaoModelo(m) {
  const ativo = MODELOS.ativo === m.id;
  const ficha = el("div", "mcard" + (ativo ? " on" : ""));
  ficha.innerHTML =
    `<div class="mcard-top">` +
    `<span class="mcard-emoji">${m.nivel_emoji}</span>` +
    `<div class="mcard-nome"><strong>${esc(m.apelido)}</strong>` +
    `<code>${esc(m.modelo)}</code></div>` +
    (ativo ? `<span class="rtag r-safe">em uso</span>` : "") +
    (m.tem_chave ? "" : `<span class="rtag r-write">sem chave</span>`) +
    `</div>` +
    `<div class="mcard-meta">${esc(hostDe(m.url))} · nível ${esc(m.nivel_nome)}` +
    (m.nota ? ` · ${esc(m.nota)}` : "") + `</div>`;

  const acoes = el("div", "mcard-acoes");
  if (!ativo) {
    const usar = el("button", "primary small", "usar");
    usar.addEventListener("click", () => usarModelo(m.id));
    acoes.append(usar);
  }
  const testar = el("button", "ghost small", TESTANDO === m.id ? "testando…" : "testar");
  testar.disabled = TESTANDO === m.id;
  testar.title = "roda 3 perguntas simples e mede acerto e velocidade (gasta quase nada)";
  testar.addEventListener("click", () => testarModelo(m.id));
  const editar = el("button", "ghost small", "editar");
  editar.addEventListener("click", () => editarModelo(m));
  const del = el("button", "ghost small", "remover");
  del.addEventListener("click", () => removerModelo(m));
  acoes.append(testar, editar, del);
  ficha.append(acoes);

  const r = RESULTADOS[m.id];
  if (r) ficha.append(blocoTeste(r));
  return ficha;
}

function blocoTeste(r) {
  const cls = r.acertos === r.total ? "s-ok" : r.acertos ? "s-aviso" : "s-erro";
  const box = el("div", "mteste " + cls);
  const linhas = (r.detalhes || []).map((d) =>
    `<div class="mt-linha"><span class="mt-ico">${d.ok ? "✓" : "✗"}</span>` +
    `<span class="mt-tempo">${d.segundos}s</span>` +
    `<div><div class="mt-resp">${esc(String(d.resposta).slice(0, 130))}</div>` +
    (d.ok ? "" : `<div class="mt-motivo">${esc(d.motivo || "resposta ruim")}</div>`) +
    `</div></div>`).join("");
  box.innerHTML =
    `<div class="mt-top"><strong>${esc(r.veredito)}</strong>` +
    `<span>${r.acertos}/${r.total} · média ${r.media_segundos}s</span></div>` + linhas;
  return box;
}

async function usarModelo(id) {
  const r = await api("/api/modelos", { method: "POST", body: { acao: "ativar", id } });
  toast(r.msg || r.erro || "pronto", r.ok ? "ok" : "err");
  MODELOS = r.lista || MODELOS;
  renderCatalogo();
  await loadState();
}

async function testarModelo(id) {
  TESTANDO = id;
  renderCatalogo();
  try {
    const r = await api("/api/modelos", { method: "POST", body: { acao: "testar", id } });
    if (r.teste) RESULTADOS[id] = r.teste;
    toast(r.msg || r.erro || "teste concluído", r.teste && r.teste.acertos === r.teste.total ? "ok" : "err");
  } catch (e) {
    toast("não consegui testar: " + e, "err");
  }
  TESTANDO = "";
  renderCatalogo();
}

function editarModelo(m) {
  EDITANDO = m.id;
  $("#mApelido").value = m.apelido || "";
  $("#mNivel").value = String(m.nivel || 2);
  $("#mUrl").value = m.url || "";
  $("#mModelo").value = m.modelo || "";
  $("#mChave").value = "";
  $("#mChave").placeholder = m.tem_chave_propria
    ? `chave salva (${m.chave_mascarada}) — digite outra para trocar`
    : "vazio = usa a chave global";
  $("#mNota").value = m.nota || "";
  $("#mCancelar").style.display = "";
  $("#mSalvar").textContent = "Salvar alterações";
  $("#modelAdd").open = true;
  $("#mStatus").textContent = `editando "${m.apelido}"`;
  $("#modelAdd").scrollIntoView({ block: "nearest" });
}

function limparFormModelo() {
  EDITANDO = "";
  ["#mApelido", "#mUrl", "#mModelo", "#mChave", "#mNota"].forEach((s) => { $(s).value = ""; });
  $("#mChave").placeholder = "vazio = usa a chave global";
  $("#mNivel").value = "2";
  $("#mCancelar").style.display = "none";
  $("#mSalvar").textContent = "Salvar modelo";
  $("#mStatus").textContent = "";
  $("#mStatus").className = "status";
}

async function salvarModelo() {
  const st = $("#mStatus");
  st.className = "status";
  st.textContent = "salvando…";
  const r = await api("/api/modelos", {
    method: "POST",
    body: {
      acao: "salvar",
      id: EDITANDO,
      apelido: $("#mApelido").value.trim(),
      nivel: Number($("#mNivel").value || 2),
      url: $("#mUrl").value.trim(),
      modelo: $("#mModelo").value.trim(),
      chave: $("#mChave").value,
      nota: $("#mNota").value.trim(),
    },
  });
  if (!r.ok) {
    st.className = "status err";
    st.textContent = r.erro || r.msg || "não deu para salvar";
    return;
  }
  st.className = "status ok";
  st.textContent = r.msg;
  MODELOS = r.lista || MODELOS;
  limparFormModelo();
  renderCatalogo();
  await loadState();
  toast(r.msg, "ok");
}

async function removerModelo(m) {
  if (!confirm(`Remover "${m.apelido}" do catálogo? (a chave e a config global ficam como estão)`)) return;
  const r = await api("/api/modelos", { method: "POST", body: { acao: "remover", id: m.id } });
  toast(r.msg || r.erro || "pronto", r.ok ? "ok" : "err");
  MODELOS = r.lista || MODELOS;
  renderCatalogo();
  await loadState();
}

$("#btnModelo").addEventListener("click", async () => {
  $("#modelModal").classList.add("show");
  limparFormModelo();
  await carregarModelos();
});
$("#modelModalClose").addEventListener("click", () => $("#modelModal").classList.remove("show"));
$("#mSalvar").addEventListener("click", salvarModelo);
$("#mCancelar").addEventListener("click", limparFormModelo);
(function niveisSelect() {
  const sel = $("#mNivel");
  [[3, "🧠 Potente"], [2, "⚖️ Equilibrado"], [1, "⚡ Rápido"]].forEach(([v, rot]) => {
    const o = document.createElement("option");
    o.value = String(v);
    o.textContent = rot;
    sel.append(o);
  });
  sel.value = "2";
})();

/* ───────────────── init ───────────────── */
/* o campo cresce conforme você escreve (até 6 linhas) e volta ao normal */
(function campoCresce() {
  const ta = $("#prompt");
  const ajustar = () => {
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 132) + "px";
  };
  ta.addEventListener("input", () => {
    ajustar();
    // não adianta deixar "Enviar" aceso com o campo vazio
    const b = $("#btnEnviar");
    if (b) b.disabled = !ta.value.trim();
  });
  ta.addEventListener("blur", () => {
    if (!ta.value.trim()) ta.style.height = "auto";
  });
  // estado inicial: campo vazio = botão apagado
  const b0 = $("#btnEnviar");
  if (b0) b0.disabled = !ta.value.trim();
})();

/* Esc fecha qualquer modal aberto */
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  document.querySelectorAll(".modal.show").forEach((m) => m.classList.remove("show"));
});

/* atalho: Ctrl/Cmd + K foca o campo de digitar */
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    irPara("chat");
    $("#prompt").focus();
  }
});

/* estado vazio reutilizável */
function vazio(icone, titulo, texto) {
  return `<div class="vazio"><div class="vazio-ico">${icone}</div>` +
         `<strong>${esc(titulo)}</strong><p>${esc(texto)}</p></div>`;
}

/* rótulos de acessibilidade nas abas */
[...document.querySelectorAll("#tabbar .tab")].forEach((t) => {
  t.setAttribute("role", "tab");
  t.setAttribute("aria-label", t.querySelector("span").textContent);
});

/* ═══════════════════════ teste de saúde ═══════════════════════ */
const SAUDE_ICO = { ok: "✓", aviso: "!", erro: "✕" };

async function testarTudo() {
  const btn = $("#btnSaude");
  const lista = $("#saudeLista");
  const resumo = $("#saudeResumo");
  btn.disabled = true;
  btn.textContent = "testando…";
  resumo.textContent = "";
  resumo.className = "status";
  lista.innerHTML = '<div class="esqueleto"></div><div class="esqueleto"></div><div class="esqueleto"></div>';
  try {
    const d = await api("/api/saude");
    lista.innerHTML = "";
    (d.itens || []).forEach((i) => {
      const el2 = el("div", "saude-item s-" + i.estado);
      el2.innerHTML =
        `<div class="sdot">${SAUDE_ICO[i.estado] || "•"}</div>` +
        `<div class="scorpo"><div class="sname">${esc(i.nome)}</div>` +
        `<div class="sarg">${esc(i.detalhe)}</div>` +
        (i.dica ? `<div class="sarg dica">💡 ${esc(i.dica)}</div>` : "") + `</div>`;
      lista.append(el2);
    });
    resumo.textContent = d.resumo;
    resumo.className = "status " + (d.erros ? "err" : d.avisos ? "" : "ok");
  } catch (e) {
    lista.innerHTML = "";
    resumo.className = "status err";
    resumo.textContent = "não consegui rodar o teste: " + e;
  }
  btn.disabled = false;
  btn.textContent = "Testar tudo";
}
$("#btnSaude").addEventListener("click", testarTudo);

/* ───────────────── init ───────────────── */
loadState();
carregarLoja();
carregarSessoes();
renderSessaoBar();
setInterval(loadState, 20000);
