"""Núcleo do Shark Harness — registro de ferramentas e carregamento de plugins.

O núcleo não sabe fazer nada sozinho. Ele só:
  1. descobre plugins em DUAS pastas (embutidos + instalados pelo usuário)
  2. deixa cada plugin registrar ferramentas (`register(reg)`)
  3. despacha chamadas (`reg.dispatch(nome, args)`) com auditoria

Todo o resto — shell, arquivos, agendador, dispositivo — é plugin.

Pastas de plugin (a ordem importa: o usuário pode sobrescrever um embutido):
  1. `nh/plugins/`                    embutidos, vêm no pacote (git pull atualiza)
  2. `~/.shark-harness/plugins/`      instalados pelo usuário — SOBREVIVEM ao git pull

Cada plugin pode declarar um `MANIFEST` (dict) no topo do módulo com id, nome,
versão, autor, categoria, risco máximo e dependências. É o que o marketplace lê.
Um plugin pode ser um arquivo `.py` solto ou uma PASTA com `__init__.py` (para
quando precisa de template, asset ou tradução junto).
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


def pasta_usuario():
    """Pasta onde ficam os plugins instalados pelo usuário (sobrevive ao git pull)."""
    from .paths import HOME

    return HOME / "plugins"


def _registrar(mod, reg: Registry) -> None:
    hook = getattr(mod, "register", None)
    if callable(hook):
        hook(reg)


def _plugin_do_usuario(caminho: Path):
    """Importa um plugin instalado a partir de um arquivo .py ou de uma pasta."""
    if caminho.is_dir():
        alvo = caminho / "__init__.py"
        if not alvo.is_file():
            return None
    else:
        alvo = caminho
    nome = f"shark_plugin_{caminho.stem}"
    if nome in __import__("sys").modules:  # já carregado (recarga a quente)
        return __import__("sys").modules[nome]
    try:
        spec = importlib.util.spec_from_file_location(nome, alvo)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        __import__("sys").modules[nome] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception as exc:  # noqa: BLE001 — plugin quebrado não derruba o harness
        print(f"⚠️  plugin '{caminho.name}' falhou ao carregar: {type(exc).__name__}: {exc}")
        return None


def _desativados() -> set[str]:
    from .paths import read_config

    return {str(x) for x in (read_config().get("plugins_desativados") or [])}


def load_plugins(reg: Registry | None = None, *, incluir_desativados: bool = False) -> Registry:
    """Carrega os plugins embutidos e os instalados pelo usuário.

    Plugins desativados (config.json → `plugins_desativados`) são pulados —
    é assim que o usuário escolhe o que carrega, sem apagar nada.
    """
    reg = reg or Registry()
    fora = set() if incluir_desativados else _desativados()

    # 1) embutidos (vêm no pacote)
    pkg = importlib.import_module(PLUGINS_PACKAGE)
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("_") or info.name in fora:
            continue
        _registrar(importlib.import_module(f"{PLUGINS_PACKAGE}.{info.name}"), reg)

    # 2) instalados pelo usuário (ficam fora do pacote, em ~/.shark-harness/plugins)
    pasta = pasta_usuario()
    if pasta.is_dir():
        for item in sorted(pasta.iterdir()):
            if item.name.startswith((".", "_")):
                continue
            if item.is_file() and item.suffix != ".py":
                continue
            if item.stem in fora:
                continue
            mod = _plugin_do_usuario(item)
            if mod is not None:
                _registrar(mod, reg)
    return reg


def manifesto(mod) -> dict:
    """Lê o MANIFEST do módulo do plugin (ou deduz um mínimo pelo nome)."""
    m = getattr(mod, "MANIFEST", None)
    if isinstance(m, dict):
        d = dict(m)
        d.setdefault("id", d.get("nome", "").lower() or getattr(mod, "__name__", "").split(".")[-1])
        return d
    return {}


def manifestos() -> list[dict]:
    """Todos os manifestos conhecidos: embutidos + instalados (inclui desativados)."""
    saida: list[dict] = []
    pkg = importlib.import_module(PLUGINS_PACKAGE)
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"{PLUGINS_PACKAGE}.{info.name}")
        except Exception:  # noqa: BLE001
            continue
        d = manifesto(mod)
        d.setdefault("id", info.name)
        d["origem"] = "embutido"
        saida.append(d)

    pasta = pasta_usuario()
    if pasta.is_dir():
        for item in sorted(pasta.iterdir()):
            if item.name.startswith((".", "_")):
                continue
            if item.is_file() and item.suffix != ".py":
                continue
            mod = _plugin_do_usuario(item)
            if mod is None:
                continue
            d = manifesto(mod)
            d.setdefault("id", item.stem)
            d["origem"] = "instalado"
            d["arquivo"] = str(item)
            saida.append(d)
    return saida


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
