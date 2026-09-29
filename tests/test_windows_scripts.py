"""Guarda os scripts de Windows contra o bug que quebrou o instalador.

O que aconteceu de verdade: o `install.ps1` tinha um travessão (`—`) dentro de uma
string. O Windows PowerShell 5.1 lê arquivos UTF-8 SEM BOM como ANSI, então o byte
0x94 (parte do travessão em UTF-8) virou uma aspa curva `”`, que ABRIU uma string e
engoliu a chave `}` — o parser morreu com "Token '}' inesperado" na linha 32.

Como não dá para rodar PowerShell no servidor Linux, este teste garante por análise:

  1. `.ps1` e `.bat` são 100% ASCII (a única exceção é o BOM do .ps1)
  2. `.ps1` tem BOM UTF-8 (para o 5.1 ler como UTF-8 se algum dia ganhar acento)
  3. chaves, parênteses e strings estão balanceados, ignorando comentários
  4. os `.bat` usam o caminho certo do Windows (Scripts, não bin)
  5. o README não manda comando de Linux para quem está no Windows
"""

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

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


def balancear(texto: str) -> list[str]:
    """Confere {} e () fora de comentário e de string (regras do PowerShell)."""
    pilha: list[tuple[str, int]] = []
    problemas: list[str] = []
    i = 0
    linha = 1
    while i < len(texto):
        c = texto[i]
        if c == "\n":
            linha += 1
        if c == "#":
            while i < len(texto) and texto[i] != "\n":
                i += 1
            continue
        if c == "'":
            i += 1
            while i < len(texto):
                if texto[i] == "\n":
                    linha += 1
                if texto[i] == "'":
                    if i + 1 < len(texto) and texto[i + 1] == "'":
                        i += 2
                        continue
                    break
                i += 1
        elif c == '"':
            i += 1
            while i < len(texto):
                if texto[i] == "\n":
                    linha += 1
                if texto[i] == "`":
                    i += 2
                    continue
                if texto[i] == '"':
                    break
                i += 1
        elif c in "{(":
            pilha.append((c, linha))
        elif c in "})":
            esperado = {"}": "{", ")": "("}[c]
            if not pilha:
                problemas.append(f"linha {linha}: '{c}' fecha sem ter aberto")
            elif pilha[-1][0] != esperado:
                problemas.append(
                    f"linha {linha}: '{c}' fecha '{pilha[-1][0]}' aberto na linha {pilha[-1][1]}")
                pilha.pop()
            else:
                pilha.pop()
        i += 1
    problemas += [f"linha {ln}: '{a}' nunca foi fechado" for a, ln in pilha]
    return problemas


ps1 = sorted(RAIZ.glob("*.ps1"))
bat = sorted(RAIZ.glob("*.bat"))

checar(bool(ps1), f"achei os instaladores .ps1 ({[p.name for p in ps1]})")
checar(bool(bat), f"achei os atalhos .bat ({[b.name for b in bat]})")

print("\n── 1. os .ps1 são ASCII e têm BOM ──")
for f in ps1:
    bruto = f.read_bytes()
    tem_bom = bruto.startswith(b"\xef\xbb\xbf")
    corpo = bruto[3:] if tem_bom else bruto
    especiais = sorted({b for b in corpo if b > 127})
    checar(tem_bom, f"{f.name}: tem BOM UTF-8 (o PowerShell 5.1 precisa)")
    checar(not especiais, f"{f.name}: 100% ASCII",
           f"bytes não-ASCII: {[hex(b) for b in especiais[:8]]} — emoji/acento/travessão "
           "quebram o parser do PowerShell 5.1")

print("\n── 2. chaves, parênteses e strings balanceados ──")
for f in ps1:
    problemas = balancear(f.read_text(encoding="utf-8-sig"))
    checar(not problemas, f"{f.name}: estrutura balanceada",
           "; ".join(problemas[:4]))

print("\n── 3. os .bat são ASCII ──")
for f in bat:
    especiais = sorted({b for b in f.read_bytes() if b > 127})
    checar(not especiais, f"{f.name}: 100% ASCII (o cmd.exe usa codepage antiga)",
           f"bytes não-ASCII: {[hex(b) for b in especiais[:8]]} — saem como lixo na tela")

print("\n── 4. os .bat usam o caminho certo do Windows ──")
for f in bat:
    t = f.read_text(encoding="ascii", errors="replace")
    if ".venv" in t:
        checar("Scripts" in t, f"{f.name}: usa .venv\\Scripts (Windows, não bin)")
        checar("/.venv/bin" not in t.replace("\\", "/"),
               f"{f.name}: não usa caminho de Linux (/.venv/bin)")

print("\n── 5. o .bat não chama comando de Linux ──")
linux_only = ("pkill", "chmod +x", "./run_web.sh", "./install.sh")
for f in bat:
    t = f.read_text(encoding="ascii", errors="replace")
    achados = [c for c in linux_only if c in t]
    checar(not achados, f"{f.name}: sem comando exclusivo de Linux", str(achados))

print("\n── 6. o README não mistura os caminhos ──")
readme = (RAIZ / "README.md").read_text(encoding="utf-8")
bloco_win = ""
if "### 🪟 Windows" in readme:
    bloco_win = readme.split("### 🪟 Windows", 1)[1].split("###", 1)[0]
checar("Scripts" in bloco_win or "run_web.bat" in bloco_win,
       "a seção de Windows mostra o caminho com Scripts / run_web.bat")
checar(".venv/bin" not in bloco_win,
       "a seção de Windows NÃO manda usar .venv/bin (é de Linux)")

print()
if falhou:
    print(f"❌ {falhou} teste(s) falharam · {ok} passaram")
    raise SystemExit(1)
print(f"🎉 SCRIPTS DE WINDOWS VALIDADOS — {ok} testes passando")
