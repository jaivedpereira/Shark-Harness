"""Plugin: git — versionamento de verdade, sem abrir o terminal.

O agente passa a saber o estado do repositório, ver o diff, commitar e subir. As
ferramentas de leitura (status, log, diff, branch) são risco 'safe' — só olham.
As que mexem no repositório (commit, pull, push, checkout) são 'exec' e passam
pela guarda: force-push em main continua bloqueado.
"""

from __future__ import annotations

import subprocess

MANIFEST = {
    "id": "git",
    "nome": "Git",
    "versao": "1.0.0",
    "autor": "jaivedpereira",
    "categoria": "dev",
    "descricao": "Status, log, diff, commit, pull, push e branches do repositório atual.",
    "risco_max": "exec",
    "plataformas": ["linux", "windows", "darwin", "android"],
    "requer": ["git"],
    "tags": ["git", "versionamento", "desenvolvimento"],
}


def _rodar(pasta: str, *args: str, timeout: int = 120) -> tuple[int, str]:
    """Roda git em modo lista (nunca shell=True) e devolve (código, saída)."""
    cmd = ["git"] + list(args)
    try:
        r = subprocess.run(cmd, cwd=(pasta or None), capture_output=True,
                           text=True, timeout=max(5, min(int(timeout), 600)))
    except FileNotFoundError:
        return 127, "❌ git não está instalado (no Termux: pkg install git)"
    except subprocess.TimeoutExpired:
        return 124, "❌ git demorou demais e foi interrompido."
    saida = (r.stdout or "") + (r.stderr or "")
    return r.returncode, saida.strip()


def _cabecalho(pasta: str) -> str:
    _, raiz = _rodar(pasta, "rev-parse", "--show-toplevel")
    _, ramo = _rodar(pasta, "rev-parse", "--abbrev-ref", "HEAD")
    return f"📁 {raiz or pasta} · ramo {ramo or '—'}"


def git_status(pasta: str = ".") -> str:
    """Mostra o que mudou no repositório (arquivos novos, alterados e prontos).

    Args:
        pasta: pasta do repositório (vazio = pasta atual).
    """
    codigo, saida = _rodar(pasta, "status", "--short", "--branch")
    if codigo == 128:
        return f"❌ {pasta} não é um repositório git."
    if codigo != 0:
        return f"❌ git status falhou:\n{saida}"
    linhas = saida.splitlines() or []
    if len(linhas) <= 1:
        return f"{_cabecalho(pasta)}\n✅ nada pendente — repositório limpo."
    return f"{_cabecalho(pasta)}\n{saida}"


def git_log(pasta: str = ".", limite: int = 10) -> str:
    """Últimos commits (hash curto, data, autor e mensagem).

    Args:
        pasta: pasta do repositório.
        limite: quantos commits mostrar.
    """
    codigo, saida = _rodar(pasta, "log", f"-{max(1, min(int(limite), 100))}",
                           "--pretty=format:%h  %ad  %an  %s", "--date=short")
    if codigo != 0:
        return f"❌ {saida or 'não é um repositório git.'}"
    n_linhas = len(saida.splitlines())
    return f"📜 últimos {n_linhas} commits:\n" + "\n".join("  " + l for l in saida.splitlines())


def git_diff(pasta: str = ".", staged: bool = False, arquivo: str = "") -> str:
    """Mostra exatamente o que mudou no código (útil antes de commitar).

    Args:
        pasta: pasta do repositório.
        staged: True para ver o que já está marcado para commit.
        arquivo: limita o diff a um arquivo.
    """
    args = ["diff", "--stat", "--patch"]
    if staged:
        args.append("--cached")
    if arquivo:
        args += ["--", arquivo]
    codigo, saida = _rodar(pasta, *args)
    if codigo != 0:
        return f"❌ {saida}"
    if not saida:
        return "✅ nenhuma diferença" + (" no que está marcado (staged)" if staged else "")
    if len(saida) > 6000:
        saida = saida[:6000] + f"\n… (diff cortado, {len(saida)} chars no total)"
    return saida


def git_commit(pasta: str = ".", mensagem: str = "", tudo: bool = True) -> str:
    """Marca as mudanças e cria o commit. Sem mensagem, não faz nada.

    Args:
        pasta: pasta do repositório.
        mensagem: texto do commit (obrigatório).
        tudo: True marca todos os arquivos alterados (git add -A) antes de commitar.
    """
    if not str(mensagem).strip():
        return "❌ preciso de uma mensagem de commit."
    if tudo:
        codigo, saida = _rodar(pasta, "add", "-A")
        if codigo != 0:
            return f"❌ git add falhou: {saida}"
    codigo, saida = _rodar(pasta, "commit", "-m", str(mensagem).strip())
    if codigo != 0:
        return f"❌ commit não saiu:\n{saida}"
    _, resumo = _rodar(pasta, "log", "-1", "--pretty=format:%h %s")
    return f"✅ commit criado: {resumo.splitlines()[0] if resumo else saida}"


def git_pull(pasta: str = ".") -> str:
    """Traz as mudanças do repositório remoto para o local.

    Args:
        pasta: pasta do repositório.
    """
    codigo, saida = _rodar(pasta, "pull")
    return (f"✅ atualizado:\n{saida}" if codigo == 0 else f"❌ git pull falhou:\n{saida}")


def git_push(pasta: str = ".", ramo: str = "", forcar: bool = False) -> str:
    """Envia os commits para o repositório remoto (force-push em main é bloqueado).

    Args:
        pasta: pasta do repositório.
        ramo: ramo de destino (vazio = o ramo atual).
        forcar: True tenta force-push — bloqueado pela guarda em main/master.
    """
    args = ["push"]
    if forcar:
        args.append("--force-with-lease")
    if ramo:
        args += ["origin", str(ramo)]
    codigo, saida = _rodar(pasta, *args)
    if codigo == 0:
        return f"✅ enviado:\n{saida or '(sem novidades para enviar)'}"
    return f"❌ git push falhou:\n{saida}"


def git_branch(pasta: str = ".") -> str:
    """Lista os ramos locais e mostra em qual você está.

    Args:
        pasta: pasta do repositório.
    """
    codigo, saida = _rodar(pasta, "branch", "-vv")
    if codigo != 0:
        return f"❌ {saida or 'não é um repositório git.'}"
    return "🌿 ramos:\n" + "\n".join("  " + l for l in saida.splitlines())


def register(reg) -> None:
    reg.add(git_status, risk="safe", plugin="git")
    reg.add(git_log, risk="safe", plugin="git")
    reg.add(git_diff, risk="safe", plugin="git")
    reg.add(git_branch, risk="safe", plugin="git")
    reg.add(git_commit, risk="exec", plugin="git")
    reg.add(git_pull, risk="exec", plugin="git")
    reg.add(git_push, risk="exec", plugin="git")
