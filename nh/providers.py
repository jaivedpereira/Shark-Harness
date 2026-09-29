"""Catálogo de provedores de LLM que o assistente aceita.

Todos falam a API OpenAI-compatível (`/chat/completions`), então o mesmo loop de
agente funciona em qualquer um — só muda a URL, o nome do modelo e a chave.

A interface usa isto para montar o seletor de provedor e preencher a URL sozinha
quando o usuário escolhe. `key_url` leva a pessoa direto para onde pegar a chave.
"""

from __future__ import annotations

PROVIDERS: dict[str, dict] = {
    "openrouter": {
        "label": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key_url": "https://openrouter.ai/keys",
        "hint": "Tem modelos ':free' (grátis). Precisa de chave.",
        "models": [
            "nvidia/nemotron-3.5-lightning:free",
            "qwen/qwen3.8-27b:free",
            "inclusionai/ling-3.0-flash-sante:free",
            "deepseek/deepseek-chat",
        ],
    },
    "groq": {
        "label": "Groq",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_url": "https://console.groq.com/keys",
        "hint": "Muito rápido e tem tier gratuito generoso.",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    },
    "deepseek": {
        "label": "DeepSeek",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "key_url": "https://platform.deepseek.com/api_keys",
        "hint": "Barato e bom em código. Requer saldo.",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "zen": {
        "label": "OpenCode Zen",
        "url": "https://opencode.ai/zen/v1/chat/completions",
        "key_url": "https://opencode.ai/auth",
        "hint": "Atenção: os modelos ':free' só funcionam dentro do próprio OpenCode.",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
    },
    "ollama": {
        "label": "Ollama (local, off-line)",
        "url": "http://localhost:11434/v1/chat/completions",
        "key_url": "https://ollama.com/download",
        "hint": "Grátis e 100% local — não precisa de chave. Instale o Ollama e rode `ollama pull llama3.2`.",
        "models": ["llama3.2", "qwen2.5-coder", "mistral"],
    },
    "custom": {
        "label": "Personalizado",
        "url": "",
        "key_url": "",
        "hint": "Qualquer endpoint OpenAI-compatível — informe a URL completa.",
        "models": [],
    },
}


def listar() -> list[dict]:
    """Lista para a interface (sem expor nada sensível — aqui não há segredo)."""
    return [
        {
            "id": pid,
            "label": p["label"],
            "url": p["url"],
            "key_url": p["key_url"],
            "hint": p["hint"],
            "models": p["models"],
            "precisa_chave": pid != "ollama",
        }
        for pid, p in PROVIDERS.items()
    ]


def achar(pid: str) -> dict | None:
    return PROVIDERS.get(pid)


def detectar(url: str) -> str:
    """Descobre qual provedor corresponde a uma URL salva."""
    if not url:
        return "custom"
    limpa = url.rstrip("/")
    for pid, p in PROVIDERS.items():
        if p["url"] and p["url"].rstrip("/") == limpa:
            return pid
    return "custom"


__all__ = ["PROVIDERS", "listar", "achar", "detectar"]
