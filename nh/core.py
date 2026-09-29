"""Núcleo do nano-harness — registro de ferramentas e carregamento de plugins.

O núcleo não sabe fazer nada sozinho. Ele só:
  1. descobre plugins em `nh/plugins/*.py`
  2. deixa cada plugin registrar ferramentas (`register(reg)`)
  3. despacha chamadas (`reg.dispatch(nome, args)`) com auditoria

Todo o resto — shell, arquivos, agendador, dispositivo — é plugin.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import guard

# Risco: define o que cada frente (CLI / MCP / agente) pode expor.
Risk = str  # "safe" | "write" | "exec" | "danger"

_PY_TO_JSON: dict[Any, dict[str, Any]] = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
}


@dataclass
class Tool:
    name: str
    fn: Callable[..., Any]
    schema: dict[str, Any]
    risk: Risk = "safe"
    plugin: str = ""
    description: str = ""

    def as_openai(self) -> dict[str, Any]:
        """Formato function-calling (OpenAI-compatível)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema,
            },
        }

    def as_mcp(self) -> dict[str, Any]:
        """Formato de listagem do MCP."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.schema,
        }


@dataclass
class Registry:
    tools: dict[str, Tool] = field(default_factory=dict)

    # ---------------------------------------------------------------- registro
    def add(
        self,
        fn: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        risk: Risk = "safe",
        plugin: str = "",
    ) -> Tool:
        tname = name or fn.__name__
        tool = Tool(
            name=tname,
            fn=fn,
            schema=build_schema(fn),
            risk=risk,
            plugin=plugin,
            description=(description or _first_para(fn.__doc__) or tname).strip(),
        )
        self.tools[tname] = tool
        return tool

    # ------------------------------------------------------------------ acesso
    def get(self, name: str) -> Tool | None:
        return self.tools.get(name)

    def names(self) -> list[str]:
        return sorted(self.tools)

    def subset(self, *, max_risk: Risk = "danger") -> list[Tool]:
        """Ferramentas até um nível de risco (usado para gatear o MCP)."""
        order = {"safe": 0, "write": 1, "exec": 2, "danger": 3}
        cap = order[max_risk]
        return [t for t in (self.tools[n] for n in self.names()) if order[t.risk] <= cap]

    # --------------------------------------------------------------- despacho
    def dispatch(self, name: str, args: dict[str, Any] | None = None) -> str:
        """Executa a ferramenta. Sempre devolve string (MCP e LLM esperam texto)."""
        args = args or {}
        tool = self.get(name)
        if tool is None:
            guard.audit(name, args, status="error", detail="ferramenta inexistente")
            return f"ERRO: ferramenta '{name}' não existe. Disponíveis: {', '.join(self.names())}"

        # valida argumentos contra o schema antes de chamar
        missing = [p for p in tool.schema.get("required", []) if p not in args]
        if missing:
            guard.audit(name, args, status="error", detail=f"faltando: {missing}")
            return f"ERRO: faltam argumentos obrigatórios: {', '.join(missing)}"

        unknown = [k for k in args if k not in tool.schema.get("properties", {})]
        if unknown:
            args = {k: v for k, v in args.items() if k not in unknown}

        try:
            out = tool.fn(**args)
            guard.audit(name, args, status="ok", detail=str(out)[:200])
            return out if isinstance(out, str) else _stringify(out)
        except guard.GuardError as exc:
            guard.audit(name, args, status="blocked", detail=str(exc))
            return f"🛑 {exc}"
        except TypeError as exc:
            guard.audit(name, args, status="error", detail=f"TypeError: {exc}")
            return f"ERRO de argumentos em '{name}': {exc}"
        except Exception as exc:  # noqa: BLE001 — o agente precisa ver o erro, não crashar
            guard.audit(name, args, status="error", detail=f"{type(exc).__name__}: {exc}")
            return f"ERRO em '{name}': {type(exc).__name__}: {exc}"


# ---------------------------------------------------------------- descoberta ---

PLUGINS_PACKAGE = "nh.plugins"


def load_plugins(reg: Registry | None = None) -> Registry:
    """Importa todo módulo em nh/plugins e chama register(reg) de cada um."""
    reg = reg or Registry()
    pkg = importlib.import_module(PLUGINS_PACKAGE)
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{PLUGINS_PACKAGE}.{info.name}")
        hook = getattr(mod, "register", None)
        if callable(hook):
            hook(reg)
    return reg


# ------------------------------------------------------------------ schema ---


def build_schema(fn: Callable[..., Any]) -> dict[str, Any]:
    """Deriva o JSON Schema da assinatura + docstring da função."""
    sig = inspect.signature(fn)
    hints = typing.get_type_hints(fn)
    props: dict[str, Any] = {}
    required: list[str] = []
    doc_params = _doc_params(fn.__doc__)

    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        spec = _json_type(hints.get(pname, str))
        if pname in doc_params:
            spec["description"] = doc_params[pname]
        props[pname] = spec
        if param.default is param.empty:
            required.append(pname)

    return {"type": "object", "properties": props, "required": required}


def _json_type(hint: Any) -> dict[str, Any]:
    if hint in _PY_TO_JSON:
        return dict(_PY_TO_JSON[hint])
    origin = typing.get_origin(hint)
    if origin in (list, tuple, set):
        args = typing.get_args(hint)
        inner = args[0] if args else str
        return {"type": "array", "items": _json_type(inner)}
    if origin is dict:
        return {"type": "object"}
    return {"type": "string"}  # fallback: aceita qualquer coisa como texto


def _doc_params(doc: str | None) -> dict[str, str]:
    """Lê a seção 'Args:' do docstring → {param: descrição}."""
    if not doc:
        return {}
    out: dict[str, str] = {}
    inside = False
    for raw in doc.splitlines():
        line = raw.strip()
        if line.lower().startswith(("args:", "argumentos:", "params:")):
            inside = True
            continue
        if inside:
            if not line:
                break
            if ":" in line:
                k, _, v = line.partition(":")
                out[k.strip().lstrip("*")] = v.strip()
    return out


def _first_para(doc: str | None) -> str:
    if not doc:
        return ""
    for block in doc.strip().split("\n\n"):
        b = " ".join(x.strip() for x in block.strip().splitlines())
        if b.lower().startswith(("args:", "argumentos:", "params:")):
            continue
        if b:
            return b
    return ""


def _stringify(out: Any) -> str:
    import json

    if isinstance(out, (dict, list)):
        return json.dumps(out, ensure_ascii=False, indent=2)
    return str(out)


def workspace() -> Path:
    from .paths import WORKSPACE, ensure_dirs

    ensure_dirs()
    return WORKSPACE


__all__ = ["Registry", "Tool", "load_plugins", "build_schema", "Risk", "workspace"]
