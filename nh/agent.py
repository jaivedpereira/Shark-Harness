"""Loop de agente — o LLM escolhe ferramentas e o harness executa.

Zero dependências externas: usa urllib da stdlib, então roda no Termux com
apenas Python. Qualquer endpoint OpenAI-compatível serve (DeepSeek, OpenCode/Zen,
Groq, OpenRouter, Ollama local...).

Config por env:
  NH_LLM_URL    default https://opencode.ai/zen/v1/chat/completions
  NH_LLM_KEY    token (se o endpoint exigir)
  NH_LLM_MODEL  default deepseek-v4-flash-free
  NH_MAX_RISK   risco máximo exposto ao modelo: safe|write|exec|danger (default exec)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .core import Registry, load_plugins
from .paths import env

# Default verificado funcionando de ponta a ponta (o tier grátis do zen exige
# rodar de dentro do OpenCode e os pagos pedem saldo — ver README).
DEFAULT_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning:free"

# Alguns provedores ficam atrás de Cloudflare e recusam o UA padrão do urllib
# ("Python-urllib/3.11") com `error code: 1010`. Um UA comum resolve.
USER_AGENT = "nano-harness/0.1 (+https://github.com)"

SYSTEM = """Você é o nano-harness: um agente que executa tarefas reais no dispositivo do usuário.

Regras:
- Use as ferramentas em vez de adivinhar. Nunca invente saída de comando.
- Antes de tarefa pesada, cheque o estado com sysinfo_report.
- Prefira passos pequenos e verifique o resultado de cada um.
- Quando terminar, responda em português, curto e direto, dizendo o que fez e o resultado real.
- Se uma ferramenta for bloqueada pela guarda, explique e proponha alternativa segura.
- Você tem permissão para criar, ler e modificar arquivos do usuário e rodar comandos
  não destrutivos. Não tente contornar a guarda de segurança.
"""


def _post(url: str, payload: dict, api_key: str = "", timeout: int = 180) -> dict:
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _tool_result_text(msg: dict) -> str:
    content = msg.get("content")
    if isinstance(content, str):
        return content
    return str(content)


def run_agent(
    user_text: str,
    *,
    reg: Registry | None = None,
    model: str = "",
    url: str = "",
    api_key: str = "",
    max_rounds: int = 8,
    max_risk: str = "",
    verbose: bool = True,
    history: list | None = None,
    on_step=None,
) -> str:
    """Roda o agente: manda o pedido ao LLM e executa as ferramentas que ele escolher.

    Devolve a resposta final em texto. `history` opcional mantém o contexto entre
    chamadas (lista de mensagens no formato OpenAI).

    `on_step(tipo, nome, detalhe)` é chamado a cada evento — usado pela interface
    web para mostrar os passos ao vivo. Tipos: 'chamada', 'resultado', 'resposta',
    'erro', 'info'.
    """
    reg = reg or load_plugins()
    url = url or env("LLM_URL", DEFAULT_URL)
    model = model or env("LLM_MODEL", DEFAULT_MODEL)
    api_key = api_key or env("LLM_KEY")
    max_risk = max_risk or env("MAX_RISK", "exec")

    tools = [t.as_openai() for t in reg.subset(max_risk=max_risk)]
    messages: list = history if history is not None else [{"role": "system", "content": SYSTEM}]
    messages.append({"role": "user", "content": user_text})

    def show(*parts: str) -> None:
        if verbose:
            print(*parts, flush=True)

    def step(tipo: str, nome: str = "", detalhe: str = "") -> None:
        if callable(on_step):
            try:
                on_step(tipo, nome, detalhe)
            except Exception:  # noqa: BLE001 — a UI nunca deve quebrar o agente
                pass

    show(f"🤖 modelo: {model} · {len(tools)} ferramentas expostas (risco ≤ {max_risk})")
    step("info", model, f"{len(tools)} ferramentas (risco ≤ {max_risk})")

    for rodada in range(1, max_rounds + 1):
        payload = {"model": model, "messages": messages, "tools": tools, "tool_choice": "auto"}
        try:
            resp = _post(url, payload, api_key)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:400]
            dica = ""
            if "1010" in body:
                dica = ("\n💡 1010 = Cloudflare bloqueou a requisição (UA/IP). "
                        "Tente rodar de outra rede ou de um endpoint local (Ollama).")
            elif exc.code in (401, 403):
                dica = "\n💡 confira NH_LLM_KEY (e se o modelo existe nesse provedor)."
            msg = f"ERRO HTTP {exc.code} no LLM: {body}{dica}"
            step("erro", "llm", msg)
            return msg
        except Exception as exc:  # noqa: BLE001
            msg = f"ERRO chamando o LLM ({url}): {type(exc).__name__}: {exc}"
            step("erro", "llm", msg)
            return msg

        choices = resp.get("choices") or []
        if not choices:
            return f"ERRO: resposta sem 'choices': {json.dumps(resp)[:300]}"
        msg = choices[0].get("message", {})
        calls = msg.get("tool_calls") or []

        if not calls:
            text = _tool_result_text(msg)
            messages.append({"role": "assistant", "content": text})
            show("✅ pronto")
            step("resposta", "", text)
            return text

        messages.append(msg)  # ecoa a decisão do modelo (inclui os tool_calls)
        for call in calls:
            fn = call.get("function") or {}
            name = fn.get("name", "")
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {}
            show(f"  🔧 [{rodada}] {name}({json.dumps(args, ensure_ascii=False)[:140]})")
            step("chamada", name, json.dumps(args, ensure_ascii=False))
            result = reg.dispatch(name, args if isinstance(args, dict) else {})
            show("     " + str(result).replace("\n", "\n     ")[:600])
            step("resultado", name, str(result))
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id", ""),
                "name": name,
                "content": str(result),
            })

    limite = "⚠️ limite de rodadas atingido sem resposta final — veja os passos acima."
    step("erro", "loop", limite)
    return limite


__all__ = ["run_agent", "SYSTEM"]
