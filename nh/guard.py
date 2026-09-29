"""Guardas de segurança do nano-harness.

Um agente que roda comandos pode destruir a máquina. Estas guardas existem para
tornar o dano acidental (ou um modelo alucinando) muito menos provável:

  1. deny-list de comandos destrutivos  → bloqueio duro, nem com --yolo passa
  2. deny-list de caminhos críticos     → escrita proibida em /etc, chaves SSH,
                                          ~/.bashrc, crontab do sistema etc.
  3. log de auditoria append-only       → todo comando executado fica registrado
  4. níveis de risco por ferramenta     → 'safe' | 'write' | 'exec' | 'danger'

Isto NÃO é uma sandbox. Sandbox de verdade = container/VM. Ver SAFETY no README.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from .paths import AUDIT_FILE, ensure_dirs

# ---------------------------------------------------------------- deny-list ---

# Comandos que podem apagar a máquina / se auto-espalhar. Bloqueio incondicional.
DENY_PATTERNS: list[tuple[str, str]] = [
    (r"rm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*[rf][a-zA-Z]*\s+/(\s|$)", "rm -rf na raiz /"),
    (r"rm\s+-[a-zA-Z]*\s+--no-preserve-root", "rm --no-preserve-root"),
    (r"\bmkfs(\.\w+)?\b", "formatação de filesystem (mkfs)"),
    (r"\bdd\b[^\n]*of=/dev/(sd|nvme|hd|mmcblk|vd)", "dd escrevendo direto no disco"),
    (r">\s*/dev/(sd|nvme|hd|mmcblk|vd)", "redirecionamento para dispositivo de bloco"),
    (r":\(\)\s*\{.*\};\s*:", "fork bomb"),
    (r"\b(shutdown|poweroff|halt|reboot)\b", "desligar/reiniciar a máquina"),
    (r"chmod\s+(-R\s+)?0?777\s+/(\s|$)", "chmod 777 na raiz"),
    (r"chown\s+(-R\s+)?[^\s]+\s+/(\s|$)", "chown na raiz"),
    (r"\b(curl|wget)\b[^|;\n]*\|\s*(sudo\s+)?(ba|z|d|k)?sh\b", "baixar script e executar (curl|sh)"),
    (r"base64\s+-d[^|;\n]*\|\s*(ba)?sh", "payload ofuscado em base64"),
    (r"\beval\s*\$?\(?\s*(curl|wget)", "eval de download remoto"),
    (r"\biptables\b|\bnft\b\s+flush|\bufw\b\s+disable", "alteração de firewall"),
    (r"\buserdel\b|\bpasswd\b\s+-d|\bvisudo\b", "alteração de usuários/sudo"),
    (r"history\s+-c\b|>\s*~?/?\.bash_history|truncate\s+-s\s*0\s+~?/?\.bash_history", "apagar rastro (histórico)"),
    (r"git\s+push[^\n]*--force[^\n]*\b(main|master)\b", "force-push em main/master"),
]

# Caminhos onde NUNCA escrevemos: vetores clássicos de persistência/sequestro.
DENY_PATHS: list[str] = [
    "/etc/passwd",
    "/etc/shadow",
    "/etc/sudoers",
    "/etc/hosts",
    "/etc/crontab",
    "/etc/rc.local",
    "/boot/",
    "/sys/",
    "/proc/sys/",
    "/dev/",
]

# Nomes de arquivo (em qualquer lugar) que não podem ser criados/alterados:
# são os pontos onde código malicioso se esconde para rodar de novo no boot.
DENY_BASENAMES: list[str] = [
    ".bashrc",
    ".bash_profile",
    ".zshrc",
    ".profile",
    ".ssh/authorized_keys",
    "id_rsa",
    "id_ed25519",
]


class GuardError(RuntimeError):
    """Levantado quando uma ação é bloqueada pela guarda."""


def check_command(cmd: str) -> None:
    """Bloqueia comandos destrutivos. Levanta GuardError."""
    flat = " ".join(cmd.split())
    for pattern, why in DENY_PATTERNS:
        if re.search(pattern, flat, flags=re.IGNORECASE):
            raise GuardError(
                f"BLOQUEADO pela guarda: {why}. "
                f"Se for intencional, rode fora do Shark Harness."
            )


def check_path(path: str | Path, *, writing: bool = True) -> Path:
    """Normaliza e valida um caminho de escrita. Levanta GuardError."""
    p = Path(path).expanduser()
    try:
        p = p.resolve()
    except OSError:
        p = Path(os.path.abspath(str(p)))

    if not writing:
        return p

    s = str(p)
    for bad in DENY_PATHS:
        if s == bad.rstrip("/") or s.startswith(bad):
            raise GuardError(f"BLOQUEADO pela guarda: escrita em caminho crítico ({bad}).")
    for bad in DENY_BASENAMES:
        if s.endswith("/" + bad) or s == bad:
            raise GuardError(
                f"BLOQUEADO pela guarda: não escrevo em {bad} "
                f"(vetor de persistência automática)."
            )
    return p


# ------------------------------------------------------------------- auditoria ---


def audit(tool: str, args: dict[str, Any], *, status: str, detail: str = "") -> None:
    """Registra a chamada no log append-only. Nunca falha por causa do log."""
    try:
        ensure_dirs()
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tool": tool,
            "status": status,  # ok | blocked | error
            "detail": detail[:500],
            "args": _redact(args),
        }
        with AUDIT_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


_SECRET_HINT = re.compile(r"(token|key|secret|password|passwd|senha|pwd)", re.IGNORECASE)


def _redact(args: dict[str, Any]) -> dict[str, Any]:
    """Mascara valores que parecem segredo antes de gravar no log."""
    out: dict[str, Any] = {}
    for k, v in (args or {}).items():
        if _SECRET_HINT.search(str(k)) and isinstance(v, str) and len(v) > 4:
            out[k] = v[:3] + "***"
        else:
            out[k] = v if not isinstance(v, str) or len(v) < 400 else v[:400] + "…"
    return out


__all__ = ["GuardError", "check_command", "check_path", "audit", "DENY_PATTERNS"]
