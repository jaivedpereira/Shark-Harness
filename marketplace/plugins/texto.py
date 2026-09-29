"""Plugin: texto — utilitários de texto, codificação e senhas.

Tarefas pequenas que sempre dão trabalho na mão: codificar/decodificar base64,
gerar senha forte, tirar hash, contar palavras, achar links e fazer slug de título.
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
import string
import unicodedata

MANIFEST = {
    "id": "texto",
    "nome": "Texto e Senhas",
    "versao": "1.0.0",
    "autor": "jaivedpereira",
    "categoria": "utilidades",
    "descricao": "Base64, senha forte, hash, contagem de texto, extrair links e slug de título.",
    "risco_max": "safe",
    "plataformas": ["linux", "windows", "darwin", "android"],
    "requer": [],
    "tags": ["texto", "utilidades", "senha", "base64"],
}


def base64_codificar(texto: str) -> str:
    """Transforma um texto em base64 (útil para embutir conteúdo em URL/JSON).

    Args:
        texto: o texto a codificar.
    """
    return f"🔐 base64:\n{base64.b64encode(str(texto).encode('utf-8')).decode('ascii')}"


def base64_decodificar(codigo: str) -> str:
    """Volta um base64 para o texto original.

    Args:
        codigo: o texto em base64.
    """
    try:
        limpo = "".join(str(codigo).split())
        return f"📖 decodificado:\n{base64.b64decode(limpo + '=' * (-len(limpo) % 4)).decode('utf-8', 'replace')}"
    except Exception as exc:  # noqa: BLE001
        return f"❌ não é um base64 válido: {exc}"


def gerar_senha(tamanho: int = 20, simbolos: bool = True, quantidade: int = 1) -> str:
    """Gera senha forte de verdade (aleatoriedade do sistema, não rand comum).

    Args:
        tamanho: número de caracteres (mínimo 8).
        simbolos: incluir símbolos como !@#$%.
        quantidade: quantas senhas gerar.
    """
    n = max(8, min(int(tamanho), 200))
    alfabeto = string.ascii_letters + string.digits + ("!@#$%&*+-=?" if simbolos else "")
    senhas = ["".join(secrets.choice(alfabeto) for _ in range(n)) for _ in range(max(1, min(int(quantidade), 20)))]
    entropia = n * (len(alfabeto).bit_length() - 1)
    return ("🔑 senha(s) gerada(s):\n" + "\n".join("   " + s for s in senhas)
            + f"\n   força: ~{entropia} bits de entropia "
            + ("(excelente)" if entropia >= 100 else "(boa)" if entropia >= 70 else "(fraca — aumente o tamanho)"))


def hash_texto(texto: str, algoritmo: str = "sha256") -> str:
    """Hash de um texto (confere se um conteúdo mudou sem guardar o conteúdo).

    Args:
        texto: texto a resumir.
        algoritmo: md5, sha1, sha256 ou sha512.
    """
    alg = str(algoritmo).lower()
    if alg not in ("md5", "sha1", "sha256", "sha512"):
        return "❌ algoritmo inválido (use md5, sha1, sha256 ou sha512)."
    h = hashlib.new(alg, str(texto).encode("utf-8")).hexdigest()
    return f"🧾 {alg}:\n   {h}"


def contar_texto(texto: str) -> str:
    """Estatística de um texto: caracteres, palavras, linhas e tempo de leitura.

    Args:
        texto: o texto a medir.
    """
    t = str(texto)
    palavras = re.findall(r"\b[\w'-]+\b", t, flags=re.UNICODE)
    linhas = t.splitlines() or [""]
    minutos = len(palavras) / 200 if palavras else 0
    sem_espacos = len(re.sub(r"\s", "", t))
    return (f"📊 TEXTO\n   caracteres: {len(t)} (sem espaços: {sem_espacos})\n"
            f"   palavras..: {len(palavras)}\n   linhas....: {len(linhas)}\n"
            f"   leitura...: {minutos:.1f} min (~200 palavras/min)")


def extrair_links(texto: str) -> str:
    """Lista todos os links http/https encontrados num texto.

    Args:
        texto: texto ou HTML onde procurar.
    """
    achados = re.findall(r"https?://[^\s\"'<>)\]]+", str(texto))
    vistos = list(dict.fromkeys(achados))
    if not vistos:
        return "🔍 nenhum link encontrado."
    return f"🔗 {len(vistos)} link(s):\n" + "\n".join("   " + u for u in vistos[:50])


def slug(titulo: str) -> str:
    """Transforma um título num slug para URL/nome de arquivo.

    Args:
        titulo: texto original, ex.: "Cálculo de Concreto — Parte 1".
    """
    s = unicodedata.normalize("NFKD", str(titulo)).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    final = re.sub(r"[-\s]+", "-", s)
    return f"🔗 slug: {final}"


def register(reg) -> None:
    reg.add(base64_codificar, risk="safe", plugin="texto")
    reg.add(base64_decodificar, risk="safe", plugin="texto")
    reg.add(gerar_senha, risk="safe", plugin="texto")
    reg.add(hash_texto, risk="safe", plugin="texto")
    reg.add(contar_texto, risk="safe", plugin="texto")
    reg.add(extrair_links, risk="safe", plugin="texto")
    reg.add(slug, risk="safe", plugin="texto")
