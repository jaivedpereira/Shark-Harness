"""Plugin: meta — o harness falando de si mesmo."""


from __future__ import annotations

import json

from ..core import Registry
from ..guard import AUDIT_FILE

MANIFEST = {
    "id": "meta",
    "nome": "Auto-conhecimento",
    "versao": "1.0.0",
    "autor": "jaivedpereira",
    "categoria": "núcleo",
    "descricao": "Listar as ferramentas, ver os parâmetros de uma e ler o histórico de auditoria.",
    "risco_max": "safe",
    "plataformas": ["linux", "windows", "darwin", "android"],
    "requer": [],
    "tags": ["ferramentas", "auditoria"],
}


def list_tools(filtrar: str = "") -> str:
    """Lista as ferramentas do harness, com o nível de risco de cada uma.

    Args:
        filtrar: texto para filtrar pelo nome ou descrição (vazio = todas).
    """
    from ..core import load_plugins

    reg = load_plugins()
    icons = {"safe": "🟢", "write": "🟡", "exec": "🟠", "danger": "🔴"}
    tools = [reg.get(n) for n in reg.names()]
    if filtrar:
        f = filtrar.lower()
        tools = [t for t in tools if t and (f in t.name.lower() or f in t.description.lower())]
    if not tools:
        return f"nenhuma ferramenta bate com '{filtrar}'"

    by_plugin: dict[str, list] = {}
    for t in tools:
        by_plugin.setdefault(t.plugin or "core", []).append(t)

    out = [f"🧰 {len(tools)} ferramenta(s) disponíveis:"]
    for plugin in sorted(by_plugin):
        out.append(f"\n📦 {plugin}")
        for t in sorted(by_plugin[plugin], key=lambda x: x.name):
            out.append(f"  {icons.get(t.risk, '⚪')} {t.name} — {t.description}")
    out.append("\n🟢 só leitura · 🟡 escreve arquivo/tarefa · 🟠 executa comando · 🔴 apaga")
    return "\n".join(out)


def tool_help(nome: str) -> str:
    """Mostra a assinatura completa e os parâmetros de uma ferramenta específica.

    Args:
        nome: nome exato da ferramenta (ex.: 'run_shell').
    """
    from ..core import load_plugins

    reg = load_plugins()
    tool = reg.get(nome)
    if tool is None:
        return f"❌ '{nome}' não existe. Rode list_tools para ver as disponíveis."
    return (
        f"🔧 {tool.name}  [{tool.plugin} · risco {tool.risk}]\n"
        f"{tool.description}\n\n"
        f"schema:\n{json.dumps(tool.schema, ensure_ascii=False, indent=2)}"
    )


def audit_tail(linhas: int = 20) -> str:
    """Mostra as últimas ações que o harness executou (log de auditoria).

    Args:
        linhas: quantas entradas mostrar do fim do log.
    """
    if not AUDIT_FILE.exists():
        return "📭 log de auditoria vazio (nada executado ainda)."
    try:
        content = AUDIT_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:  # noqa: BLE001
        return f"ERRO lendo log: {exc}"
    tail = content[-max(1, int(linhas)):]
    out = [f"📜 últimas {len(tail)} de {len(content)} entrada(s) do log:"]
    for line in tail:
        try:
            rec = json.loads(line)
            out.append(f"  {rec.get('ts')} [{rec.get('status')}] {rec.get('tool')} — {str(rec.get('detail'))[:70]}")
        except Exception:
            out.append("  " + line[:100])
    return "\n".join(out)


def register(reg: Registry) -> None:
    reg.add(list_tools, risk="safe", plugin="meta")
    reg.add(tool_help, risk="safe", plugin="meta")
    reg.add(audit_tail, risk="safe", plugin="meta")
