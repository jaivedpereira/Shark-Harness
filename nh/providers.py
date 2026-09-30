"""Catálogo de provedores de LLM + descoberta dos modelos de cada um.

Todos aqui falam a API OpenAI-compatível (`/chat/completions`), então o mesmo loop
de agente funciona em qualquer um — só muda a URL, o nome do modelo e a chave.

Além da lista, este módulo sabe perguntar ao provedor **quais modelos ele tem**
(`listar_modelos`): em vez de você decorar nomes como
`meta-llama/llama-3.3-70b-instruct:free`, a interface busca a lista real e você
escolhe. Isso é o que mais reduz erro de digitação e modelo inexistente.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

USER_AGENT = "Mozilla/5.0 (compatible; SharkHarness/1.0)"

# tipo: "nuvem" precisa de internet e (quase sempre) chave · "local" roda na sua máquina
PROVIDERS: dict[str, dict] = {
    "openrouter": {
        "label": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key_url": "https://openrouter.ai/keys",
        "hint": "Centenas de modelos, vários ':free'. Ótimo para começar.",
        "tipo": "nuvem",
        "models": [
            "nvidia/nemotron-3.5-lightning:free",
            "qwen/qwen3.8-27b:free",
            "deepseek/deepseek-chat",
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o-mini",
        ],
    },
    "groq": {
        "label": "Groq",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_url": "https://console.groq.com/keys",
        "hint": "O mais RÁPIDO de todos (hardware próprio) e com plano grátis generoso.",
        "tipo": "nuvem",
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
            "qwen/qwen3-32b",
        ],
    },
    "deepseek": {
        "label": "DeepSeek",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "key_url": "https://platform.deepseek.com/api_keys",
        "hint": "Muito barato e forte em código. Requer saldo (poucos centavos).",
        "tipo": "nuvem",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "mistral": {
        "label": "Mistral AI",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "key_url": "https://console.mistral.ai/api-keys",
        "hint": "Francês, rápido e com tier gratuito para testes.",
        "tipo": "nuvem",
        "models": ["mistral-large-latest", "mistral-small-latest", "codestral-latest"],
    },
    "gemini": {
        "label": "Google Gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "key_url": "https://aistudio.google.com/apikey",
        "hint": "Endpoint OpenAI-compatível. Tem cota gratuita boa no AI Studio.",
        "tipo": "nuvem",
        "models": ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro"],
    },
    "cerebras": {
        "label": "Cerebras",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "key_url": "https://cloud.cerebras.ai/",
        "hint": "Velocidade absurda (inferência no wafer). Plano grátis para testar.",
        "tipo": "nuvem",
        "models": ["llama-3.3-70b", "llama3.1-8b", "qwen-3-32b"],
    },
    "together": {
        "label": "Together AI",
        "url": "https://api.together.xyz/v1/chat/completions",
        "key_url": "https://api.together.ai/settings/api-keys",
        "hint": "Muitos modelos abertos hospedados. Tem créditos iniciais.",
        "tipo": "nuvem",
        "models": [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "Qwen/Qwen2.5-Coder-32B-Instruct",
        ],
    },
    "fireworks": {
        "label": "Fireworks AI",
        "url": "https://api.fireworks.ai/inference/v1/chat/completions",
        "key_url": "https://fireworks.ai/account/api-keys",
        "hint": "Rápido para modelos abertos. Tem créditos de entrada.",
        "tipo": "nuvem",
        "models": [
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "accounts/fireworks/models/qwen2p5-coder-32b-instruct",
        ],
    },
    "xai": {
        "label": "xAI (Grok)",
        "url": "https://api.x.ai/v1/chat/completions",
        "key_url": "https://console.x.ai/",
        "hint": "Modelos Grok. Pago por uso.",
        "tipo": "nuvem",
        "models": ["grok-3-mini", "grok-3"],
    },
    "openai": {
        "label": "OpenAI",
        "url": "https://api.openai.com/v1/chat/completions",
        "key_url": "https://platform.openai.com/api-keys",
        "hint": "O oficial. Pago por uso (o mini é barato).",
        "tipo": "nuvem",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
    },
    "anthropic": {
        "label": "Anthropic (Claude)",
        "url": "https://api.anthropic.com/v1/chat/completions",
        "key_url": "https://console.anthropic.com/settings/keys",
        "hint": "Camada de compatibilidade OpenAI. Ótimo para código.",
        "tipo": "nuvem",
        "models": [
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
        ],
    },
    "opencode": {
        "label": "OpenCode Zen",
        "url": "https://opencode.ai/zen/v1/chat/completions",
        "key_url": "https://opencode.ai/auth",
        "hint": "Atenção: os modelos ':free' só funcionam dentro do próprio OpenCode.",
        "tipo": "nuvem",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
    },
    "ollama": {
        "label": "Ollama (local, off-line)",
        "url": "http://localhost:11434/v1/chat/completions",
        "key_url": "https://ollama.com/download",
        "hint": "Grátis e 100% local, sem chave. Instale o Ollama e rode `ollama pull llama3.2`.",
        "tipo": "local",
        "models": ["llama3.2", "qwen2.5-coder", "mistral", "gemma3"],
    },
    "lmstudio": {
        "label": "LM Studio (local, off-line)",
        "url": "http://localhost:1234/v1/chat/completions",
        "key_url": "https://lmstudio.ai/",
        "hint": "Interface gráfica para rodar modelos no PC. Ative o servidor local.",
        "tipo": "local",
        "models": [],
    },
    "llamacpp": {
        "label": "llama.cpp / llama-server (local)",
        "url": "http://localhost:8080/v1/chat/completions",
        "key_url": "https://github.com/ggml-org/llama.cpp",
        "hint": "Servidor do llama.cpp. Rode `llama-server -m modelo.gguf`.",
        "tipo": "local",
        "models": [],
    },
    # ── mais nuvens (todas falam a API OpenAI, então o mesmo loop serve) ──
    "cohere": {
        "label": "Cohere",
        "url": "https://api.cohere.ai/compatibility/v1/chat/completions",
        "key_url": "https://dashboard.cohere.com/api-keys",
        "hint": "Tier de teste grátis. Bom em texto e RAG.",
        "tipo": "nuvem",
        "models": ["command-r-plus-08-2024", "command-r-08-2024"],
    },
    "moonshot": {
        "label": "Moonshot (Kimi)",
        "url": "https://api.moonshot.ai/v1/chat/completions",
        "key_url": "https://platform.moonshot.ai/console/api-keys",
        "hint": "Kimi. Barato e com contexto gigante (ótimo para ler arquivo grande).",
        "tipo": "nuvem",
        "models": ["kimi-k2-0905-preview", "moonshot-v1-128k"],
    },
    "zhipu": {
        "label": "Zhipu (GLM)",
        "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "key_url": "https://open.bigmodel.cn/usercenter/apikeys",
        "hint": "GLM. Tem versão gratuita (glm-4-flash) para começar sem gastar.",
        "tipo": "nuvem",
        "models": ["glm-4-flash", "glm-4-plus", "glm-4-air"],
    },
    "qwen": {
        "label": "Alibaba Qwen (DashScope)",
        "url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        "key_url": "https://bailian.console.alibabacloud.com/?apiKey=1",
        "hint": "Qwen. Forte em código e multilíngue; tem cota gratuita generosa.",
        "tipo": "nuvem",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen2.5-coder-32b-instruct"],
    },
    "deepinfra": {
        "label": "DeepInfra",
        "url": "https://api.deepinfra.com/v1/openai/chat/completions",
        "key_url": "https://deepinfra.com/dash/api_keys",
        "hint": "Hospeda modelos abertos (Llama, Qwen, Mistral) com preço baixo.",
        "tipo": "nuvem",
        "models": ["meta-llama/Meta-Llama-3.1-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct"],
    },
    "perplexity": {
        "label": "Perplexity",
        "url": "https://api.perplexity.ai/chat/completions",
        "key_url": "https://www.perplexity.ai/settings/api",
        "hint": "Responde com busca na web embutida (bom para pergunta de atualidade).",
        "tipo": "nuvem",
        "models": ["sonar", "sonar-pro", "sonar-reasoning"],
    },
    "github": {
        "label": "GitHub Models",
        "url": "https://models.github.ai/inference/chat/completions",
        "key_url": "https://github.com/settings/tokens",
        "hint": "Grátis com um token do GitHub (basta um PAT clássico, sem escopo).",
        "tipo": "nuvem",
        "models": ["openai/gpt-4o", "meta/Llama-3.3-70B-Instruct", "mistral-ai/Mistral-Large-2411"],
    },
    "nebius": {
        "label": "Nebius AI Studio",
        "url": "https://api.studio.nebius.com/v1/chat/completions",
        "key_url": "https://studio.nebius.com/settings/api-keys",
        "hint": "Modelos abertos com crédito inicial grátis.",
        "tipo": "nuvem",
        "models": ["meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-Coder-32B-Instruct"],
    },
    "hyperbolic": {
        "label": "Hyperbolic",
        "url": "https://api.hyperbolic.xyz/v1/chat/completions",
        "key_url": "https://app.hyperbolic.xyz/settings",
        "hint": "Modelos abertos bem baratos com crédito de entrada.",
        "tipo": "nuvem",
        "models": ["meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct"],
    },
    "novita": {
        "label": "Novita AI",
        "url": "https://api.novita.ai/v3/openai/chat/completions",
        "key_url": "https://novita.ai/settings/key-management",
        "hint": "Muitos modelos abertos, com crédito grátis para testar.",
        "tipo": "nuvem",
        "models": ["deepseek/deepseek-v3", "meta-llama/llama-3.3-70b-instruct"],
    },
    "sambanova": {
        "label": "SambaNova",
        "url": "https://api.sambanova.ai/v1/chat/completions",
        "key_url": "https://cloud.sambanova.ai/apis",
        "hint": "Muito rápido em modelos abertos grandes; tier grátis para começar.",
        "tipo": "nuvem",
        "models": ["Meta-Llama-3.3-70B-Instruct", "DeepSeek-R1-Distill-Llama-70B"],
    },
    "chutes": {
        "label": "Chutes (Bittensor)",
        "url": "https://llm.chutes.ai/v1/chat/completions",
        "key_url": "https://chutes.ai/app/api",
        "hint": "Rede descentralizada. Vários modelos abertos sem cobrar por token.",
        "tipo": "nuvem",
        "models": ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen3-235B-A22B"],
    },
    "requesty": {
        "label": "Requesty (roteador)",
        "url": "https://router.requesty.ai/v1/chat/completions",
        "key_url": "https://app.requesty.ai/api-keys",
        "hint": "Um roteador que fala com vários provedores por uma chave só.",
        "tipo": "nuvem",
        "models": ["openai/gpt-4o-mini", "anthropic/claude-3-5-sonnet"],
    },
    "vercel": {
        "label": "Vercel AI Gateway",
        "url": "https://ai-gateway.vercel.sh/v1/chat/completions",
        "key_url": "https://vercel.com/dashboard/ai-gateway",
        "hint": "Roteador da Vercel — se você já usa Vercel, aproveita a mesma conta.",
        "tipo": "nuvem",
        "models": ["openai/gpt-4o-mini", "anthropic/claude-3-5-sonnet", "google/gemini-2.0-flash"],
    },
    # ── mais locais (não precisam de chave, e não gastam nada) ──
    "vllm": {
        "label": "vLLM (local)",
        "url": "http://localhost:8000/v1/chat/completions",
        "key_url": "https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html",
        "hint": "Servidor local de alta vazão (8000). Sem chave.",
        "tipo": "local",
        "models": [],
    },
    "jan": {
        "label": "Jan (local)",
        "url": "http://localhost:1337/v1/chat/completions",
        "key_url": "https://jan.ai",
        "hint": "App de desktop que sobe um servidor local na 1337. Sem chave.",
        "tipo": "local",
        "models": [],
    },
    "custom": {
        "label": "Personalizado",
        "url": "",
        "key_url": "",
        "hint": "Qualquer endpoint OpenAI-compatível — informe a URL completa.",
        "tipo": "nuvem",
        "models": [],
    },
}


def listar() -> list[dict]:
    """Lista para a interface (aqui não há nada sensível)."""
    return [
        {
            "id": pid,
            "label": p["label"],
            "url": p["url"],
            "key_url": p["key_url"],
            "hint": p["hint"],
            "models": p["models"],
            "tipo": p.get("tipo", "nuvem"),
            "precisa_chave": p.get("tipo", "nuvem") != "local",
        }
        for pid, p in PROVIDERS.items()
    ]


def achar(pid: str) -> dict | None:
    return PROVIDERS.get(pid)


def detectar(url: str) -> str:
    """Descobre qual provedor corresponde a uma URL.

    Casa pelo **host** (e, nos locais, também pela porta) em vez de comparar a URL
    inteira: assim uma URL com caminho ligeiramente diferente ainda é reconhecida,
    e `https://api.groq.com/qualquer/coisa` não vira "personalizado".

    Cuidado que já mordeu: comparar por pedaço de string (`url.split("/api")`) casa
    "https://" com todo mundo — por isso aqui é `urlparse` + hostname.
    """
    from urllib.parse import urlparse

    if not url:
        return "custom"
    alvo = urlparse(url)
    host = (alvo.hostname or "").lower()
    if not host:
        return "custom"

    # 1) host + porta exatos (é o que separa Ollama de LM Studio, os dois em localhost)
    for pid, p in PROVIDERS.items():
        if not p.get("url"):
            continue
        pu = urlparse(p["url"])
        if (pu.hostname or "").lower() == host and (pu.port or 0) == (alvo.port or 0):
            return pid
    # 2) só o host (endereços de nuvem, que não usam porta explícita)
    for pid, p in PROVIDERS.items():
        if not p.get("url"):
            continue
        pu = urlparse(p["url"])
        if (pu.hostname or "").lower() == host and not alvo.port:
            return pid
    return "custom"


def url_modelos(url_chat: str) -> str:
    """Deduz a URL da lista de modelos a partir da URL de chat.

    `.../v1/chat/completions` -> `.../v1/models`. É convenção da API OpenAI, e os
    provedores compatíveis seguem. Se a URL não terminar em /chat/completions,
    tenta trocar o último pedaço por 'models'.
    """
    u = (url_chat or "").rstrip("/")
    if u.endswith("/chat/completions"):
        return u[: -len("/chat/completions")] + "/models"
    if u.endswith("/completions"):
        return u[: -len("/completions")] + "/models"
    return u + "/models"


def listar_modelos(url_chat: str, chave: str = "", timeout: int = 20) -> dict:
    """Pergunta ao provedor quais modelos ele oferece (GET /v1/models).

    Devolve `{"ok": True, "modelos": [...]}` ou `{"ok": False, "erro": "..."}` com
    um motivo em português — porque "HTTP 401" sozinho não ajuda ninguém.
    """
    if not url_chat:
        return {"ok": False, "erro": "Informe o endpoint primeiro."}
    alvo = url_modelos(url_chat)

    cabecalhos = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if chave:
        cabecalhos["Authorization"] = f"Bearer {chave}"

    try:
        req = urllib.request.Request(alvo, headers=cabecalhos, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            dados = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        corpo = exc.read().decode("utf-8", "replace")[:200]
        if exc.code in (401, 403):
            motivo = "a chave foi recusada — confira se ela é desse provedor"
        elif exc.code == 404:
            motivo = ("esse provedor não expõe lista de modelos nesse endereço; "
                      "digite o nome do modelo na mão")
        elif exc.code == 429:
            motivo = "rate-limit ao pedir a lista — tente de novo em instantes"
        else:
            motivo = f"o provedor respondeu HTTP {exc.code}: {corpo}"
        return {"ok": False, "erro": motivo, "url": alvo}
    except urllib.error.URLError as exc:
        return {"ok": False, "erro": f"não consegui falar com {alvo} ({exc.reason})",
                "url": alvo}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "erro": f"{type(exc).__name__}: {exc}", "url": alvo}

    # formato OpenAI: {"data": [{"id": "..."}]} — alguns devolvem lista direta
    itens = dados.get("data") if isinstance(dados, dict) else dados
    if not isinstance(itens, list):
        return {"ok": False, "erro": "resposta em formato inesperado.", "url": alvo}

    modelos = []
    for it in itens:
        if isinstance(it, dict):
            nome = it.get("id") or it.get("name") or it.get("model")
            if nome:
                modelos.append({
                    "id": str(nome),
                    "preco": (it.get("pricing") or {}).get("prompt") if isinstance(it.get("pricing"), dict) else None,
                    "contexto": it.get("context_length") or it.get("context_window"),
                })
        elif isinstance(it, str):
            modelos.append({"id": it, "preco": None, "contexto": None})

    modelos.sort(key=lambda m: m["id"])
    return {"ok": True, "modelos": modelos, "url": alvo, "total": len(modelos),
            "gratis": [m["id"] for m in modelos if ":free" in m["id"]][:40]}


__all__ = ["PROVIDERS", "listar", "achar", "detectar", "url_modelos", "listar_modelos"]
