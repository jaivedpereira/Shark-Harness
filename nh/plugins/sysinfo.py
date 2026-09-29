"""Plugin: sistema — relatório de saúde do aparelho (RAM, disco, bateria, uptime)."""


from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ..core import Registry
from ..paths import WORKSPACE, has_cmd, platform_name

MANIFEST = {
    "id": "sysinfo",
    "nome": "Saúde do sistema",
    "versao": "1.0.0",
    "autor": "jaivedpereira",
    "categoria": "sistema",
    "descricao": "RAM, disco, bateria, uptime e relógio — para saber se cabe tarefa pesada.",
    "risco_max": "safe",
    "plataformas": ["linux", "windows", "darwin", "android"],
    "requer": [],
    "tags": ["ram", "disco", "bateria"],
}


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def _meminfo() -> dict[str, int]:
    """Lê /proc/meminfo (Linux/Android)."""
    out: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, _, v = line.partition(":")
            parts = v.strip().split()
            if parts:
                out[k.strip()] = int(parts[0]) * 1024  # kB → bytes
    except Exception:
        pass
    return out


def _battery() -> str:
    plat = platform_name()
    if plat == "android" and has_cmd("termux-battery-status"):
        try:
            p = subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=15)
            if p.returncode == 0:
                import json

                d = json.loads(p.stdout)
                return f"{d.get('percentage', '?')}% ({d.get('status', '?').lower()}, {d.get('temperature', '?')}°C)"
        except Exception:
            pass
    for path in ("/sys/class/power_supply/BAT0", "/sys/class/power_supply/battery"):
        base = Path(path)
        try:
            cap = (base / "capacity").read_text().strip()
            st = (base / "status").read_text().strip() if (base / "status").exists() else "?"
            return f"{cap}% ({st.lower()})"
        except Exception:
            continue
    if plat == "windows" and has_cmd("powershell"):
        try:
            p = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_Battery).EstimatedChargeRemaining"],
                capture_output=True, text=True, timeout=20,
            )
            if p.returncode == 0 and p.stdout.strip():
                return f"{p.stdout.strip()}%"
        except Exception:
            pass
    return "n/d"


def sysinfo_report() -> str:
    """Relatório de saúde do aparelho: sistema, CPU, RAM, disco, bateria e uptime.

    Use antes de tarefas pesadas (ex.: saber se cabe subir um servidor) ou para
    monitorar o dispositivo.
    """
    plat = platform_name()
    lines = [
        "🖥️  RELATÓRIO DO DISPOSITIVO",
        f"plataforma : {plat} ({platform.system()} {platform.release()})",
        f"máquina    : {platform.machine()} · {os.cpu_count()} núcleo(s)",
        f"python     : {sys.version.split()[0]} ({sys.executable})",
    ]

    mem = _meminfo()
    if mem:
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", mem.get("MemFree", 0))
        used = max(0, total - avail)
        pct = (used / total * 100) if total else 0
        lines.append(f"RAM        : {_human(used)} usados de {_human(total)} ({pct:.0f}%)")
    elif plat == "windows":
        lines.append("RAM        : (n/d — use o Gerenciador de Tarefas)")

    try:
        total, used, free = shutil.disk_usage(str(Path.home()))
        lines.append(f"disco home : {_human(used)} usados de {_human(total)} ({_human(free)} livres)")
    except Exception:
        pass

    lines.append(f"bateria    : {_battery()}")
    try:
        up = float(Path("/proc/uptime").read_text().split()[0])
        h, m = divmod(int(up // 60), 60)
        lines.append(f"uptime     : {h}h{m:02d}min")
    except Exception:
        pass

    # usa o WORKSPACE de verdade (antes tinha "nh-workspace" na mão, da marca antiga,
    # e Path.home() — que no Termux pode cair em `/`)
    lines.append(f"workspace  : {WORKSPACE}")

    return "\n".join(lines)


def disk_usage(caminho: str = "") -> str:
    """Mostra quanto espaço um diretório (ou o home) está usando.

    Args:
        caminho: pasta a medir; vazio = home do usuário.
    """
    target = Path(caminho).expanduser() if caminho else WORKSPACE.parent
    if not target.exists():
        return f"❌ não existe: {target}"
    try:
        total, used, free = shutil.disk_usage(str(target))
    except Exception as exc:  # noqa: BLE001
        return f"ERRO: {exc}"
    pct = used / total * 100 if total else 0
    return (
        f"💾 {target}\n"
        f"   total: {_human(total)}\n"
        f"   usado: {_human(used)} ({pct:.0f}%)\n"
        f"   livre: {_human(free)}"
    )


def clock() -> str:
    """Retorna a data e hora atuais do dispositivo."""
    return time.strftime("🕐 %Y-%m-%d %H:%M:%S (%A)")


def register(reg: Registry) -> None:
    reg.add(sysinfo_report, risk="safe", plugin="sysinfo")
    reg.add(disk_usage, risk="safe", plugin="sysinfo")
    reg.add(clock, risk="safe", plugin="sysinfo")
