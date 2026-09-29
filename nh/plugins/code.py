"""Plugin: código — escreve e executa Python/Node direto, sem arquivo manual.

É o que faz o harness "capaz de programar": o agente manda o código, o harness
grava num temporário, roda e devolve a saída real. O código também passa pela
deny-list (um `os.system("rm -rf /")` é bloqueado igual).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ..core import Registry, workspace
from ..guard import check_command
from ..paths import has_cmd

MAX_OUT = 8000


def _run_code(lang: str, code: str, timeout: int) -> str:
    check_command(code)  # pega os.system/exec com comando destrutivo
    tmpdir = workspace() / ".tmp"
    tmpdir.mkdir(parents=True, exist_ok=True)
    suffix = {"python": ".py", "node": ".js"}[lang]
    fd = tempfile.NamedTemporaryFile(
        "w", suffix=suffix, dir=tmpdir, delete=False, encoding="utf-8"
    )
    with fd:
        fd.write(code)
    script = Path(fd.name)

    if lang == "python":
        exe = [sys.executable, str(script)]
    else:
        if not has_cmd("node"):
            return "❌ node não instalado (pule o teste ou instale Node.js)."
        exe = ["node", str(script)]

    started = time.time()
    try:
        proc = subprocess.run(
            exe, capture_output=True, text=True, timeout=max(1, min(int(timeout), 300))
        )
    except subprocess.TimeoutExpired:
        return f"⏱️ timeout de {timeout}s — código morto.\n{code[:300]}"
    finally:
        script.unlink(missing_ok=True)

    dur = round(time.time() - started, 2)
    parts = [f"▶️ {lang} ({dur}s, exit {proc.returncode})"]
    if proc.stdout.strip():
        parts.append(proc.stdout.rstrip())
    if proc.stderr.strip():
        parts.append("--- stderr ---\n" + proc.stderr.rstrip())
    if len(parts) == 1:
        parts.append("(sem saída — o código rodou sem imprimir nada)")
    out = "\n".join(parts)
    return out[:MAX_OUT] + (f"\n… truncado ({len(out)} chars)" if len(out) > MAX_OUT else "")


def run_python(code: str, timeout: int = 60) -> str:
    """Executa código Python e devolve a saída real (stdout + stderr).

    Use para calcular, testar uma ideia, processar dados, gerar arquivo.

    Args:
        code: código Python completo (com print() no que você quer ver).
        timeout: segundos antes de matar o processo.
    """
    return _run_code("python", code, timeout)


def run_node(code: str, timeout: int = 60) -> str:
    """Executa código JavaScript/Node e devolve a saída real.

    Args:
        code: código JS completo (use console.log para a saída).
        timeout: segundos antes de matar o processo.
    """
    return _run_code("node", code, timeout)


def check_syntax(caminho: str) -> str:
    """Confere se um arquivo Python tem sintaxe válida (sem executar).

    Args:
        caminho: caminho do .py a validar.
    """
    import ast

    p = Path(caminho).expanduser()
    if not p.is_absolute():
        p = workspace() / p
    if not p.exists():
        return f"❌ não existe: {p}"
    try:
        ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as exc:
        return f"❌ erro de sintaxe em {p}:{exc.lineno}: {exc.msg}"
    return f"✅ {p} — sintaxe OK"


def register(reg: Registry) -> None:
    reg.add(run_python, risk="exec", plugin="code")
    reg.add(run_node, risk="exec", plugin="code")
    reg.add(check_syntax, risk="safe", plugin="code")
