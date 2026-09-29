"""Plugin: arquivos compactados e integridade — backup e restauração de verdade.

`zipar` + `deszipar` + `sha256` cobrem o caso mais comum de automação pessoal:
fazer backup de uma pasta, conferir que o arquivo baixado não corrompeu, e
restaurar depois.
"""


from __future__ import annotations

import hashlib
import os
import tarfile
import time
import zipfile
from pathlib import Path

from ..core import Registry, workspace
from ..guard import check_path

MANIFEST = {
    "id": "archive",
    "nome": "Backup e integridade",
    "versao": "1.0.0",
    "autor": "jaivedpereira",
    "categoria": "sistema",
    "descricao": "Compactar em zip/tar.gz, extrair, conferir hash e achar o que ocupa espaço.",
    "risco_max": "write",
    "plataformas": ["linux", "windows", "darwin", "android"],
    "requer": [],
    "tags": ["backup", "zip", "hash"],
}


def _destino(caminho: str) -> Path:
    p = Path(caminho).expanduser()
    if not p.is_absolute():
        p = workspace() / p
    return check_path(str(p))


def zipar(origem: str, destino: str = "", formato: str = "zip") -> str:
    """Compacta uma pasta ou arquivo (backup). Devolve o caminho do arquivo criado.

    Args:
        origem: pasta ou arquivo a compactar.
        destino: nome do arquivo de saída; vazio = workspace/backup-<data>.<formato>.
        formato: 'zip' ou 'tar.gz'.
    """
    src = Path(origem).expanduser()
    if not src.is_absolute():
        src = workspace() / src
    if not src.exists():
        return f"❌ não existe: {src}"

    if not destino:
        selo = time.strftime("%Y%m%d-%H%M%S")
        ext = "tar.gz" if formato == "tar.gz" else "zip"
        destino = str(workspace() / f"backup-{selo}.{ext}")
    dst = _destino(destino)
    dst.parent.mkdir(parents=True, exist_ok=True)

    try:
        if destino.endswith((".tar.gz", ".tgz")):
            with tarfile.open(dst, "w:gz") as tf:
                tf.add(src, arcname=src.name)
        else:
            with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
                if src.is_dir():
                    for p in src.rglob("*"):
                        if p.is_file():
                            z.write(p, p.relative_to(src.parent).as_posix())
                else:
                    z.write(src, src.name)
    except Exception as exc:  # noqa: BLE001
        return f"❌ falha ao compactar: {type(exc).__name__}: {exc}"

    return f"✅ backup criado: {dst} ({dst.stat().st_size / 1024:.0f} KB)"


def deszipar(arquivo: str, destino: str = "") -> str:
    """Extrai um .zip ou .tar.gz. Por segurança, só extrai dentro do destino escolhido.

    Args:
        arquivo: caminho do arquivo compactado.
        destino: pasta onde extrair; vazio = workspace/extraido-<nome>.
    """
    src = _destino(arquivo)
    if not src.is_file():
        return f"❌ não achei o arquivo: {src}"
    pasta = Path(destino).expanduser() if destino else (workspace() / f"extraido-{src.stem}")
    if not pasta.is_absolute():
        pasta = workspace() / pasta
    pasta = check_path(str(pasta))
    pasta.mkdir(parents=True, exist_ok=True)
    raiz = str(pasta.resolve())

    def _seguro(membro: str) -> bool:
        """Barra zip-slip: membro que escaparia da pasta de destino."""
        alvo = str((pasta / membro).resolve())
        return alvo == raiz or alvo.startswith(raiz + os.sep)

    try:
        n = 0
        if src.suffix == ".zip":
            with zipfile.ZipFile(src) as z:
                for info in z.infolist():
                    if _seguro(info.filename):
                        z.extract(info, pasta)
                        n += 1
        elif str(src).endswith((".tar.gz", ".tgz", ".tar")):
            with tarfile.open(src) as tf:
                for m in tf.getmembers():
                    if _seguro(m.name) and (m.isfile() or m.isdir()):
                        tf.extract(m, pasta)
                        n += 1
        else:
            return "❌ formato não suportado (use .zip ou .tar.gz)"
    except Exception as exc:  # noqa: BLE001
        return f"❌ falha ao extrair: {type(exc).__name__}: {exc}"
    if not n:
        return "⚠️ nada foi extraído (arquivo vazio ou todos os caminhos foram bloqueados)"
    return f"✅ {n} item(ns) extraído(s) em {pasta}"


def sha256(caminho: str) -> str:
    """Calcula o SHA-256 de um arquivo — confere se o download veio íntegro.

    Args:
        caminho: arquivo a verificar.
    """
    p = _destino(caminho)
    if not p.is_file():
        return f"❌ não achei o arquivo: {p}"
    h = hashlib.sha256()
    try:
        with p.open("rb") as fh:
            for bloco in iter(lambda: fh.read(1 << 20), b""):
                h.update(bloco)
    except Exception as exc:  # noqa: BLE001
        return f"❌ falha ao ler: {exc}"
    return f"🔐 sha256 de {p.name}\n   {h.hexdigest()}"


def tamanho_arquivos(path: str = ".", limite: int = 15) -> str:
    """Lista os maiores arquivos de uma pasta (acha o que está ocupando espaço).

    Args:
        path: pasta a analisar.
        limite: quantos arquivos mostrar.
    """
    base = Path(path).expanduser()
    if not base.is_absolute():
        base = workspace() / base
    if not base.is_dir():
        return f"❌ pasta inválida: {base}"
    itens: list[tuple[int, str]] = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".venv", "venv"}]
        for f in files:
            p = Path(root) / f
            try:
                itens.append((p.stat().st_size, str(p)))
            except OSError:
                continue
    if not itens:
        return f"📂 {base} — nenhum arquivo"
    itens.sort(reverse=True)
    total = sum(t for t, _ in itens)

    def h(n: float) -> str:
        for u in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f}{u}"
            n = n / 1024
        return f"{n:.1f}TB"

    linhas = [f"📊 {base} — {len(itens)} arquivos, {h(total)} no total", "   maiores:"]
    for t, nome in itens[: int(limite)]:
        linhas.append(f"   {h(t):>9}  {nome}")
    return "\n".join(linhas)


def register(reg: Registry) -> None:
    reg.add(zipar, risk="write", plugin="archive")
    reg.add(deszipar, risk="write", plugin="archive")
    reg.add(sha256, risk="safe", plugin="archive")
    reg.add(tamanho_arquivos, risk="safe", plugin="archive")
