"""Gera os gráficos do catálogo do Shark Harness (matplotlib)."""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "pdf_build"
SAIDA.mkdir(exist_ok=True)

AZUL = "#2563eb"
AZUL_CLARO = "#93c5fd"
ESCURO = "#0f172a"
CINZA = "#64748b"
CORES_RISCO = {"safe": "#22c55e", "write": "#eab308", "exec": "#f97316", "danger": "#ef4444"}

dados = json.loads((RAIZ / "catalogo_tools.json").read_text(encoding="utf-8"))
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": "#cbd5e1"})


def salvar(fig, nome):
    caminho = SAIDA / nome
    fig.savefig(caminho, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  ", nome)


# ── 1. ferramentas por plugin ────────────────────────────────────────────────
plugins = sorted(dados["plugins"], key=lambda p: p["qtd"])
fig, ax = plt.subplots(figsize=(7.6, 4.0))
y = range(len(plugins))
ax.barh(list(y), [p["qtd"] for p in plugins], color=AZUL, height=0.62, zorder=3)
ax.set_yticks(list(y))
ax.set_yticklabels([p["titulo"] for p in plugins], fontsize=10)
ax.set_xlabel("quantidade de ferramentas")
ax.set_title("Ferramentas por área", fontsize=12, fontweight="bold", color=ESCURO, pad=12)
ax.grid(axis="x", ls=":", alpha=0.55, zorder=0)
ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
for i, p in enumerate(plugins):
    ax.text(p["qtd"] + 0.12, i, str(p["qtd"]), va="center", fontsize=10,
            fontweight="bold", color=AZUL)
ax.set_xlim(0, max(p["qtd"] for p in plugins) + 1)
salvar(fig, "grafico_areas.png")

# ── 2. distribuição de risco ─────────────────────────────────────────────────
contagem = {}
for t in dados["tools"]:
    contagem[t["risco"]] = contagem.get(t["risco"], 0) + 1
ordem = ["safe", "write", "exec", "danger"]
rotulos = {"safe": "Só leitura", "write": "Escreve arquivo", "exec": "Executa comando", "danger": "Apaga / perigoso"}
valores = [contagem.get(r, 0) for r in ordem]

fig, ax = plt.subplots(figsize=(7.6, 3.4))
barras = ax.bar([rotulos[r] for r in ordem], valores,
                color=[CORES_RISCO[r] for r in ordem], width=0.6, zorder=3)
ax.set_title("Distribuição por nível de risco", fontsize=12, fontweight="bold", color=ESCURO, pad=12)
ax.set_ylabel("ferramentas")
ax.grid(axis="y", ls=":", alpha=0.55, zorder=0)
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for b, v in zip(barras, valores):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.25, str(v), ha="center",
            fontweight="bold", color=ESCURO)
ax.set_ylim(0, max(valores) + 2)
salvar(fig, "grafico_risco.png")

# ── 3. diagrama: um registro, quatro frentes ─────────────────────────────────
fig, ax = plt.subplots(figsize=(7.6, 3.5))
ax.axis("off")
ax.set_xlim(0, 10)
ax.set_ylim(0, 5)

ax.add_patch(Rectangle((3.35, 2.05), 3.3, 1.0, facecolor=AZUL, edgecolor="none", zorder=3))
ax.text(5.0, 2.55, "1 registro de ferramentas", ha="center", va="center",
        color="white", fontsize=11.5, fontweight="bold", zorder=4)

frentes = [
    (0.55, "Interface web", "o painel azul no navegador"),
    (2.85, "Servidor MCP", "Claude Code, Cursor"),
    (5.15, "Linha de comando", "nh run | do | cron"),
    (7.45, "Agente (LLM)", "decide e executa sozinho"),
]
for x, titulo, sub in frentes:
    ax.add_patch(Rectangle((x, 0.55), 2.0, 1.0, facecolor="#eff6ff",
                               edgecolor=AZUL, linewidth=1.4, zorder=3))
    ax.text(x + 1.0, 1.14, titulo, ha="center", va="center", fontsize=10,
            fontweight="bold", color=ESCURO, zorder=4)
    ax.text(x + 1.0, 0.8, sub, ha="center", va="center", fontsize=7.6, color=CINZA, zorder=4)
    ax.annotate("", xy=(x + 1.0, 1.55), xytext=(5.0, 2.05),
                arrowprops=dict(arrowstyle="-|>", color=AZUL, lw=1.5,
                                connectionstyle="arc3,rad=0.12"), zorder=2)
ax.text(5.0, 4.6, "Um só conjunto de ferramentas, quatro formas de usar",
        ha="center", fontsize=12, fontweight="bold", color=ESCURO)
salvar(fig, "diagrama_frentes.png")

# ── 4. fluxo de segurança (o que a guarda bloqueia x o que passa) ────────────
fig, ax = plt.subplots(figsize=(7.6, 2.7))
ax.axis("off")
ax.set_xlim(0, 10)
ax.set_ylim(0, 3)

ax.add_patch(Rectangle((0.2, 0.45), 3.0, 1.9, facecolor="#f0fdf4",
                           edgecolor="#22c55e", linewidth=1.4))
ax.text(1.7, 2.1, "PASSA", ha="center", fontsize=10.5, fontweight="bold", color="#15803d")
ax.text(1.7, 1.25, "ls, git, python,\ntar, criar arquivo\nno workspace",
        ha="center", va="center", fontsize=8.6, color=ESCURO)

ax.annotate("", xy=(4.0, 1.4), xytext=(3.3, 1.4),
            arrowprops=dict(arrowstyle="-|>", color="#94a3b8", lw=2))

ax.add_patch(Rectangle((4.1, 0.45), 2.6, 1.9, facecolor="#eff6ff",
                           edgecolor=AZUL, linewidth=1.6))
ax.text(5.4, 2.1, "A GUARDA", ha="center", fontsize=10.5, fontweight="bold", color=AZUL)
ax.text(5.4, 1.25, "deny-list de comandos\ne de caminhos\n+ log de auditoria",
        ha="center", va="center", fontsize=8.6, color=ESCURO)

ax.annotate("", xy=(7.4, 1.4), xytext=(6.8, 1.4),
            arrowprops=dict(arrowstyle="-|>", color="#94a3b8", lw=2))

ax.add_patch(Rectangle((7.5, 0.45), 2.3, 1.9, facecolor="#fef2f2",
                           edgecolor="#ef4444", linewidth=1.4))
ax.text(8.65, 2.1, "BLOQUEIA", ha="center", fontsize=10.5, fontweight="bold", color="#b91c1c")
ax.text(8.65, 1.25, "rm -rf /  ·  mkfs\ndd no disco  ·  curl|sh\n~/.bashrc  ·  chaves SSH",
        ha="center", va="center", fontsize=8.2, color=ESCURO)
salvar(fig, "diagrama_guarda.png")

print("✅ gráficos prontos")
