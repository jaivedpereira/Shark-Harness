"""Marketplace de plugins — catálogo, instalação verificada e ativar/desativar.

Como funciona:

  1. O catálogo é um `index.json` (embutido no pacote e sobrescrito pelo do
     repositório, quando há internet). Cada item traz id, versão, categoria,
     risco máximo declarado e o **sha256** do código.
  2. Instalar = baixar o `.py`, **conferir o sha256** contra o catálogo, conferir
     que o risco declarado é verdade (ver `conferir_risco`) e gravar em
     `~/.shark-harness/plugins/` — pasta FORA do pacote, que o `git pull` não apaga.
  3. Ativar/desativar só mexe numa lista no `config.json`: nada é apagado.

Sobre segurança, sem enfeite: plugin de terceiro roda com o mesmo poder que você —
não existe sandbox real dentro do mesmo processo. As travas aqui são: catálogo
curado, hash fixado, risco declarado conferido no código-fonte (AST) e confirmação
explícita para plugin que executa comando. Leia o código antes de instalar.
"""

from __future__ import annotations

import ast
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

from .core import manifesto, pasta_usuario
from .paths import read_config, update_config

RAIZ_REPO = "https://raw.githubusercontent.com/jaivedpereira/Shark-Harness/main"
INDEX_REMOTO = f"{RAIZ_REPO}/marketplace/index.json"
INDEX_LOCAL = Path(__file__).with_name("market_index.json")
UA = "shark-harness/0.1 (+https://github.com/jaivedpereira/Shark-Harness)"

# O que um plugin declara como risco máximo e o que ele REALMENTE faz no código
_IMPORTS_PROIBIDOS_SAFE = {"subprocess", "shutil", "ctypes", "socket", "multiprocessing"}
_CHAMADAS_PROIBIDAS_SAFE = {"system", "popen", "exec", "execv", "eval", "compile", "__import__", "open"}


# ------------------------------------------------------------------ catálogo ---
def _get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def catalogo(*, forcar: bool = False) -> dict:
    """Catálogo de plugins e kits. Tenta o do repositório; cai no embutido."""
    if forcar:
        try:
            return json.loads(_get(INDEX_REMOTO).decode("utf-8"))
        except Exception:  # noqa: BLE001 — sem internet usa o embutido
            pass
    if INDEX_LOCAL.is_file():
        try:
            return json.loads(INDEX_LOCAL.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {"plugins": [], "kits": []}
    try:
        return json.loads(_get(INDEX_REMOTO).decode("utf-8"))
    except Exception:  # noqa: BLE001
        return {"plugins": [], "kits": []}


def _item(pid: str) -> dict | None:
    for p in catalogo().get("plugins", []):
        if p.get("id") == pid:
            return p
    return None


def _fonte_local(pid: str) -> Path | None:
    """Cópia do plugin dentro do repositório (permite instalar sem internet)."""
    for cand in (
        Path(__file__).resolve().parent.parent / "marketplace" / "plugins" / f"{pid}.py",
        Path(__file__).resolve().parent.parent / "marketplace" / "plugins" / pid / "__init__.py",
    ):
        if cand.is_file():
            return cand
    return None


def _baixar_fonte(item: dict) -> str:
    """Pega o código do plugin: do repositório ou da cópia local."""
    pid = item["id"]
    erros = []
    if item.get("url"):
        try:
            return _get(item["url"]).decode("utf-8")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            erros.append(str(exc))
    local = _fonte_local(pid)
    if local:
        return local.read_text(encoding="utf-8")
    raise RuntimeError("não consegui baixar o plugin e não há cópia local. " + " / ".join(erros))


# ------------------------------------------------------------------- risco ---
def conferir_risco(codigo: str, declarado: str) -> list[str]:
    """Confere se o RISCO DECLARADO bate com o que o código faz de verdade.

    Devolve a lista de problemas; vazia = coerente. É o que impede um plugin de
    dizer "sou só leitura" e importar `subprocess`.
    """
    problemas: list[str] = []
    try:
        arvore = ast.parse(codigo)
    except SyntaxError as exc:
        return [f"código com erro de sintaxe: {exc}"]

    imports: set[str] = set()
    chamadas: set[str] = set()
    riscos_registrados: set[str] = set()

    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            imports.update(a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            imports.add(no.module.split(".")[0])
        elif isinstance(no, ast.Call):
            f = no.func
            nome = ""
            if isinstance(f, ast.Attribute):
                nome = f.attr
            elif isinstance(f, ast.Name):
                nome = f.id
            if nome:
                chamadas.add(nome)
            # reg.add(fn, risk="exec") — lê o risco real declarado nas ferramentas
            if nome == "add":
                for kw in no.keywords:
                    if kw.arg == "risk" and isinstance(kw.value, ast.Constant):
                        riscos_registrados.add(str(kw.value.value))

    ordem = {"safe": 0, "write": 1, "exec": 2, "danger": 3}
    if declarado in ("safe", "write"):
        ruins = sorted(imports & _IMPORTS_PROIBIDOS_SAFE)
        if ruins:
            problemas.append(f"declarou risco '{declarado}' mas importa: {', '.join(ruins)}")
        usadas = sorted((chamadas & _CHAMADAS_PROIBIDAS_SAFE))
        if usadas:
            problemas.append(f"declarou risco '{declarado}' mas chama: {', '.join(usadas)}()")
    if declarado != "danger" and "danger" in riscos_registrados:
        problemas.append("declarou risco máximo acima de 'danger' que a própria ferramenta usa")
    if declarado in ordem and riscos_registrados:
        teto = ordem[declarado]
        fora = sorted(r for r in riscos_registrados if ordem.get(r, 0) > teto)
        if fora:
            problemas.append(f"registra ferramenta com risco {', '.join(fora)} acima do declarado '{declarado}'")
    if "shutil" in imports and "rmtree" in chamadas and declarado != "danger":
        problemas.append("usa shutil.rmtree() e não declarou risco 'danger'")
    return problemas


def conferir_manifesto(codigo: str) -> dict:
    """Extrai o MANIFEST do código sem executá-lo (procura o literal no AST)."""
    try:
        arvore = ast.parse(codigo)
    except SyntaxError:
        return {}
    for no in arvore.body:
        if isinstance(no, ast.Assign):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name) and alvo.id == "MANIFEST":
                    try:
                        return ast.literal_eval(no.value)
                    except Exception:  # noqa: BLE001
                        return {}
    return {}


# -------------------------------------------------------------- instalados ---
def instalados() -> list[dict]:
    """Plugins instalados pelo usuário (com manifesto, risco e ferramentas)."""
    from .core import load_plugins

    reg = load_plugins(incluir_desativados=True)
    fora = set(str(x) for x in (read_config().get("plugins_desativados") or []))
    por_plugin: dict[str, list[str]] = {}
    for t in reg.tools.values():
        por_plugin.setdefault(t.plugin or "", []).append(t.name)

    saida = []
    for m in _manifestos_usuario():
        pid = m.get("id", "")
        m = dict(m)
        m["ferramentas"] = sorted(por_plugin.get(pid, []))
        m["ativo"] = pid not in fora
        saida.append(m)
    return saida


def _manifestos_usuario() -> list[dict]:
    """Manifestos dos plugins em ~/.shark-harness/plugins (sem carregar o resto)."""
    from .core import _plugin_do_usuario

    pasta = pasta_usuario()
    if not pasta.is_dir():
        return []
    saida = []
    for item in sorted(pasta.iterdir()):
        if item.name.startswith((".", "_")) or (item.is_file() and item.suffix != ".py"):
            continue
        mod = _plugin_do_usuario(item)
        if mod is None:
            saida.append({"id": item.stem, "nome": item.stem, "quebrado": True})
            continue
        d = manifesto(mod)
        d.setdefault("id", item.stem)
        d["arquivo"] = str(item)
        saida.append(d)
    return saida


def disponiveis() -> list[dict]:
    """Itens do catálogo que ainda NÃO estão instalados."""
    tenho = {m.get("id") for m in _manifestos_usuario()}
    return [p for p in catalogo().get("plugins", []) if p.get("id") not in tenho]


# ------------------------------------------------------------------- ações ---
def instalar(pid: str, *, confirmar_exec: bool = False) -> str:
    """Instala um plugin do catálogo (confere hash e risco antes de gravar).

    Args:
        pid: id do plugin no catálogo (ex.: obras, git).
        confirmar_exec: precisa ser True para plugin que executa comando (risco exec/danger).
    """
    item = _item(pid)
    if item is None:
        return f"❌ '{pid}' não está no catálogo. Veja o que existe com: nh plugin procurar"
    if _fonte_local(pid) is None and not item.get("url"):
        return f"❌ '{pid}' não tem fonte de download no catálogo."

    try:
        codigo = _baixar_fonte(item)
    except Exception as exc:  # noqa: BLE001
        return f"❌ não consegui baixar '{pid}': {exc}"

    esperado = str(item.get("sha256") or "")
    obtido = hashlib.sha256(codigo.encode("utf-8")).hexdigest()
    if esperado and obtido != esperado:
        return (f"🛑 ABORTADO: o código de '{pid}' não bate com o hash do catálogo.\n"
                f"   esperado: {esperado[:16]}…\n   recebido: {obtido[:16]}…\n"
                f"   ou o catálogo está velho, ou alguém trocou o arquivo. Nada foi instalado.")

    problemas = conferir_risco(codigo, str(item.get("risco_max", "safe")))
    if problemas:
        return ("🛑 ABORTADO: o plugin declara um risco que o código não cumpre:\n  - "
                + "\n  - ".join(problemas))

    man = conferir_manifesto(codigo)
    declared = str(item.get("risco_max", "safe"))
    if declared in ("exec", "danger") and not confirmar_exec:
        return (f"⚠️ '{pid}' executa comandos no seu dispositivo (risco '{declared}').\n"
                f"   Ele vai rodar com o MESMO poder que você — leia o código antes.\n"
                f"   Para instalar assim mesmo, use: nh plugin instalar {pid} --confiar")

    pasta = pasta_usuario()
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{pid}.py").write_text(codigo, encoding="utf-8")

    nome = man.get("nome") or item.get("nome") or pid
    ferramentas = item.get("ferramentas") or []
    return (f"✅ '{pid}' ({nome}) instalado em {pasta / (pid + '.py')}\n"
            f"   {len(ferramentas)} ferramenta(s): {', '.join(ferramentas) if ferramentas else '—'}\n"
            f"   risco máximo: {declared} · já está ativo (reinicie o nh web para aparecer na interface)")


def remover(pid: str) -> str:
    """Remove um plugin instalado (não mexe nos embutidos)."""
    alvo = pasta_usuario() / f"{pid}.py"
    pasta = pasta_usuario() / pid
    if alvo.is_file():
        alvo.unlink()
        return f"🗑️ plugin '{pid}' removido."
    if pasta.is_dir():
        import shutil

        shutil.rmtree(pasta)
        return f"🗑️ plugin '{pid}' removido (pasta)."
    return f"❌ '{pid}' não está instalado (só dá para remover o que você instalou)."


def _mudar_ativo(pid: str, ativo: bool) -> str:
    fora = set(str(x) for x in (read_config().get("plugins_desativados") or []))
    if ativo:
        fora.discard(pid)
    else:
        fora.add(pid)
    update_config(plugins_desativados=sorted(fora))
    verbo = "ativado" if ativo else "desativado"
    return (f"✅ plugin '{pid}' {verbo}. "
            + ("Ele volta a carregar na próxima execução." if ativo
               else "Nada foi apagado — `nh plugin ativar " + pid + "` reverte."))


def ativar(pid: str) -> str:
    """Liga um plugin que estava desativado (sem reinstalar)."""
    return _mudar_ativo(pid, True)


def desativar(pid: str) -> str:
    """Desliga um plugin sem apagar nada (ele some das ferramentas e do agente)."""
    return _mudar_ativo(pid, False)


# --------------------------------------------------------------------- kits ---
def kits() -> list[dict]:
    """Kits prontos: conjuntos de plugins por perfil de uso."""
    return catalogo().get("kits", [])


def instalar_kit(kid: str, *, confirmar_exec: bool = False) -> str:
    """Instala um kit inteiro (conjunto de plugins escolhido por perfil).

    Args:
        kid: id do kit (ex.: dev, celular, midia, obras, estudo).
        confirmar_exec: autoriza os plugins que executam comando dentro do kit.
    """
    kit = next((k for k in kits() if k.get("id") == kid), None)
    if kit is None:
        return f"❌ kit '{kid}' não existe. Disponíveis: {', '.join(k['id'] for k in kits())}"
    linhas = [f"📦 kit {kit.get('nome', kid)} — {kit.get('descricao', '')}"]
    ja = {m.get("id") for m in _manifestos_usuario()}
    for pid in kit.get("plugins", []):
        if pid in ja:
            linhas.append(f"   • {pid}: já instalado")
            continue
        r = instalar(pid, confirmar_exec=confirmar_exec)
        linhas.append(f"   • {pid}: {'ok' if r.startswith('✅') else r.splitlines()[0]}")
    return "\n".join(linhas)


__all__ = ["catalogo", "disponiveis", "instalados", "instalar", "remover", "ativar",
           "desativar", "kits", "instalar_kit", "conferir_risco", "conferir_manifesto"]
