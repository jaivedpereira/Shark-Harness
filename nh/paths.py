"""Diretórios e resolução de plataforma do nano-harness."""

from __future__ import annotations

import os
import sys
from pathlib import Path

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
