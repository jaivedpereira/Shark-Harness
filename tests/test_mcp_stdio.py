"""Teste do servidor MCP em stdio REAL (JSON-RPC por stdin/stdout).

Padrão obrigatório: abrir o processo com stdin ABERTO + thread leitora.
`printf ... | python server.py` NÃO funciona — o servidor vê EOF e morre antes
de responder.

Roda:  .venv/bin/python tests/test_mcp_stdio.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv" / "bin" / "python")
CMD = [PY, "-m", "nh", "serve"]

falhas: list[str] = []


def ok(cond: bool, label: str, extra: str = "") -> None:
    print(("✅ " if cond else "❌ ") + label + (f"  {extra}" if extra else ""))
    if not cond:
        falhas.append(label)


class McpClient:
    """Cliente MCP mínimo sobre stdio."""

    def __init__(self, cmd: list[str]) -> None:
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(ROOT),
        )
        self.responses: dict[int, dict] = {}
        self.lock = threading.Lock()
        self._id = 0
        self._alive = True
        self.reader = threading.Thread(target=self._read_loop, daemon=True)
        self.reader.start()

    def _read_loop(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in msg:
                with self.lock:
                    self.responses[msg["id"]] = msg
        self._alive = False

    def send(self, method: str, params: dict | None = None, *, notify: bool = False) -> int:
        self._id += 1
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notify:
            msg["id"] = self._id
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        return self._id

    def wait(self, msg_id: int, timeout: float = 90.0) -> dict | None:
        limite = time.time() + timeout
        while time.time() < limite:
            with self.lock:
                if msg_id in self.responses:
                    return self.responses.pop(msg_id)
            time.sleep(0.05)
        return None

    def call(self, method: str, params: dict | None = None, timeout: float = 90.0) -> dict | None:
        return self.wait(self.send(method, params), timeout)

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def payload(resp: dict | None) -> str:
    if not resp:
        return ""
    if "error" in resp:
        return f"ERROR: {resp['error']}"
    result = resp.get("result", {})
    content = result.get("content")
    if isinstance(content, list) and content:
        return content[0].get("text", "")
    return json.dumps(result)


def main() -> int:
    print("=== servidor MCP: shark-harness ===")
    ok(Path(PY).exists(), f"venv encontrado ({PY})")
    cli = McpClient(CMD)

    # 1) handshake
    init = cli.call("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "teste-nh", "version": "1.0"},
    }, timeout=60)
    info = (init or {}).get("result", {}).get("serverInfo", {})
    ok(bool(info), "handshake initialize respondeu", f"{info.get('name')} v{info.get('version')}")
    ok(info.get("name") == "shark-harness", f"nome do servidor = {info.get('name')}")

    cli.send("notifications/initialized", {}, notify=True)

    # 2) tools/list
    listed = cli.call("tools/list", {})
    tools = (listed or {}).get("result", {}).get("tools", [])
    names = [t["name"] for t in tools]
    print(f"\n=== tools/list: {len(names)} ferramentas ===")
    ok(len(tools) >= 20, f"{len(tools)} ferramentas expostas")
    esperadas = ["run_shell", "run_python", "write_file", "read_file", "schedule_task",
                 "list_tasks", "device_notify", "sysinfo_report", "clock", "list_tools"]
    faltando = [e for e in esperadas if e not in names]
    ok(not faltando, "todas as ferramentas-chave presentes", f"faltando: {faltando}" if faltando else "")
    ok("delete_path" not in names, "ferramenta 'danger' (delete_path) NÃO exposta com risco ≤ exec")
    com_schema = [t for t in tools if t.get("inputSchema", {}).get("properties")]
    ok(len(com_schema) >= 15, f"{len(com_schema)} ferramentas com inputSchema preenchido")
    desc_ok = all(t.get("description") for t in tools)
    ok(desc_ok, "todas as ferramentas têm descrição (a IA precisa disso)")

    # 3) tools/call — ferramentas reais
    print("\n=== tools/call (resultados reais) ===")
    casos = [
        ("clock", {}, "🕐"),
        ("sysinfo_report", {}, "RAM"),
        ("list_tools", {}, "ferramenta"),
        ("which", {"programa": "python3"}, "python3"),
        ("run_shell", {"command": "echo mcp-shell-ok"}, "mcp-shell-ok"),
        ("run_python", {"code": "print(6*7)"}, "42"),
        ("write_file", {"path": "mcp_teste.txt", "conteudo": "escrito via MCP\n"}, "gravado"),
        ("read_file", {"path": "mcp_teste.txt"}, "escrito via MCP"),
        ("schedule_task", {"nome": "job-mcp", "cron": "*/30 * * * *", "comando": "echo agendado"}, "agendada"),
        ("list_tasks", {}, "job-mcp"),
        ("explain_cron", {"expressao": "0 7 * * 1-5"}, "seg"),
        ("run_shell", {"command": "rm -rf /"}, "BLOQUEADO"),
    ]
    for name, args, esperado in casos:
        resp = cli.call("tools/call", {"name": name, "arguments": args}, timeout=90)
        texto = payload(resp)
        ok(esperado.lower() in texto.lower(), f"{name} → contém '{esperado}'", texto.replace("\n", " ")[:80])

    # 4) erro: ferramenta inexistente
    resp = cli.call("tools/call", {"name": "ferramenta_fantasma", "arguments": {}})
    erro_ou_texto = payload(resp)
    ok(bool(resp), "ferramenta inexistente não derruba o servidor",
       ("protocol error OK" if "error" in (resp or {}) else erro_ou_texto[:60]))

    # 5) limpeza do job de teste
    lista = payload(cli.call("tools/call", {"name": "list_tasks", "arguments": {}}))
    if "job-mcp" in lista:
        payload(cli.call("tools/call", {"name": "remove_task", "arguments": {"id_ou_nome": "job-mcp"}}))
    depois = payload(cli.call("tools/call", {"name": "list_tasks", "arguments": {}}))
    ok("job-mcp" not in depois, "job de teste removido")

    cli.close()

    print("\n" + ("🎉 MCP VALIDADO — handshake, tools/list e tools/call funcionando"
                  if not falhas else f"💥 {len(falhas)} FALHA(S): {falhas}"))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
