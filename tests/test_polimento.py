"""Testes do polimento: catálogo de modelos (ordem, cópia, marcação) + métricas.

O que este arquivo guarda, e por quê:

1. O BUG CENTRAL desta rodada — "trocar de modelo não funciona". O `listar()` não
   dizia qual modelo estava em uso, então a interface não tinha como destacar o
   ativo nem confirmar a troca: o usuário trocava, via "✅ trocado", e a tela
   continuava mostrando o modelo antigo. Agora a marcação é testada.

2. A ORDEM do catálogo é comportamento, não enfeite: `reservas()` percorre na
   ordem em que os modelos aparecem. Por isso mover precisa de teste.

3. `mover()` e `duplicar()` chamavam `write_config()`, que NÃO existe neste
   módulo (o nome certo é `update_config`). Só apareceu porque eu testei as duas
   de verdade — o `mover` "passava" quando o item já estava no fim, porque nesse
   caso ele retorna antes de gravar.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import nh.models as models  # noqa: E402
import nh.providers as providers  # noqa: E402
from nh.web import Handler  # noqa: E402

ok = 0
falhou = 0


def checar(cond, rotulo, detalhe=""):
    global ok, falhou
    if cond:
        print(f"✅ {rotulo}")
        ok += 1
    else:
        print(f"❌ {rotulo}" + (f"\n      {detalhe}" if detalhe else ""))
        falhou += 1


# ── cenário: catálogo limpo, dois modelos ──
originais = models.listar(incluir_sensiveis=True)
for m in originais:
    models.remover(m["id"])

try:
    print("── 1. o modelo ativo é marcado na lista (o bug da troca) ──")
    a = models.salvar({"apelido": "Teste A", "nivel": 3,
                       "url": "https://a.invalid/v1/chat/completions", "modelo": "aa"})
    b = models.salvar({"apelido": "Teste B", "nivel": 1,
                       "url": "https://b.invalid/v1/chat/completions", "modelo": "bb"})

    sem_ativo = models.listar()
    checar(all(x["ativo"] is False for x in sem_ativo),
           "sem modelo ativo: nenhum vem marcado", str([(x["apelido"], x["ativo"]) for x in sem_ativo]))

    models.definir_ativo(a["id"])
    marcados = {x["apelido"]: x["ativo"] for x in models.listar()}
    checar(marcados.get("Teste A") is True, "o ativo vem com ativo=True")
    checar(marcados.get("Teste B") is False, "os outros vêm com ativo=False")
    checar(all(x["em_uso"] == x["ativo"] for x in models.listar()),
           "`em_uso` acompanha `ativo` (a interface usa os dois nomes)")

    # e o `listar()` sem argumento descobre sozinho — quem chama não precisa saber
    checar(any(x["ativo"] for x in models.listar(id_ativo="")),
           "listar() sem id deduz o ativo do próprio catálogo")

    print("\n── 2. duplicar ──")
    r = models.duplicar(a["id"])
    checar(r.get("ok") is True, "duplicar devolve ok")
    checar(len(models.listar()) == 3, "o catálogo tem 3 depois da cópia")
    copia = [x for x in models.listar() if "cópia" in x["apelido"]]
    checar(len(copia) == 1, "a cópia existe e tem nome próprio")
    checar(copia and copia[0]["modelo"] == "aa", "a cópia herdou o modelo original")
    checar(copia and copia[0]["id"] != a["id"], "a cópia tem id diferente")
    checar(copia and copia[0]["ativo"] is False, "a cópia NÃO nasce ativa")
    models.remover(copia[0]["id"])

    print("\n── 3. mover muda a ORDEM (que é o comportamento das reservas) ──")
    antes = [x["apelido"] for x in models.listar()]
    checar(antes == ["Teste A", "Teste B"], "a ordem inicial é a de cadastro", str(antes))
    # posição é 1-based e reflete a ordem de tentativa das reservas
    checar([x["posicao"] for x in models.listar()] == [1, 2], "a posição acompanha a ordem")

    models.mover(b["id"], "subir")   # B sobe para primeiro
    depois = [x["apelido"] for x in models.listar()]
    checar(depois == ["Teste B", "Teste A"], "subir troca de lugar de verdade", str(depois))
    checar([x["posicao"] for x in models.listar()] == [1, 2],
           "as posições são recalculadas depois de mover")

    models.mover(b["id"], "descer")  # e volta
    checar([x["apelido"] for x in models.listar()] == antes, "descer desfaz a mudança")

    # a ordem mexida tem que valer para as RESERVAS, que é o motivo de existir
    models.mover(b["id"], "subir")
    reservas = [r.get("apelido") for r in models.reservas()]
    checar(reservas and reservas[0] == "Teste B",
           "a primeira reserva é o modelo que subiu", str(reservas))
    models.mover(b["id"], "descer")

    print("\n── 4. limites do mover ──")
    primeiro = models.listar()[0]["id"]
    msg = models.mover(primeiro, "subir")
    checar("fim da lista" in msg or "⚠️" in msg, "subir o primeiro avisa em vez de quebrar", msg)
    ultimo = models.listar()[-1]["id"]
    msg = models.mover(ultimo, "descer")
    checar("fim da lista" in msg or "⚠️" in msg, "descer o último avisa em vez de quebrar", msg)
    checar(models.mover("nao-existe", "subir").startswith("❌"),
           "id inexistente devolve erro tratado")
    checar(models.duplicar("nao-existe").get("ok") is False,
           "duplicar id inexistente devolve erro tratado")

    print("\n── 5. marcar ativo não bagunça a ordem ──")
    ordem_antes = [x["apelido"] for x in models.listar()]
    models.definir_ativo(b["id"])
    ordem_depois = [x["apelido"] for x in models.listar()]
    checar(ordem_depois == ordem_antes,
           "marcar ativo NÃO reordena o catálogo", f"{ordem_antes} -> {ordem_depois}")
    checar(models.ativo()["apelido"] == "Teste B", "o ativo é o B")
    checar([x["apelido"] for x in models.listar() if x["ativo"]] == ["Teste B"],
           "só um modelo vem marcado como ativo")

    print("\n── 6. aviso de chave: dá para saber antes de tentar usar ──")
    so_sem_chave = {"url": "https://x.invalid/v1/chat/completions", "chave": ""}
    checar(models.tem_chave(so_sem_chave) in (True, False),
           "tem_chave responde bool (nunca estoura)")

finally:
    for m in models.listar(incluir_sensiveis=True):
        models.remover(m["id"])
    for m in originais:      # devolve o catálogo como estava
        dados = {k: v for k, v in m.items()
                 if k not in ("nivel_nome", "nivel_emoji", "tem_chave", "tem_chave_propria",
                              "ativo", "em_uso", "chave_mascarada")}
        models.salvar(dados)

print("\n── 7. catálogo de provedores ──")
lista = providers.listar()
checar(len(lista) >= 30, f"pelo menos 30 provedores (tem {len(lista)})")
nuvem = [p for p in lista if p["tipo"] == "nuvem"]
local = [p for p in lista if p["tipo"] == "local"]
checar(len(nuvem) >= 25, f"pelo menos 25 na nuvem (tem {len(nuvem)})")
checar(len(local) >= 5, f"pelo menos 5 locais sem chave (tem {len(local)})")
checar(all(not p["precisa_chave"] for p in local), "todo provedor local dispensa chave")
checar(all(p["precisa_chave"] for p in nuvem), "todo provedor de nuvem pede chave")
# "Personalizado" fica de fora: ali o endpoint e a chave são escolha do usuário,
# então não existe página oficial para linkar
com_link = [p for p in nuvem if p["id"] != "custom"]
checar(all(p.get("key_url") for p in com_link),
       "todo provedor de nuvem (menos Personalizado) tem link para pegar a chave",
       str([p["id"] for p in com_link if not p.get("key_url")]))
# os que importam de verdade
for pid in ["openrouter", "groq", "deepseek", "gemini", "qwen", "github", "ollama", "lmstudio"]:
    checar(pid in providers.PROVIDERS, f"tem o provedor '{pid}'")

print("\n── 8. detectar provedor pelas URLs novas ──")
for url, esperado in [
    ("https://api.moonshot.ai/v1/chat/completions", "moonshot"),
    ("https://open.bigmodel.cn/api/paas/v4/chat/completions", "zhipu"),
    ("https://api.cohere.ai/compatibility/v1/chat/completions", "cohere"),
    ("https://models.github.ai/inference/chat/completions", "github"),
    ("http://localhost:8000/v1/chat/completions", "vllm"),
    ("http://localhost:1337/v1/chat/completions", "jan"),
]:
    checar(providers.detectar(url) == esperado,
           f"{esperado:9} <- {url.split('//')[1][:40]}",
           f"veio '{providers.detectar(url)}'")

print("\n── 9. métricas do sysinfo (o relatório é TEXTO, não dados) ──")
relatorio = (
    "🖥️  RELATÓRIO DO DISPOSITIVO\n"
    "plataforma : linux (Linux 6.17.0)\n"
    "máquina    : x86_64 · 2 núcleo(s)\n"
    "RAM        : 510.3MB usados de 842.8MB (61%)\n"
    "disco home : 11.6GB usados de 28.0GB (16.4GB livres)\n"
    "uptime     : 1452h09min\n"
)
m = Handler._metricas_do_sysinfo(relatorio)
checar(m.get("ram_pct") == 61, f"extrai a % da RAM ({m.get('ram_pct')})")
checar(m.get("ram_usado") == "510.3MB", f"extrai a RAM usada ({m.get('ram_usado')})")
checar(m.get("ram_total") == "842.8MB", f"extrai a RAM total ({m.get('ram_total')})")
checar(m.get("disco_pct") == 41, f"calcula a % do disco ({m.get('disco_pct')}) — 11.6 de 28.0")
checar(m.get("disco_livre") == "16.4GB", f"extrai o disco livre ({m.get('disco_livre')})")
checar(m.get("uptime") == "1452h09min", f"extrai o uptime ({m.get('uptime')})")
checar(Handler._metricas_do_sysinfo("") == {}, "texto vazio devolve {} em vez de estourar")
checar(Handler._metricas_do_sysinfo("lixo sem formato") == {},
       "texto fora do formato devolve {} em vez de estourar")

print()
if falhou:
    print(f"❌ {falhou} teste(s) falharam · {ok} passaram")
    raise SystemExit(1)
print(f"🎉 POLIMENTO VALIDADO — {ok} testes passando")
