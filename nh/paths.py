"""Diretórios, configuração e resolução de plataforma do Shark Harness.

Ordem de precedência da configuração (usada por `env()`):

  1. variável de ambiente `SHARK_<NOME>`
  2. variável de ambiente `NH_<NOME>`       (prefixo antigo, por compatibilidade)
  3. `~/.shark-harness/config.json`         (é onde a INTERFACE WEB grava a chave)
  4. o default passado para `env()`

O arquivo `.env` (na pasta do projeto ou em `~/.shark-harness/`) também é lido no
import — necessário no Windows, onde não existe `source .env`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


# --------------------------------------------------------------------- .env ---
def _carregar_env_arquivo(caminho: Path) -> None:
    """Lê KEY=VALUE de um .env e injeta no ambiente (sem sobrescrever o que já existe)."""
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


for _cand in (Path.cwd() / ".env", Path.home() / ".shark-harness" / ".env"):
    _carregar_env_arquivo(_cand)


# ----------------------------------------------------------------- caminhos ---
# HOME/WORKSPACE usam os.environ direto: servem para ACHAR o config.json, então
# não podem depender dele.
HOME = Path(
    os.environ.get("SHARK_HOME")
    or os.environ.get("NH_HOME")
    or (Path.home() / ".shark-harness")
)
JOBS_FILE = HOME / "jobs.json"
AUDIT_FILE = HOME / "audit.log"
CONFIG_FILE = HOME / "config.json"
WORKSPACE = Path(
    os.environ.get("SHARK_WORKSPACE")
    or os.environ.get("NH_WORKSPACE")
    or (Path.home() / "shark-workspace")
)

# nome da variável de ambiente -> chave correspondente no config.json
_CONFIG_KEYS = {
    "LLM_URL": "llm_url",
    "LLM_KEY": "llm_key",
    "LLM_MODEL": "llm_model",
    "MAX_RISK": "max_risk",
    "PROVIDER": "provider",
}

_config_cache: tuple[float, dict] | None = None


# ---------------------------------------------------------------- config.json ---
def read_config(forcar: bool = False) -> dict:
    """Lê ~/.shark-harness/config.json (com cache por mtime)."""
    global _config_cache
    try:
        if not CONFIG_FILE.is_file():
            return {}
        mtime = CONFIG_FILE.stat().st_mtime
        if _config_cache and _config_cache[0] == mtime and not forcar:
            return _config_cache[1]
        dados = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if not isinstance(dados, dict):
            return {}
        _config_cache = (mtime, dados)
        return dados
    except Exception:  # noqa: BLE001 — config quebrado não pode derrubar o harness
        return {}


def save_config(dados: dict) -> Path:
    """Grava o config.json com permissão 600 (o arquivo guarda a chave da API)."""
    ensure_dirs()
    CONFIG_FILE.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    try:
        CONFIG_FILE.chmod(0o600)
    except Exception:  # noqa: BLE001 — no Windows o chmod é limitado
        pass
    global _config_cache
    _config_cache = None
    return CONFIG_FILE


def update_config(**campos) -> dict:
    """Atualiza campos do config.json sem perder os outros. `None` remove o campo."""
    dados = dict(read_config(forcar=True))
    for chave, valor in campos.items():
        if valor is None:
            dados.pop(chave, None)
        else:
            dados[chave] = valor
    save_config(dados)
    return read_config(forcar=True)


# ----------------------------------------------------------------------- env ---
def env(nome: str, default: str = "") -> str:
    """Lê uma configuração seguindo a ordem de precedência documentada no topo."""
    valor = os.environ.get(f"SHARK_{nome}") or os.environ.get(f"NH_{nome}")
    if valor:
        return valor
    chave = _CONFIG_KEYS.get(nome)
    if chave:
        do_arquivo = read_config().get(chave)
        if do_arquivo:
            return str(do_arquivo)
    return default


# ------------------------------------------------------------------ utilidades ---
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
