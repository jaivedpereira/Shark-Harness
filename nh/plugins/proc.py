"""Plugin: processos e serviços — ver o que está rodando e derrubar o que travou.

Fecha o ciclo de "monstrar utilidades": o agente consegue descobrir que um
servidor caiu (`port_check`), ver o processo (`processos`) e reiniciar/derrubar
(`matar_processo`).
"""

from __future__ import annotations

import os
import signal
import subprocess

from ..core import Registry
from ..paths import has_cmd, platform_name

# processos que NUNCA matamos por engano: derrubam a máquina ou a própria sessão
PROTEGIDOS = ("systemd", "init", "kernel", "launchd", "wininit", "csrss", "winlogon",
              "services.exe", "lsass", "svchost", "explorer.exe", "termux", "com.termux")


def processos(filtro: str = "", limite: int = 25) -> str:
    """Lista os processos em execução (nome, PID, memória, CPU).

    Args:
        filtro: texto para filtrar pelo nome/comando (vazio = todos).
        limite: máximo de linhas.
    """
    try:
        import psutil  # opcional
    except ImportError:
        psutil = None  # type: ignore[assignment]

    linhas = []
    if psutil is not None:
        for p in psutil.process_iter(["pid", "name", "memory_info", "cmdline"]):
            try:
                info = p.info
                cmd = " ".join(info.get("cmdline") or []) or (info.get("name") or "")
                if filtro and filtro.lower() not in cmd.lower():
                    continue
                mb = 0.0
                mem = info.get("memory_info")
                if mem is not None:
                    mb = mem.rss / 1024 / 1024
                linhas.append((mb, f"  {info['pid']:>7}  {mb:>7.1f}MB  {cmd.strip()[:110]}"))
            except Exception:  # noqa: BLE001
                continue
        linhas.sort(reverse=True)
        corpo = [t for _, t in linhas[: int(limite)]]
        return (f"⚙️ {len(linhas)} processo(s)" + (f" com '{filtro}'" if filtro else "") +
                f" · maiores por memória:\n" + "\n".join(corpo))

    # sem psutil: usa o sistema
    plat = platform_name()
    if plat == "windows":
        cmd = ["powershell", "-NoProfile", "-Command",
               "Get-Process | Sort-Object WS -Descending | Select-Object -First %d "
               "Id,ProcessName,@{n='MB';e={[math]::Round($_.WS/1MB,1)}} | Format-Table -AutoSize" % int(limite)]
    else:
        cmd = ["sh", "-c", f"ps -eo pid,rss,args --sort=-rss 2>/dev/null | head -{int(limite) + 1}"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
    except Exception as exc:  # noqa: BLE001
        return f"❌ não consegui listar processos: {exc}"
    if filtro:
        out = "\n".join(l for l in out.splitlines() if filtro.lower() in l.lower())
    return f"⚙️ processos" + (f" com '{filtro}'" if filtro else "") + ":\n" + (out.strip() or "(nada)")


def matar_processo(pid: int, forcar: bool = False) -> str:
    """Encerra um processo pelo PID (use `processos` antes para achar o número).

    Args:
        pid: número do processo (PID).
        forcar: True para forçar (SIGKILL / /F) se o educado não resolver.
    """
    if int(pid) <= 1:
        return "🛑 bloqueado: PID 1 (ou inválido) derruba o sistema."
    try:
        nome = ""
        try:
            import psutil

            nome = psutil.Process(int(pid)).name()
        except Exception:  # noqa: BLE001
            if platform_name() == "windows":
                nome = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}"],
                                      capture_output=True, text=True, timeout=20).stdout
        if any(x in nome.lower() for x in PROTEGIDOS):
            return f"🛑 bloqueado: '{nome}' é um processo do sistema — recusei matar."
    except Exception:  # noqa: BLE001
        pass

    try:
        if platform_name() == "windows":
            args = ["taskkill", "/PID", str(int(pid))] + (["/F"] if forcar else [])
        else:
            args = ["kill", "-9" if forcar else "-15", str(int(pid))]
        p = subprocess.run(args, capture_output=True, text=True, timeout=20)
    except Exception as exc:  # noqa: BLE001
        return f"❌ falha ao encerrar: {type(exc).__name__}: {exc}"
    if p.returncode == 0:
        return f"✅ processo {pid} encerrado{' (forçado)' if forcar else ''}."
    return f"❌ não consegui encerrar {pid}: {(p.stderr or p.stdout or '').strip()[:160]}"


def meus_processos() -> str:
    """Mostra o que o próprio Shark Harness está rodando (scheduler, interface)."""
    achados = []
    try:
        out = subprocess.run(["sh", "-c", "ps -eo pid,args 2>/dev/null | grep -i 'nh ' | grep -v grep"],
                             capture_output=True, text=True, timeout=20).stdout
        achados = [l.strip()[:120] for l in out.splitlines() if l.strip()]
    except Exception:  # noqa: BLE001
        pass
    if not achados:
        return "ℹ️ não achei processos do Shark Harness rodando (o scheduler e a interface estão parados)."
    return "🦈 processos do Shark Harness:\n" + "\n".join(f"  {a}" for a in achados)


def register(reg: Registry) -> None:
    reg.add(processos, risk="safe", plugin="proc")
    reg.add(meus_processos, risk="safe", plugin="proc")
    reg.add(matar_processo, risk="danger", plugin="proc")
