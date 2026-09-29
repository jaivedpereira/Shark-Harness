"""Testes das sessões (pasta de projeto) e da troca de workspace.

Usa pastas temporárias, então não mexe em nenhuma sessão de verdade nem no
workspace do harness.
"""

import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nh import sessions  # noqa: E402
from nh.core import definir_workspace, load_plugins, workspace  # noqa: E402

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


tmp = Path(tempfile.mkdtemp(prefix="shark-ses-"))
projeto = tmp / "meu-projeto"
projeto.mkdir()
(projeto / "README.md").write_text("# Meu Projeto\nUm projeto de teste com Flask.\n", encoding="utf-8")
(projeto / "app.py").write_text("print('oi')\n", encoding="utf-8")
(projeto / "pasta_interna").mkdir()
(projeto / "node_modules").mkdir()
(projeto / "node_modules" / "lixo.js").write_text("x", encoding="utf-8")

original = sessions.SESSOES_FILE
try:
    sessions.SESSOES_FILE = tmp / "sessions.json"

    print("── 1. criar e listar ──")
    s = sessions.criar("Meu Projeto", str(projeto))
    checar(s["id"] and s["nome"] == "Meu Projeto", "cria sessão com id e nome")
    checar(s["pasta"] == str(projeto.resolve()), "guarda o caminho absoluto da pasta")
    checar(len(sessions.listar()) == 1, "aparece na listagem")
    checar(sessions.listar()[0]["existe"] is True, "marca que a pasta existe")
    checar(sessions.listar()[0]["mensagens"] == 0, "conversa começa vazia")

    print("\n── 2. pasta inválida é recusada ──")
    try:
        sessions.criar("Ruim", str(tmp / "nao-existe"))
        checar(False, "deveria ter recusado pasta inexistente")
    except NotADirectoryError:
        checar(True, "recusa criar sessão com pasta inexistente")

    print("\n── 3. contexto do projeto (o que o agente vê) ──")
    ctx = sessions.contexto(str(projeto))
    checar("meu-projeto" in ctx, "diz em qual pasta está")
    checar("app.py" in ctx and "pasta_interna" in ctx, "lista os arquivos do projeto")
    checar("node_modules" not in ctx, "ignora pastas de ruído (node_modules)")
    checar("Flask" in ctx, "inclui o começo do README")

    print("\n── 4. árvore de arquivos ──")
    arv = sessions.arvore(str(projeto))
    checar("app.py" in arv and "pasta_interna" in arv, "mostra arquivos e subpastas")
    checar("node_modules" not in arv, "não mostra node_modules")

    print("\n── 5. histórico da conversa ──")
    historico = [
        {"role": "user", "content": "o que esse projeto faz?"},
        {"role": "assistant", "content": "É um projeto de teste com Flask."},
    ]
    sessions.guardar_historico(s["id"], historico)
    checar(len(sessions.obter(s["id"])["historico"]) == 2, "grava o histórico da sessão")
    checar(sessions.listar()[0]["mensagens"] == 2, "a listagem conta as mensagens")
    checar("Flask" in sessions.listar()[0]["ultima"], "mostra a última resposta")

    muitas = [{"role": "user", "content": f"m{i}"} for i in range(200)]
    sessions.guardar_historico(s["id"], muitas)
    checar(len(sessions.obter(s["id"])["historico"]) == sessions.MAX_MENSAGENS,
           f"corta o histórico em {sessions.MAX_MENSAGENS} mensagens (não cresce sem fim)")

    print("\n── 6. troca de workspace (o coração da sessão) ──")
    padrao = workspace()
    definir_workspace(str(projeto))
    checar(workspace() == projeto.resolve(), "workspace passa a ser a pasta da sessão")
    reg = load_plugins()
    saida = reg.dispatch("write_file", {"path": "novo.txt", "conteudo": "escrito na sessão"})
    checar((projeto / "novo.txt").is_file(), "write_file grava DENTRO da pasta do projeto")
    checar("novo.txt" in saida, "a resposta confirma o caminho")
    definir_workspace(None)
    checar(workspace() == padrao, "definir_workspace(None) volta ao padrão")

    print("\n── 7. encontrar sessão pela pasta ──")
    checar(sessions.por_pasta(str(projeto))["id"] == s["id"], "acha a sessão pela pasta")

    print("\n── 8. limpar, renomear e apagar ──")
    checar("limpa" in sessions.limpar_historico(s["id"]), "limpar zera a conversa")
    checar(len(sessions.obter(s["id"])["historico"]) == 0, "histórico ficou vazio")
    checar((projeto / "app.py").is_file(), "a pasta do projeto continua intacta")
    sessions.renomear(s["id"], "Projeto Renomeado")
    checar(sessions.obter(s["id"])["nome"] == "Projeto Renomeado", "renomeia a sessão")
    msg = sessions.apagar(s["id"])
    checar("apagada" in msg, "apaga a sessão")
    checar(sessions.obter(s["id"]) is None, "sessão não existe mais")
    checar((projeto / "app.py").is_file(), "apagar a sessão NÃO apaga a pasta")
    checar("não existe" in sessions.apagar("nao-existe"), "apagar id inexistente avisa")
finally:
    sessions.SESSOES_FILE = original
    definir_workspace(None)
    shutil.rmtree(tmp, ignore_errors=True)

print()
if falhou:
    print(f"❌ {falhou} teste(s) falharam · {ok} passaram")
    raise SystemExit(1)
print(f"🎉 SESSÕES VALIDADAS — {ok} testes passando")
