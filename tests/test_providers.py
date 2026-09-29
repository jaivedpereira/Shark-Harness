"""Testes do catálogo de provedores e da descoberta de modelos.

Nada aqui chama a internet: o que fala com a rede é testado só nos casos de erro
óbvio (URL vazia, chave errada em host inexistente), e o resto é regra pura.

O bug que este arquivo guarda: o `detectar()` comparava pedaços da URL com
`url.split("/api")`, e como "https://api.groq.com/..." tem "/api" logo no começo,
o prefixo virava "https://" e **toda** URL era detectada como Groq.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import nh.providers as prov  # noqa: E402

ok = 0
falhou = 0


def checar(condicao: bool, rotulo: str, detalhe: str = "") -> None:
    global ok, falhou
    if condicao:
        print(f"✅ {rotulo}")
        ok += 1
    else:
        print(f"❌ {rotulo}" + (f"\n      {detalhe}" if detalhe else ""))
        falhou += 1


print("── 1. o catálogo tem os provedores que importam ──")
esperados = ["openrouter", "groq", "deepseek", "mistral", "gemini", "cerebras",
             "together", "fireworks", "xai", "openai", "anthropic", "ollama",
             "lmstudio", "llamacpp", "custom"]
faltando = [p for p in esperados if p not in prov.PROVIDERS]
checar(not faltando, f"tem pelo menos {len(esperados)} provedores", f"faltam: {faltando}")
checar(len(prov.PROVIDERS) >= 14, f"catálogo com {len(prov.PROVIDERS)} provedores no total")

print("\n── 2. todo provedor está bem formado ──")
for pid, p in prov.PROVIDERS.items():
    problemas = []
    if not p.get("label"):
        problemas.append("sem label")
    if p.get("url") and not p["url"].startswith(("http://", "https://")):
        problemas.append("url não começa com http")
    if pid != "custom" and not p.get("url"):
        problemas.append("sem url")
    if not p.get("hint"):
        problemas.append("sem dica")
    checar(not problemas, f"{pid} ok", ", ".join(problemas))

print("\n── 3. nuvem precisa de chave, local não ──")
for p in prov.listar():
    esperado = p["tipo"] != "local"
    checar(p["precisa_chave"] == esperado,
           f"{p['label']}: precisa_chave={p['precisa_chave']} (tipo {p['tipo']})")

print("\n── 4. detectar o provedor pela URL (o bug do v.split('/api')) ──")
casos = [
    ("https://api.groq.com/openai/v1/chat/completions", "groq"),
    ("https://api.deepseek.com/v1/chat/completions", "deepseek"),
    ("https://openrouter.ai/api/v1/chat/completions", "openrouter"),
    ("https://api.mistral.ai/v1/chat/completions", "mistral"),
    ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "gemini"),
    ("https://api.cerebras.ai/v1/chat/completions", "cerebras"),
    ("http://localhost:11434/v1/chat/completions", "ollama"),
    ("http://localhost:1234/v1/chat/completions", "lmstudio"),
    ("http://localhost:8080/v1/chat/completions", "llamacpp"),
    ("https://api.groq.com/qualquer/outro/caminho", "groq"),
    ("https://servidor-da-empresa.com/v1/chat/completions", "custom"),
    ("", "custom"),
    ("não é url", "custom"),
]
for url, esperado in casos:
    obtido = prov.detectar(url)
    checar(obtido == esperado, f"{esperado:10} <- {url or '(vazio)'}",
           f"veio '{obtido}'")

print("\n── 5. as três portas locais não se confundem ──")
checar(prov.detectar("http://localhost:11434/v1/chat/completions") == "ollama",
       "11434 = Ollama")
checar(prov.detectar("http://localhost:1234/v1/chat/completions") == "lmstudio",
       "1234 = LM Studio")
checar(prov.detectar("http://localhost:8080/v1/chat/completions") == "llamacpp",
       "8080 = llama.cpp")

print("\n── 6. deduzir a URL da lista de modelos ──")
for entrada, esperado in [
    ("https://openrouter.ai/api/v1/chat/completions", "https://openrouter.ai/api/v1/models"),
    ("http://localhost:11434/v1/chat/completions", "http://localhost:11434/v1/models"),
    ("https://api.groq.com/openai/v1/chat/completions", "https://api.groq.com/openai/v1/models"),
]:
    obtido = prov.url_modelos(entrada)
    checar(obtido == esperado, f"/models: {obtido}", f"esperado {esperado}")

print("\n── 7. erro claro em vez de traceback ──")
r = prov.listar_modelos("", "")
checar(r["ok"] is False and "endpoint" in r["erro"].lower(),
       "sem URL: pede o endpoint em vez de estourar")
r = prov.listar_modelos("https://host-que-nao-existe-xyz.invalid/v1/chat/completions", "k")
checar(r["ok"] is False and r.get("erro"), "host inexistente: devolve erro tratado")
checar("Traceback" not in str(r.get("erro")), "o erro não é um traceback")

print()
if falhou:
    print(f"❌ {falhou} teste(s) falharam · {ok} passaram")
    raise SystemExit(1)
print(f"🎉 PROVEDORES VALIDADOS — {ok} testes passando")
