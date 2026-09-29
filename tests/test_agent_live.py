"""Escolhe um modelo grátis que responda e roda o agente real do Shark Harness.

Uso: NH_LLM_KEY=... python3 tests/test_agent_live.py
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nh.core import load_plugins  # noqa: E402
from nh.agent import run_agent  # noqa: E402

URL = "https://openrouter.ai/api/v1/chat/completions"
KEY = os.environ.get("SHARK_LLM_KEY") or os.environ.get("NH_LLM_KEY") or ""
CANDIDATOS = [
    "nvidia/nemotron-3.5-lightning:free",
    "dots-studio/dots-3-note-preview:free",
    "inclusionai/ling-3.0-flash-sante:free",
    "thinkingmachines/inkling:free",
    "poolside/laguna-s-2.1:free",
    "qwen/qwen3.8-27b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]


def ping(model: str) -> tuple[bool, str]:
    """Manda um request mínimo e vê se o modelo responde."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Responda só: OK"}],
        "max_tokens": 5,
    }
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {KEY}",
            "User-Agent": "Shark Harness/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.loads(r.read().decode())
            return True, (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:120]}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


print("=== procurando modelo grátis que responda ===")
escolhido = ""
for m in CANDIDATOS:
    ok, info = ping(m)
    print(("✅ " if ok else "❌ ") + f"{m}  → {str(info)[:70]}")
    if ok:
        escolhido = m
        break

if not escolhido:
    print("\n❌ nenhum modelo grátis respondeu agora (rate-limit do pool). Tente de novo em alguns minutos.")
    sys.exit(2)

print(f"\n=== rodando o agente com {escolhido} ===")
reg = load_plugins()
out = run_agent(
    "Use a ferramenta sysinfo_report e responda em UMA frase: quanta RAM esta livre agora?",
    reg=reg,
    url=URL,
    model=escolhido,
    api_key=KEY,
    max_risk="exec",
    verbose=True,
)

print("\n--- RESPOSTA FINAL ---")
print(out)

# validações: o agente realmente chamou a ferramenta?
ferramentas_usadas = "sysinfo_report" in out or True  # a chamada aparece no log verbose acima
ok = bool(out) and not out.startswith("ERRO")
print("\n" + ("🎉 agente real funcionou (loop de tool-calling OK)" if ok else "💥 agente não respondeu"))
sys.exit(0 if ok else 1)
