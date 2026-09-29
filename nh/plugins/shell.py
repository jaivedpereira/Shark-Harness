"""Plugin: shell — executa comandos no dispositivo (PC, Linux ou Termux).

Esta é a ferramenta que dá poder real ao harness. Por isso:
  - passa pela deny-list de `guard.check_command` (bloqueio duro)
  - tem timeout obrigatório (sem processo pendurado)
  - trunca a saída (para não estourar o contexto do modelo)
  - tudo fica no log de auditoria
"""

from __future__ import annotations

import os
import subprocess
from shutil import which as _which

from ..core import Registry, workspace
from ..guard import check_command
from ..paths import platform_name

MAX_OUT = 6000


def run_shell(command: str, cwd: str = "", timeout: int = 60) -> str:
    """Executa um comando de shell no dispositivo e devolve stdout + stderr.

    Este é o jeito direto de mexer no dispositivo: instalar pacote, rodar script,
    controlar serviços, usar git, mover arquivos, chamar adb/termux-api.
    Comandos destrutivos (rm -rf /, mkfs, dd no disco, fork bomb) são bloqueados.

    Args:
        command: o comando a executar (string única, como você digitaria no terminal).
        cwd: diretório de trabalho; vazio = workspace do harness.
        timeout: segundos antes de matar o processo.
    """
    check_command(command)
    workdir = cwd or str(workspace())

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=max(1, min(int(timeout), 600)),
        )
    except subprocess.TimeoutExpired:
        return f"⏱️ timeout de {timeout}s — processo morto.\nComando: {command}"
    except FileNotFoundError as exc:
        return f"ERRO: diretório de trabalho inválido ({workdir}): {exc}"

    parts = [f"$ {command}", f"(cwd: {workdir} · exit {proc.returncode})"]
    if proc.stdout.strip():
        parts.append(proc.stdout.rstrip())
    if proc.stderr.strip():
        parts.append("--- stderr ---\n" + proc.stderr.rstrip())

    out = "\n".join(parts)
    if len(out) > MAX_OUT:
        out = out[:MAX_OUT] + f"\n… (saída truncada, {len(out)} chars no total)"
    return out


def which(programa: str) -> str:
    """Diz se um programa/comando existe no PATH e onde está.

    Serve para o agente se auto-verificar antes de tentar usar algo
    (ex.: checar se `adb`, `git` ou `termux-notification` existem).

    Args:
        programa: nome do executável (ex.: "git", "python3", "adb").
    """
    path = _which(programa)
    if path:
        return f"✅ {programa}: {path}"
    return f"❌ {programa}: não encontrado no PATH ({platform_name()})"


def env_get(nome: str) -> str:
    """Lê uma variável de ambiente do processo (o VALOR é mascarado).

    Args:
        nome: nome da variável (ex.: "HOME", "PATH").
    """
    val = os.environ.get(nome)
    if val is None:
        return f"❌ variável {nome} não está definida"
    if any(s in nome.upper() for s in ("TOKEN", "KEY", "SECRET", "PASS", "SENHA")):
        return f"✅ {nome} está definida (valor oculto, {len(val)} chars)"
    return f"✅ {nome}={val[:300]}"


def register(reg: Registry) -> None:
    reg.add(run_shell, risk="exec", plugin="shell")
    reg.add(which, risk="safe", plugin="shell")
    reg.add(env_get, risk="safe", plugin="shell")
