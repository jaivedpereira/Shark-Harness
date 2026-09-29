"""Move o bloco MANIFEST para DEPOIS dos imports.

`from __future__ import annotations` precisa ser a primeira instrução do arquivo,
então o MANIFEST não pode ficar entre o docstring e ele. Este script tira o bloco
de onde estiver e recoloca logo antes da primeira `def`/`class` de nível zero.

Idempotente: rodar de novo não muda nada se já estiver no lugar certo.
"""

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def extrair_bloco(texto: str) -> tuple[str, str]:
    """Devolve (texto sem o MANIFEST, bloco do MANIFEST)."""
    linhas = texto.splitlines(keepends=True)
    ini = None
    for i, linha in enumerate(linhas):
        if linha.startswith("MANIFEST = {"):
            ini = i
            break
    if ini is None:
        return texto, ""
    # acha o fechamento: primeira linha que é exatamente "}"
    fim = None
    for j in range(ini, len(linhas)):
        if linhas[j].rstrip("\n") == "}":
            fim = j
            break
    if fim is None:
        return texto, ""
    bloco = "".join(linhas[ini:fim + 1])
    restante = linhas[:ini] + linhas[fim + 1:]
    # remove a linha em branco extra que sobrou
    limpo: list[str] = []
    for k, linha in enumerate(restante):
        if linha.strip() == "" and k > 0 and restante[k - 1].strip() == "" and (
                k + 1 < len(restante) and restante[k + 1].strip() == ""):
            continue
        limpo.append(linha)
    return "".join(limpo), bloco


def posicionar(texto: str, bloco: str) -> str:
    """Insere o bloco antes da primeira def/class de nível zero."""
    linhas = texto.splitlines(keepends=True)
    alvo = len(linhas)
    for i, linha in enumerate(linhas):
        if linha.startswith(("def ", "class ", "async def ", "@")):
            alvo = i
            break
    antes = "".join(linhas[:alvo]).rstrip("\n")
    depois = "".join(linhas[alvo:])
    return f"{antes}\n\n{bloco.strip()}\n\n\n{depois}"


def main() -> int:
    alterados = 0
    for arq in sorted((RAIZ / "nh" / "plugins").glob("*.py")):
        texto = arq.read_text(encoding="utf-8")
        sem, bloco = extrair_bloco(texto)
        if not bloco:
            continue
        novo = posicionar(sem, bloco)
        if novo != texto:
            arq.write_text(novo, encoding="utf-8")
            alterados += 1

    # valida a sintaxe de todos
    import ast

    problemas = []
    for arq in sorted((RAIZ / "nh" / "plugins").glob("*.py")):
        try:
            ast.parse(arq.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            problemas.append(f"{arq.name}: {exc}")
    print(f"{alterados} arquivo(s) reposicionado(s)")
    if problemas:
        print("❌ ainda com erro:")
        for p in problemas:
            print("   " + p)
        return 1
    print("✅ sintaxe de todos os plugins OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
