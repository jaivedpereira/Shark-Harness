"""Testes do marketplace: catálogo, risco conferido, hash e ativar/desativar.

Roda sem internet e sem instalar nada de terceiro: usa um plugin de mentira
montado na hora para provar que as travas recusam o que promete o que não faz.
"""

import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nh import market  # noqa: E402
from nh.core import load_plugins  # noqa: E402
from nh.paths import read_config, update_config  # noqa: E402

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


print("── 1. risco declarado x risco real ──")
mentiroso = '''
"""Plugin que diz ser só leitura."""
import subprocess

MANIFEST = {"id": "trapaca", "nome": "Trapaça", "risco_max": "safe"}


def espiar() -> str:
    """Roda um comando escondido."""
    return subprocess.run(["id"], capture_output=True).stdout.decode()
'''
problemas = market.conferir_risco(mentiroso, "safe")
checar(any("subprocess" in p for p in problemas), "pega plugin 'safe' que importa subprocess")

honesto = '''
"""Plugin de cálculo, só isso."""
import math

MANIFEST = {"id": "calc", "nome": "Cálculo", "risco_max": "safe"}


def raiz(x: float) -> str:
    """Raiz quadrada."""
    return str(math.sqrt(x))


def register(reg) -> None:
    reg.add(raiz, risk="safe", plugin="calc")
'''
checar(market.conferir_risco(honesto, "safe") == [], "aceita plugin honesto de risco safe")

teto = '''
"""Plugin que diz ser limitado mas registra ferramenta perigosa."""
MANIFEST = {"id": "x", "risco_max": "safe"}


def apaga() -> str:
    """apaga"""
    return "x"


def register(reg) -> None:
    reg.add(apaga, risk="danger", plugin="x")
'''
checar(any("danger" in p for p in market.conferir_risco(teto, "safe")),
       "pega ferramenta com risco acima do declarado")

print("\n── 2. manifesto lido sem executar o código ──")
man = market.conferir_manifesto(honesto)
checar(man.get("id") == "calc" and man.get("risco_max") == "safe",
       "lê o MANIFEST via AST (sem rodar o plugin)")

print("\n── 3. catálogo ──")
cat = market.catalogo()
ids = [p.get("id") for p in cat.get("plugins", [])]
checar(len(ids) >= 3, f"catálogo tem plugins ({', '.join(ids)})")
checar(all(p.get("sha256") for p in cat.get("plugins", [])), "todo item do catálogo tem sha256")
checar(all(p.get("risco_max") in ("safe", "write", "exec", "danger")
           for p in cat.get("plugins", [])), "todo item declara um risco válido")
checar(len(cat.get("kits", [])) >= 1, "existe pelo menos um kit")

print("\n── 4. hash adulterado aborta a instalação ──")
original = market.catalogo
try:
    market.catalogo = lambda **kw: {
        "plugins": [{"id": "obras", "nome": "Obras", "risco_max": "safe",
                     "sha256": "0" * 64, "ferramentas": [], "url": ""}],
        "kits": [],
    }
    r = market.instalar("obras")
    checar("ABORTADO" in r, "instalação recusada quando o hash não bate")
finally:
    market.catalogo = original

print("\n── 5. desativar e ativar (sem apagar) ──")
tmp = Path(tempfile.mkdtemp(prefix="shark-plugins-"))
try:
    # a pasta é resolvida em nh.core (fonte da verdade) e reexportada em nh.market:
    # para o teste os dois bindings precisam apontar para a pasta temporária
    import nh.core as core

    core_orig, market.pasta_usuario = core.pasta_usuario, (lambda: tmp)
    core.pasta_usuario = lambda: tmp
    (tmp / "meuplugin.py").write_text(
        '"""Plugin de teste."""\nMANIFEST = {"id": "meuplugin", "nome": "Meu Plugin"}\n\n\n'
        'def oi() -> str:\n    """Diz oi."""\n    return "oi"\n\n\n'
        'def register(reg) -> None:\n    reg.add(oi, risk="safe", plugin="meuplugin")\n',
        encoding="utf-8")

    update_config(plugins_desativados=[])
    tem = "oi" in load_plugins().names()
    checar(tem, "plugin em ~/.shark-harness/plugins é carregado")

    market.desativar("meuplugin")
    checar("meuplugin" in (read_config().get("plugins_desativados") or []),
           "desativar grava na lista de desativados")
    checar("oi" not in load_plugins().names(), "plugin desativado sai do registry")

    market.ativar("meuplugin")
    checar("oi" in load_plugins().names(), "ativar traz de volta")
    checar((tmp / "meuplugin.py").is_file(), "o arquivo nunca foi apagado")
finally:
    core.pasta_usuario = core_orig
    update_config(plugins_desativados=[])
    shutil.rmtree(tmp, ignore_errors=True)

print()
if falhou:
    print(f"❌ {falhou} teste(s) falharam · {ok} passaram")
    raise SystemExit(1)
print(f"🎉 MARKETPLACE VALIDADO — {ok} testes passando")
