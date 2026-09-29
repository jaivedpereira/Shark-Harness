"""Sessões — cada uma aponta para uma PASTA de projeto, tipo Claude Code.

Uma sessão guarda:

  • a pasta onde o agente trabalha (todas as ferramentas passam a enxergar ali)
  • o histórico da conversa daquela pasta (o agente lembra o que já fez)
  • nome, modelo (opcional) e datas

Fica tudo em `~/.shark-harness/sessions.json`. A pasta NÃO precisa ser o workspace
do harness: você aponta para qualquer projeto (o repo clonado, a pasta de estudo,
o /storage/... no celular).

O que faz a diferença em relação a um chat solto: ao abrir a sessão o agente recebe
um **resumo do projeto** (árvore de arquivos + ramo do git + começo do README), então
ele já sabe com o que está lidando antes da primeira pergunta.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from .paths import HOME

SESSOES_FILE = HOME / "sessions.json"
MAX_MENSAGENS = 60  # histórico guardado por sessão (o suficiente para manter o fio)

# pastas que nunca entram no resumo do projeto
IGNORAR = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
           ".next", ".cache", ".pytest_cache", "target", ".idea", ".vscode"}
LIMITE_ARQUIVOS = 70


def _ler() -> dict:
    if not SESSOES_FILE.is_file():
        return {"sessoes": []}
    try:
        d = json.loads(SESSOES_FILE.read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("sessoes"), list):
            return d
    except Exception:  # noqa: BLE001
        pass
    return {"sessoes": []}


def _gravar(d: dict) -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    SESSOES_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------- CRUD ---
def criar(nome: str, pasta: str, modelo: str = "") -> dict:
    """Cria uma sessão apontando para uma pasta de projeto."""
    p = Path(pasta).expanduser()
    if not p.is_dir():
        raise NotADirectoryError(f"não achei a pasta: {p}")
    p = p.resolve()
    d = _ler()
    s = {
        "id": uuid.uuid4().hex[:10],
        "nome": (nome or "").strip() or p.name,
        "pasta": str(p),
        "modelo": modelo or "",
        "criado": time.time(),
        "atualizado": time.time(),
        "historico": [],
    }
    d["sessoes"].append(s)
    _gravar(d)
    return s


def listar() -> list[dict]:
    """Todas as sessões, sem o histórico (só o resumo de cada uma)."""
    saida = []
    for s in _ler()["sessoes"]:
        s = dict(s)
        hist = s.pop("historico", []) or []
        s["mensagens"] = len(hist)
        s["ultima"] = (hist[-1].get("content") or "")[:120] if hist else ""
        s["existe"] = Path(str(s.get("pasta", ""))).is_dir()
        saida.append(s)
    saida.sort(key=lambda x: -float(x.get("atualizado") or 0))
    return saida


def obter(sid: str) -> dict | None:
    """Uma sessão completa (com histórico)."""
    for s in _ler()["sessoes"]:
        if s.get("id") == sid:
            return s
    return None


def por_pasta(pasta: str) -> dict | None:
    """Acha a sessão daquela pasta, se existir."""
    alvo = str(Path(pasta).expanduser().resolve())
    for s in _ler()["sessoes"]:
        if str(s.get("pasta")) == alvo:
            return s
    return None


def apagar(sid: str) -> str:
    """Apaga a sessão (a pasta do projeto NÃO é tocada)."""
    d = _ler()
    antes = len(d["sessoes"])
    d["sessoes"] = [s for s in d["sessoes"] if s.get("id") != sid]
    if len(d["sessoes"]) == antes:
        return f"❌ sessão '{sid}' não existe."
    _gravar(d)
    return f"🗑️ sessão '{sid}' apagada (a pasta do projeto continua intacta)."


def renomear(sid: str, nome: str) -> str:
    """Troca o nome de uma sessão."""
    d = _ler()
    for s in d["sessoes"]:
        if s.get("id") == sid:
            s["nome"] = (nome or "").strip() or s["nome"]
            s["atualizado"] = time.time()
            _gravar(d)
            return f"✅ sessão renomeada para '{s['nome']}'."
    return f"❌ sessão '{sid}' não existe."


def definir_modelo(sid: str, modelo: str) -> str:
    """Fixa um modelo para a sessão (vazio = usa o global)."""
    d = _ler()
    for s in d["sessoes"]:
        if s.get("id") == sid:
            s["modelo"] = (modelo or "").strip()
            _gravar(d)
            return f"✅ modelo da sessão: {s['modelo'] or '(o global)'}"
    return f"❌ sessão '{sid}' não existe."


# ---------------------------------------------------------------- histórico ---
def guardar_historico(sid: str, mensagens: list) -> None:
    """Grava o histórico da conversa (mantém só as últimas MAX_MENSAGENS)."""
    d = _ler()
    for s in d["sessoes"]:
        if s.get("id") == sid:
            corte = list(mensagens)[-MAX_MENSAGENS:]
            s["historico"] = corte
            s["atualizado"] = time.time()
            _gravar(d)
            return


def limpar_historico(sid: str) -> str:
    """Zera a conversa da sessão, mantendo a pasta e o nome."""
    d = _ler()
    for s in d["sessoes"]:
        if s.get("id") == sid:
            s["historico"] = []
            s["atualizado"] = time.time()
            _gravar(d)
            return f"🧹 conversa da sessão '{s['nome']}' limpa (a pasta continua a mesma)."
    return f"❌ sessão '{sid}' não existe."


# ------------------------------------------------------------------ contexto ---
def arvore(pasta: str, limite: int = LIMITE_ARQUIVOS) -> str:
    """Árvore de arquivos da pasta (sem as pastas de ruído), para mostrar na tela."""
    raiz = Path(pasta).expanduser()
    if not raiz.is_dir():
        return "(pasta não encontrada)"
    linhas: list[str] = []
    total = 0
    for item in sorted(raiz.rglob("*")):
        partes = set(item.relative_to(raiz).parts)
        if partes & IGNORAR:
            continue
        rel = item.relative_to(raiz)
        prof = len(rel.parts) - 1
        if prof > 3:
            continue
        total += 1
        if total > limite:
            linhas.append("   …")
            break
        if item.is_dir():
            linhas.append("   " * prof + f"{item.name}/")
        else:
            try:
                kb = item.stat().st_size / 1024
            except OSError:
                kb = 0
            linhas.append("   " * prof + f"{item.name} ({kb:.0f} KB)")
    return "\n".join(linhas) or "(pasta vazia)"


def contexto(pasta: str) -> str:
    """Resumo do projeto que vai no system prompt: arquivos, git e README."""
    raiz = Path(pasta).expanduser()
    if not raiz.is_dir():
        return ""
    partes = [f"Você está trabalhando na pasta: {raiz}",
              "Todos os caminhos relativos das ferramentas apontam para essa pasta.", ""]

    # arquivos do topo (o mapa do projeto)
    try:
        arquivos = []
        for item in sorted(raiz.iterdir()):
            if item.name in IGNORAR or item.name.startswith("."):
                continue
            arquivos.append(f"{item.name}/" if item.is_dir() else item.name)
        if arquivos:
            partes.append("Conteúdo da pasta (nível 1): " + ", ".join(arquivos[:40]))
    except Exception:  # noqa: BLE001
        pass

    # é repositório git?
    try:
        import subprocess

        ramo = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=raiz,
                              capture_output=True, text=True, timeout=10)
        if ramo.returncode == 0 and ramo.stdout.strip():
            partes.append(f"É um repositório git, no ramo '{ramo.stdout.strip()}'.")
    except Exception:  # noqa: BLE001
        pass

    # README dá o tom do projeto
    for nome in ("README.md", "readme.md", "README.txt", "LEIAME.md"):
        alvo = raiz / nome
        if alvo.is_file():
            try:
                texto = alvo.read_text(encoding="utf-8", errors="replace")
                partes.append(f"\nComeço do {nome}:\n" + texto[:1200])
            except Exception:  # noqa: BLE001
                pass
            break
    return "\n".join(partes)


__all__ = ["criar", "listar", "obter", "por_pasta", "apagar", "renomear", "definir_modelo",
           "guardar_historico", "limpar_historico", "arvore", "contexto", "SESSOES_FILE"]
