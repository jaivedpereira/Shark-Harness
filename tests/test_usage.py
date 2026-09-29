"""Testes do registro de uso do modelo (tokens e custo estimado).

Usa um arquivo temporário para não sujar o histórico de verdade.
"""

import json
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import nh.usage as usage  # noqa: E402

ok = 0
falhou = 0


def checar(condicao: bool, rotulo: str) -> None:
    global ok, falhou
    if condicao:
        print(f"✅ {rotulo}")
        ok += 1
    else:
        print(f"❌ {rotulo}")
        falhou += 1


print("── 1. tabela de preço ──")
checar(usage.preco("nvidia/nemotron-3.5-lightning:free") == (0.0, 0.0), "modelo ':free' custa zero")
checar(usage.preco("openai/gpt-4o") == (2.50, 10.00), "gpt-4o tem preço na tabela")
checar(usage.preco("modelo/inexistente-xyz") is None, "modelo desconhecido não tem preço")
c = usage.estimar_custo("openai/gpt-4o", 1_000_000, 1_000_000)
checar(c is not None and abs(c - 12.50) < 1e-9, "custo de 1M+1M tokens no gpt-4o = US$ 12,50")

print("\n── 2. gravar e ler ──")
tmp = Path(tempfile.mkdtemp(prefix="shark-uso-")) / "usage.jsonl"
original = usage.USAGE_FILE
try:
    usage.USAGE_FILE = tmp
    usage.registrar("openai/gpt-4o", 1000, 500, rodadas=2, ferramentas=["concreto_volume"])
    usage.registrar("openai/gpt-4o", 2000, 700, rodadas=1, ferramentas=["peso_aco"])
    registros = usage.ler(30)
    checar(len(registros) == 2, "gravou as duas execuções")
    checar(registros[0]["total"] == 1500 and registros[1]["total"] == 2700, "soma entrada + saída em cada linha")

    usage.registrar("openai/gpt-4o", 0, 0)
    checar(len(usage.ler(30)) == 2, "execução sem consumo informado NÃO é gravada")

    print("\n── 3. resumo ──")
    r = usage.resumo(30)
    checar(r["total"]["execucoes"] == 2, "resumo conta 2 execuções")
    checar(r["total"]["total"] == 4200, "resumo soma 4200 tokens")
    checar(len(r["por_dia"]) == 14, "série do gráfico tem 14 dias")
    checar(r["hoje"]["execucoes"] == 2, "tudo caiu em 'hoje'")
    checar(r["modelos"][0]["modelo"] == "openai/gpt-4o", "agrupou por modelo")
    checar([f[0] for f in r["ferramentas"]] == ["concreto_volume", "peso_aco"] or
           set(f[0] for f in r["ferramentas"]) == {"concreto_volume", "peso_aco"},
           "lista as ferramentas usadas")
    custo_esperado = (3000 / 1e6) * 2.50 + (1200 / 1e6) * 10.00
    checar(abs(r["total"]["custo"] - custo_esperado) < 1e-9,
           f"custo total estimado = US$ {custo_esperado:.6f}")

    print("\n── 4. janela de tempo ──")
    antigo = {"ts": time.time() - 40 * 86400, "quando": "2000-01-01T00:00:00",
              "modelo": "openai/gpt-4o", "entrada": 999, "saida": 1, "total": 1000,
              "rodadas": 1, "ferramentas": [], "origem": ""}
    with tmp.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(antigo) + "\n")
    checar(len(usage.ler(7)) == 2, "registro de 40 dias atrás fica fora da janela de 7 dias")
    checar(len(usage.ler(365)) == 3, "mas aparece na janela de 365 dias")
    checar(usage.resumo(7)["total"]["execucoes"] == 2, "o resumo respeita a janela")

    print("\n── 5. limpar ──")
    msg = usage.limpar()
    checar("apagado" in msg, "limpar apaga o histórico")
    checar(usage.ler(365) == [], "histórico ficou vazio")
    checar("vazio" in usage.limpar(), "limpar de novo avisa que já está vazio")
finally:
    usage.USAGE_FILE = original
    import shutil

    shutil.rmtree(tmp.parent, ignore_errors=True)

print()
if falhou:
    print(f"❌ {falhou} teste(s) falharam · {ok} passaram")
    raise SystemExit(1)
print(f"🎉 USO DO MODELO VALIDADO — {ok} testes passando")
