"""Servidor MCP (stdio) — expõe as ferramentas do harness para IAs.

O mesmo registry usado pela CLI e pelo agente vira um servidor MCP, então
Claude Code / Cursor / OpenCode enxergam as ferramentas e podem chamá-las.

Gate de risco: só entram ferramentas até `NH_MAX_RISK` (default 'exec').
Coloque NH_MAX_RISK=danger se quiser que a IA também possa apagar coisas.

O SDK do MCP é OPCIONAL: no Termux ele não instala (rpds-py precisa de Rust),
e nesse caso a CLI e o agente continuam funcionando normalmente.
"""

from __future__ import annotations

import functools
import os
import sys

from .core import Registry, load_plugins
from .guard import GuardError
from .paths import env

try:  # MCP SDK v2 (FastMCP foi renomeado para MCPServer)
    from mcp.server.mcpserver import MCPServer

    MCP_AVAILABLE = True
except Exception:  # noqa: BLE001
    MCPServer = None  # type: ignore[assignment]
    MCP_AVAILABLE = False


SERVER_NAME = "shark-harness"
INSTRUCTIONS = (
    "Ferramentas para programar, executar comandos, mexer em arquivos, controlar "
    "o dispositivo e agendar tarefas recorrentes. Prefira chamar as ferramentas a "
    "inventar resultado. Comandos destrutivos são bloqueados por uma guarda."
)


def _friendly(fn):
    """Converte exceção em texto de resultado.

    Sem isto, `run_shell("rm -rf /")` chega ao cliente como erro de PROTOCOLO
    ("Error executing tool run_shell") em vez de "🛑 BLOQUEADO pela guarda: ...".
    O modelo precisa da mensagem para explicar ao usuário e tentar outro caminho.
    Também evita que uma ferramenta quebrada derrube a sessão inteira.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except GuardError as exc:
            return f"🛑 {exc}"
        except TypeError as exc:
            return f"ERRO de argumentos em '{fn.__name__}': {exc}"
        except Exception as exc:  # noqa: BLE001
            return f"ERRO em '{fn.__name__}': {type(exc).__name__}: {exc}"

    return wrapper


def build_server(reg: Registry | None = None, max_risk: str = "") -> "MCPServer":
    """Monta o servidor MCP a partir do registry."""
    if not MCP_AVAILABLE:
        raise RuntimeError(
            "SDK do MCP não instalado. No PC: pip install 'mcp[cli]'.\n"
            "No Termux ele não instala (rpds-py/Rust) — use a CLI (`nh`) ou o agente."
        )

    reg = reg or load_plugins()
    max_risk = max_risk or env("MAX_RISK", "exec")

    mcp = MCPServer(
        name=SERVER_NAME,
        title="🦈 Shark Harness",
        description="Agente de tarefas: shell, arquivos, código, agendamento e controle do dispositivo.",
        instructions=INSTRUCTIONS,
        version="0.1.0",
    )

    expostas = reg.subset(max_risk=max_risk)
    for tool in expostas:
        # docstring + type hints viram o schema; _friendly mantém a assinatura
        mcp.tool(name=tool.name)(_friendly(tool.fn))

    return mcp


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    reg = load_plugins()

    if not MCP_AVAILABLE:
        print(
            "❌ SDK do MCP não encontrado.\n"
            "   No PC/servidor:  pip install 'mcp[cli]'\n"
            "   No Termux:       use a CLI (`nh --help`) ou `nh run \"...\"`\n\n"
            f"   As {len(reg.names())} ferramentas do harness funcionam sem o SDK."
        )
        return 1

    max_risk = env("MAX_RISK", "exec")
    mcp = build_server(reg, max_risk)
    expostas = reg.subset(max_risk=max_risk)

    if "--list" in argv:
        print(f"MCP '{SERVER_NAME}' — {len(expostas)} ferramenta(s), risco ≤ {max_risk}:")
        for t in expostas:
            print(f"  • {t.name} [{t.risk}] — {t.description}")
        return 0

    if "--selftest" in argv:
        return _selftest(mcp, expostas)

    print(f"🔌 MCP '{SERVER_NAME}' em stdio ({len(expostas)} ferramentas, risco ≤ {max_risk})", file=sys.stderr)
    mcp.run(transport="stdio")
    return 0


def _selftest(mcp, expostas) -> int:
    """Handshake + tools/list + tools/call por stdio num subprocesso de verdade.

    Não dá para testar com `printf | python -m nh serve`: o servidor vê EOF e
    morre antes de responder. Por isso abrimos o processo com stdin ABERTO e
    lemos as respostas linha a linha (JSON-RPC delimitado por newline).
    """
    import json
    import subprocess
    import threading
    import time

    proc = subprocess.Popen(
        [sys.executable, "-m", "nh", "serve"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    respostas: dict = {}
    lock = threading.Lock()

    def leitor() -> None:
        assert proc.stdout is not None
        for linha in proc.stdout:
            linha = linha.strip()
            if not linha:
                continue
            try:
                msg = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if "id" in msg:
                with lock:
                    respostas[msg["id"]] = msg

    threading.Thread(target=leitor, daemon=True).start()

    def rpc(method: str, params: dict | None = None, notify: bool = False, i: int = 0):
        if notify:
            msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        else:
            msg = {"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}}
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        if notify:
            return None
        fim = time.time() + 60
        while time.time() < fim:
            with lock:
                if i in respostas:
                    return respostas.pop(i)
            time.sleep(0.05)
        return None

    try:
        init = rpc(
            "initialize",
            {"protocolVersion": "2024-11-05", "capabilities": {},
             "clientInfo": {"name": "selftest", "version": "1.0"}},
            i=1,
        )
        info = (init or {}).get("result", {}).get("serverInfo")
        if not info:
            print(f"❌ handshake falhou: {json.dumps(init)[:200]}")
            return 1
        print(f"✅ handshake: {info.get('name')} v{info.get('version')}")

        rpc("notifications/initialized", {}, notify=True)

        listed = rpc("tools/list", {}, i=2) or {}
        tools = listed.get("result", {}).get("tools", [])
        names = [t["name"] for t in tools]
        print(f"✅ tools/list: {len(names)} ferramentas")
        faltando = [t.name for t in expostas if t.name not in names]
        if faltando:
            print("❌ não expostas: " + ", ".join(faltando))
            return 1
        print("✅ todas as ferramentas esperadas estão expostas")

        call = rpc("tools/call", {"name": "clock", "arguments": {}}, i=3) or {}
        conteudo = call.get("result", {}).get("content", [{}])
        texto = conteudo[0].get("text", "") if conteudo else ""
        print(f"✅ tools/call clock → {texto[:60]}")

        bloqueio = rpc("tools/call", {"name": "run_shell", "arguments": {"command": "rm -rf /"}}, i=4) or {}
        bc = bloqueio.get("result", {}).get("content", [{}])
        btexto = bc[0].get("text", "") if bc else ""
        if "BLOQUEADO" in btexto:
            print("✅ guarda ativa dentro do MCP (rm -rf / barrado)")
        else:
            print(f"❌ guarda não barrou dentro do MCP: {btexto[:80]}")
            return 1
        return 0
    finally:
        try:
            if proc.stdin:
                proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
