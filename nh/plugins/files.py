"""Plugin: arquivos — ler, escrever, listar e procurar em disco.

Toda escrita passa por `guard.check_path`, que barra caminhos críticos do
sistema e vetores de persistência automática (~/.bashrc, authorized_keys, etc.).
"""


from __future__ import annotations

import fnmatch
import os
import shutil
from pathlib import Path

from ..core import Registry, workspace
from ..guard import check_path

MAX_READ = 20000

MANIFEST = {
    "id": "files",
    "nome": "Arquivos",
    "versao": "1.0.0",
    "autor": "jaivedpereira",
    "categoria": "sistema",
    "descricao": "Ler, escrever, listar, procurar por nome e por conteúdo, criar pasta e apagar.",
    "risco_max": "danger",
    "plataformas": ["linux", "windows", "darwin", "android"],
    "requer": [],
    "tags": ["arquivo", "pasta", "disco"],
}


def _abs(path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = workspace() / p
    return check_path(str(p), writing=False)


def _target(path: str) -> Path:
    """Resolve o destino ANTES de validar.

    Importante: `check_path` faz `.resolve()`, que ancora caminho relativo no
    cwd do processo. Por isso o workspace precisa ser aplicado primeiro —
    senão `write_file("x.txt")` grava no diretório de onde o `nh` foi chamado.
    """
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = workspace() / p
    return check_path(str(p))


def read_file(path: str, inicio: int = 1, limite: int = 400) -> str:
    """Lê um arquivo de texto e devolve o conteúdo numerado por linha.

    Args:
        path: caminho do arquivo (relativo = dentro do workspace).
        inicio: linha inicial (1 = começo).
        limite: quantas linhas devolver.
    """
    p = _abs(path)
    if not p.exists():
        return f"❌ não existe: {p}"
    if p.is_dir():
        return f"❌ {p} é um diretório (use list_dir)"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return f"ERRO lendo {p}: {exc}"

    lines = text.splitlines()
    ini = max(1, int(inicio))
    fim = min(len(lines), ini - 1 + max(1, int(limite)))
    body = "\n".join(f"{i}|{lines[i - 1]}" for i in range(ini, fim + 1))
    head = f"📄 {p}  ({len(lines)} linhas, mostrando {ini}-{fim})"
    out = f"{head}\n{body}"
    return out[:MAX_READ] + (f"\n… truncado ({len(out)} chars)" if len(out) > MAX_READ else "")


def write_file(path: str, conteudo: str, append: bool = False) -> str:
    """Cria ou sobrescreve um arquivo de texto (cria as pastas necessárias).

    Args:
        path: caminho do arquivo (relativo = dentro do workspace).
        conteudo: conteúdo a gravar.
        append: True para acrescentar no fim em vez de sobrescrever.
    """
    p = _target(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a" if append else "w", encoding="utf-8") as fh:
            fh.write(conteudo)
    except PermissionError:
        return (
            f"❌ PERMISSÃO NEGADA ao escrever em {p}\n"
            f"   a pasta {p.parent} não aceita escrita.\n"
            + ("   No Termux, para gravar em /sdcard rode `termux-setup-storage`.\n"
               if str(p).startswith(("/sdcard", "/storage")) else "")
            + "   Alternativa: defina outro destino com  export SHARK_WORKSPACE=$HOME/shark-workspace"
        )
    except IsADirectoryError:
        return f"❌ {p} é uma PASTA — escolha um nome de arquivo."
    except FileNotFoundError as exc:
        return f"❌ caminho inválido para {p}: {exc}\n   confira se as pastas-pai existem."
    except OSError as exc:
        return f"❌ erro do sistema ao escrever {p}: {exc.strerror or exc} (errno {exc.errno})"
    except Exception as exc:  # noqa: BLE001
        return f"❌ erro inesperado ao escrever {p}: {type(exc).__name__}: {exc}"
    return f"✅ {'acrescentado em' if append else 'gravado'}: {p} ({len(conteudo)} chars)"


def list_dir(path: str = ".", mostrar_ocultos: bool = False) -> str:
    """Lista o conteúdo de um diretório com tamanho e tipo.

    Args:
        path: diretório (relativo = dentro do workspace).
        mostrar_ocultos: incluir arquivos que começam com ponto.
    """
    p = _abs(path)
    if not p.exists():
        return f"❌ não existe: {p}"
    if not p.is_dir():
        return f"❌ {p} não é diretório"
    items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    if not mostrar_ocultos:
        items = [i for i in items if not i.name.startswith(".")]
    if not items:
        return f"📂 {p} (vazio)"
    lines = [f"📂 {p}  ({len(items)} itens)"]
    for i in items[:200]:
        if i.is_dir():
            lines.append(f"  {i.name}/")
        else:
            try:
                lines.append(f"  {i.name}  ({i.stat().st_size:,} bytes)")
            except OSError:
                lines.append(f"  {i.name}")
    return "\n".join(lines)


def find_files(padrao: str, path: str = ".", limite: int = 60) -> str:
    """Procura arquivos por nome (glob) dentro de uma pasta, recursivamente.

    Args:
        padrao: padrão do nome, ex.: "*.py", "manga*", "*.m3u".
        path: pasta onde começar a busca.
        limite: máximo de resultados.
    """
    base = _abs(path)
    if not base.is_dir():
        return f"❌ pasta inválida: {base}"
    hits: list[str] = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", "venv", ".venv"}]
        for f in files:
            if fnmatch.fnmatch(f, padrao):
                hits.append(str(Path(root) / f))
                if len(hits) >= int(limite):
                    break
        if len(hits) >= int(limite):
            break
    if not hits:
        return f"🔍 nada encontrado para '{padrao}' em {base}"
    return f"🔍 {len(hits)} resultado(s) para '{padrao}':\n" + "\n".join(f"  {h}" for h in hits)


def make_dir(path: str) -> str:
    """Cria uma pasta (e as pastas-pai que faltarem).

    Args:
        path: caminho da pasta a criar.
    """
    p = _target(path)
    p.mkdir(parents=True, exist_ok=True)
    return f"✅ pasta criada: {p}"


def delete_path(path: str) -> str:
    """⚠️ APAGA um arquivo ou pasta (recursivo). Use com cuidado.

    Args:
        path: o que apagar. Não aceita raiz do sistema nem caminho crítico.
    """
    p = _target(path)
    if str(p) in ("/", str(Path.home())):
        return "🛑 bloqueado: recusei apagar a raiz ou o home inteiro."
    if not p.exists():
        return f"❌ não existe: {p}"
    try:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
    except Exception as exc:  # noqa: BLE001
        return f"ERRO apagando {p}: {exc}"
    return f"🗑️ apagado: {p}"


def register(reg: Registry) -> None:
    reg.add(read_file, risk="safe", plugin="files")
    reg.add(list_dir, risk="safe", plugin="files")
    reg.add(find_files, risk="safe", plugin="files")
    reg.add(grep_files, risk="safe", plugin="files")
    reg.add(write_file, risk="write", plugin="files")
    reg.add(make_dir, risk="write", plugin="files")
    reg.add(delete_path, risk="danger", plugin="files")


def grep_files(termo: str, path: str = ".", limite: int = 40) -> str:
    """Procura um texto DENTRO dos arquivos (não só no nome) e mostra as linhas.

    Muito útil para achar onde algo está definido num projeto.

    Args:
        termo: texto ou trecho a procurar (sem regex, busca literal).
        path: pasta ou arquivo onde procurar.
        limite: máximo de linhas de resultado.
    """
    base = _abs(path)
    alvos: list[Path] = []
    if base.is_file():
        alvos = [base]
    elif base.is_dir():
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", "venv", ".venv"}]
            alvos.extend(Path(root) / f for f in files)
    else:
        return f"❌ caminho inválido: {base}"

    achados: list[str] = []
    lidos = 0
    for arq in alvos:
        if len(achados) >= int(limite):
            break
        try:
            if arq.stat().st_size > 3_000_000:  # pula arquivos gigantes/binários óbvios
                continue
            texto = arq.read_text(encoding="utf-8", errors="strict")
        except Exception:  # noqa: BLE001
            continue
        lidos += 1
        for n, linha in enumerate(texto.splitlines(), 1):
            if termo.lower() in linha.lower():
                achados.append(f"{arq}:{n}: {linha.strip()[:160]}")
                if len(achados) >= int(limite):
                    break

    if not achados:
        return f"🔍 '{termo}' não encontrado em {base} ({lidos} arquivos de texto lidos)"
    return (f"🔍 {len(achados)} ocorrência(s) de '{termo}':\n" + "\n".join(achados))
