"""Testes do catálogo de modelos e do teste de qualidade.

Nada aqui chama a internet: o classificador de resposta e a ordenação de reservas
são testados direto, e a chave usada é falsa.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import nh.models as models  # noqa: E402

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


print("── 1. classificação da resposta (o que reprova um modelo) ──")
casos = [
    ("43", ["43"], 12, True, "resposta certa e curta passa"),
    ("", ["43"], 12, False, "resposta vazia reprova"),
    ("Here's a thinking process:\n\n1. **Analyze User Input:**\n- The user asks "
     "for the sum of 17 and 26, so I need to add them together carefully and then "
     "report the final number to the user in Portuguese as requested.",
     ["43"], 12, False, "raciocínio vazando (textão) reprova"),
    ("Vinte e nove", ["43"], 12, False, "resposta errada reprova"),
    ("A cor do céu é azul.", ["azul"], 20, True, "certo com contexto curto passa"),
]
for texto, esperados, limite, esperado_ok, rotulo in casos:
    passou, motivo = models._classificar(texto, esperados, limite)
    checar(passou == esperado_ok, rotulo + (f" (motivo: {motivo})" if motivo else ""))
passou, motivo = models._classificar("Here's a thinking process: I need to add 17 and 26 now.",
                                     ["43"], 12)
checar(motivo == "raciocinio", "o motivo aponta 'vazou o raciocínio'")

print("\n── 2. níveis ──")
checar(models.nivel_info(1)["nome"] == "Rápido", "nível 1 = Rápido")
checar(models.nivel_info(3)["nome"] == "Potente", "nível 3 = Potente")
checar(models.nivel_info(99)["nome"] == "Equilibrado", "nível inválido cai no equilibrado")
checar(models.nivel_info("x")["nome"] == "Equilibrado", "nível não numérico cai no equilibrado")

print("\n── 3. máscara da chave ──")
checar(models.mascarar("sk-or-v1-abcdef123456") == "sk-or-…3456", "mascara mostrando pontas")
checar(models.mascarar("") == "", "chave vazia não vira máscara")
checar("abcdef123456" not in models.mascarar("sk-or-v1-abcdef123456"),
       "a máscara não contém a chave inteira")

tmp = Path(tempfile.mkdtemp(prefix="shark-modelos-"))
original = None
try:
    import nh.paths as paths

    original = paths.CONFIG_FILE
    paths.CONFIG_FILE = tmp / "config.json"
    paths._config_cache = None
    models.update_config = paths.update_config
    models.read_config = paths.read_config
    models.ler_env = lambda nome, default="": {
        "LLM_KEY": "", "LLM_URL": "", "LLM_MODEL": "",
    }.get(nome, default)

    print("\n── 4. salvar, listar e escolher ──")
    a = models.salvar({"apelido": "Rápido barato", "url": "https://a.example/v1/chat",
                       "modelo": "modelo-a", "nivel": 1})
    b = models.salvar({"apelido": "Potente caro", "url": "https://b.example/v1/chat",
                       "modelo": "modelo-b", "nivel": 3})
    checar(bool(a["id"]) and bool(b["id"]), "cria dois modelos com id")
    checar(len(models.listar()) == 2, "os dois aparecem na listagem")
    checar(models.listar()[0]["nivel"] == 1, "ordena do nível mais rápido para o mais potente")
    checar(models.listar()[0]["nivel_emoji"] == "⚡", "cada item traz o emoji do nível")
    checar(models.obter(a["id"])["apelido"] == "Rápido barato", "acha pelo id")

    print("\n── 5. validações ──")
    for faltando in ({"modelo": "x", "url": ""}, {"url": "https://x", "modelo": ""}):
        try:
            models.salvar(faltando)
            checar(False, f"deveria recusar {faltando}")
        except ValueError:
            checar(True, "recusa cadastro sem endpoint ou sem modelo")
    m = models.salvar({"apelido": "Nivel alto", "url": "https://c.example",
                       "modelo": "m", "nivel": 99})
    checar(m["nivel"] == 3, "nível fora da faixa é limitado a 3")

    print("\n── 6. chave por modelo ──")
    com_chave = models.salvar({"apelido": "Com chave", "url": "https://d.example",
                               "modelo": "m", "nivel": 2, "chave": "sk-bem-secreta-123456"})
    publico = models.listar()
    item = [x for x in publico if x["id"] == com_chave["id"]][0]
    checar(item["chave"] == "", "a listagem NÃO devolve a chave")
    checar(item["tem_chave_propria"] is True, "mas avisa que tem chave própria")
    checar("secreta" not in json.dumps(publico), "a chave não aparece em lugar nenhum do JSON")
    privado = [x for x in models.listar(incluir_sensiveis=True)
               if x["id"] == com_chave["id"]][0]
    checar(privado["chave"] == "sk-bem-secreta-123456", "internamente a chave é preservada")

    print("\n── 7. editar sem apagar a chave ──")
    models.salvar({"id": com_chave["id"], "apelido": "Com chave (editado)",
                   "url": "https://d.example", "modelo": "m2", "nivel": 2, "chave": ""})
    depois = [x for x in models.listar(incluir_sensiveis=True)
              if x["id"] == com_chave["id"]][0]
    checar(depois["chave"] == "sk-bem-secreta-123456",
           "salvar sem mandar chave NÃO apaga a que estava lá")
    checar(depois["modelo"] == "m2", "mas o resto foi atualizado")

    print("\n── 8. escolher o ativo ──")
    checar(models.ativo() is None, "sem escolha, não há ativo (usa o global)")
    msg = models.definir_ativo(b["id"])
    checar("✅" in msg, "define o modelo do chat")
    checar(models.ativo()["id"] == b["id"], "o ativo é o escolhido")
    checar("❌" in models.definir_ativo("nao-existe"), "recusa id inexistente")

    print("\n── 9. reservas ordenadas pelo nível ──")
    models.definir_ativo(b["id"])  # b é nível 3 (potente)
    fila = models.reservas()
    checar(len(fila) == 3, "os outros três entram como reserva")
    checar(b["id"] not in [f["id"] for f in fila], "o próprio ativo não é reserva dele mesmo")
    niveis = [f["nivel"] for f in fila]
    checar(niveis == sorted(niveis, reverse=True),
           f"os mais potentes vêm primeiro: {niveis}")
    checar(all(f["url"] and f["modelo"] for f in fila), "cada reserva tem endpoint e modelo")

    models.definir_ativo(a["id"])  # a é nível 1 (rápido)
    fila1 = models.reservas()
    # a regra é: primeiro o nível mais PRÓXIMO do ativo, depois os mais potentes.
    # como não existe outro nível 1, o nível 2 (equilibrado) é o vizinho mais perto.
    distancias = [abs(f["nivel"] - 1) for f in fila1]
    checar(distancias == sorted(distancias),
           f"com ativo rápido, o nível mais próximo vem primeiro: {distancias}")

    print("\n── 10. remover ──")
    models.definir_ativo(a["id"])
    checar("🗑️" in models.remover(a["id"]), "remove do catálogo")
    checar(models.obter(a["id"]) is None, "o removido sumiu")
    checar(models.ativo() is None, "remover o ativo volta a usar o global")
    checar("❌" in models.remover("nao-existe"), "remover id inexistente avisa")

    print("\n── 11. testar sem chave avisa em vez de tentar ──")
    r = models.testar(b["id"])
    checar(r.get("ok") is False and "chave" in (r.get("erro") or ""),
           "sem chave, o teste avisa em vez de dar erro confuso")
finally:
    import nh.paths as paths

    if original is not None:
        paths.CONFIG_FILE = original
        paths._config_cache = None
    shutil.rmtree(tmp, ignore_errors=True)

print()
if falhou:
    print(f"❌ {falhou} teste(s) falharam · {ok} passaram")
    raise SystemExit(1)
print(f"🎉 CATÁLOGO DE MODELOS VALIDADO — {ok} testes passando")
