"""Diretórios e resolução de plataforma do nano-harness."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _carregar_env_arquivo(caminho: Path) -> None:
    """Lê KEY=VALUE de um .env e injeta no ambiente (sem sobrescrever o que já existe).

    Isso faz o .env funcionar em qualquer frente (CLI, web, agente) e em qualquer
    sistema — no Windows não existe `source .env`, então o carregamento tem que
    ser do próprio Python.
    """
    try:
        if not caminho.is_file():
            return
        for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            chave = chave.strip()
            valor = valor.strip().strip('"').strip("'")
            if chave and chave not in os.environ:
                os.environ[chave] = valor
    except Exception:  # noqa: BLE001 — .env quebrado nunca deve derrubar o harness
        pass


# ordem: ./.env (pasta do projeto) e depois ~/.shark-harness/.env
for _cand in (Path.cwd() / ".env", Path.home() / ".shark-harness" / ".env"):
    _carregar_env_arquivo(_cand)

def env(nome: str, default: str = "") -> str:
    """Lê config aceitando os dois prefixos: SHARK_<nome> e depois NH_<nome>.

    O prefixo passou de NH_ (nano-harness) para SHARK_ ao virar Shark Harness;
    aceitar os dois mantém configs e scripts antigos funcionando.
    """
    return os.environ.get(f"SHARK_{nome}") or os.environ.get(f"NH_{nome}") or default


HOME = Path(env("HOME") or (Path.home() / ".shark-harness"))

JOBS_FILE = HOME / "jobs.json"
AUDIT_FILE = HOME / "audit.log"
WORKSPACE = Path(env("WORKSPACE") or (Path.home() / "shark-workspace"))


def ensure_dirs() -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    WORKSPACE.mkdir(parents=True, exist_ok=True)


def platform_name() -> str:
    """'android' (Termux), 'windows', 'linux' ou 'darwin'."""
    if "com.termux" in os.environ.get("PREFIX", "") or os.path.isdir("/data/data/com.termux"):
        return "android"
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def has_cmd(name: str) -> bool:
    from shutil import which

    return which(name) is not None
