"""Plugin: net — rede. Buscar APIs, baixar arquivo, checar se um serviço está no ar.

Estas são as ferramentas que mais destravam o agente: com elas ele consulta APIs
reais (preço, clima, CEP, cotação), baixa conteúdo e verifica se teu servidor caiu.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ..core import Registry, workspace
from ..guard import check_path

UA = "Mozilla/5.0 (compatible; SharkHarness/0.1)"  # vários provedores recusam UA de urllib
MAX_TEXTO = 8000


def _requisicao(url: str, *, dados: bytes | None = None, timeout: int = 30,
                headers: dict | None = None) -> tuple[int, dict, bytes]:
    cab = {"User-Agent": UA, "Accept": "*/*"}
    if dados is not None:
        cab.setdefault("Content-Type", "application/json")
    cab.update(headers or {})
    req = urllib.request.Request(url, data=dados, headers=cab,
                                 method="POST" if dados is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=max(1, min(int(timeout), 120))) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read()


def http_get(url: str, timeout: int = 30) -> str:
    """Faz um GET numa URL e devolve o corpo (JSON formatado, ou texto).

    Serve para consultar APIs públicas, verificar se um site responde, ler uma
    página. Sempre prefira isso a inventar dados.

    Args:
        url: endereço completo, começando com http:// ou https://.
        timeout: segundos antes de desistir.
    """
    if not url.startswith(("http://", "https://")):
        return "❌ a URL precisa começar com http:// ou https://"
    try:
        status, cab, corpo = _requisicao(url, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return f"❌ falha ao conectar: {type(exc).__name__}: {exc}"

    tipo = cab.get("Content-Type", "")
    texto = corpo.decode("utf-8", "replace")
    if "json" in tipo or texto.lstrip().startswith(("{", "[")):
        try:
            texto = json.dumps(json.loads(texto), ensure_ascii=False, indent=2)
        except Exception:  # noqa: BLE001
            pass
    if len(texto) > MAX_TEXTO:
        texto = texto[:MAX_TEXTO] + f"\n… (cortado, {len(texto)} chars no total)"
    return f"🌐 HTTP {status} · {tipo or 'sem content-type'}\n{texto}"


def http_post(url: str, corpo_json: str = "{}", timeout: int = 30) -> str:
    """Faz um POST enviando JSON e devolve a resposta.

    Args:
        url: endereço completo (http:// ou https://).
        corpo_json: corpo da requisição como JSON em texto, ex.: '{"a": 1}'.
        timeout: segundos antes de desistir.
    """
    if not url.startswith(("http://", "https://")):
        return "❌ a URL precisa começar com http:// ou https://"
    try:
        dados = corpo_json.encode("utf-8") if corpo_json.strip() else b"{}"
        json.loads(dados)  # valida antes de enviar
    except json.JSONDecodeError as exc:
        return f"❌ corpo_json inválido: {exc}"
    try:
        status, cab, corpo = _requisicao(url, dados=dados, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return f"❌ falha ao conectar: {type(exc).__name__}: {exc}"
    texto = corpo.decode("utf-8", "replace")
    try:
        texto = json.dumps(json.loads(texto), ensure_ascii=False, indent=2)
    except Exception:  # noqa: BLE001
        pass
    return f"🌐 HTTP {status} (POST)\n{texto[:MAX_TEXTO]}"


def baixar_arquivo(url: str, destino: str = "", timeout: int = 120) -> str:
    """Baixa um arquivo da internet e salva no disco (workspace por padrão).

    Args:
        url: endereço do arquivo.
        destino: caminho de destino; vazio = workspace com o nome original.
        timeout: segundos antes de desistir.
    """
    if not url.startswith(("http://", "https://")):
        return "❌ a URL precisa começar com http:// ou https://"
    nome = Path(urllib.parse.urlparse(url).path).name or "download.bin"
    alvo = check_path(destino) if destino else (workspace() / nome)
    if not alvo.is_absolute():
        alvo = workspace() / alvo
    alvo = check_path(str(alvo))
    try:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        status, cab, corpo = _requisicao(url, timeout=timeout)
        if status >= 400:
            return f"❌ o servidor respondeu HTTP {status} — nada foi salvo."
        alvo.write_bytes(corpo)
    except Exception as exc:  # noqa: BLE001
        return f"❌ falha no download: {type(exc).__name__}: {exc}"
    kb = len(corpo) / 1024
    return f"✅ baixado ({kb:.0f} KB) → {alvo}"


def port_check(host: str = "127.0.0.1", porta: int = 80, timeout: int = 5) -> str:
    """Testa se uma porta/serviço está aberto (ex.: teu servidor está no ar?).

    Args:
        host: máquina (ex.: 127.0.0.1, localhost, 192.168.0.10).
        porta: número da porta (ex.: 8787, 80, 443, 22).
        timeout: segundos de espera.
    """
    try:
        with socket.create_connection((host, int(porta)), timeout=max(1, min(int(timeout), 30))):
            pass
    except socket.timeout:
        return f"⏱️ {host}:{porta} — tempo esgotado (nada respondendo)"
    except ConnectionRefusedError:
        return f"❌ {host}:{porta} — fechada (conexão recusada)"
    except Exception as exc:  # noqa: BLE001
        return f"❌ {host}:{porta} — {type(exc).__name__}: {exc}"
    return f"✅ {host}:{porta} — ABERTA e respondendo"


def ip_publico() -> str:
    """Descobre o IP público desta conexão (e a cidade aproximada)."""
    try:
        status, _, corpo = _requisicao("https://ipinfo.io/json", timeout=15)
        if status == 200:
            d = json.loads(corpo.decode("utf-8", "replace"))
            return (f"🌍 IP: {d.get('ip')}\n   {d.get('city')}/{d.get('region')} — "
                    f"{d.get('country')}\n   provedor: {d.get('org')}")
    except Exception:  # noqa: BLE001
        pass
    try:
        status, _, corpo = _requisicao("https://api.ipify.org?format=json", timeout=15)
        return f"🌍 IP público: {json.loads(corpo.decode()).get('ip')}"
    except Exception as exc:  # noqa: BLE001
        return f"❌ não consegui descobrir: {exc}"


def cep(cep_numero: str) -> str:
    """Consulta um CEP brasileiro e devolve o endereço (rua, bairro, cidade/UF).

    Args:
        cep_numero: os 8 dígitos do CEP (com ou sem traço).
    """
    limpo = "".join(c for c in cep_numero if c.isdigit())
    if len(limpo) != 8:
        return "❌ informe os 8 dígitos do CEP, ex.: 01001000"
    try:
        status, _, corpo = _requisicao(f"https://viacep.com.br/ws/{limpo}/json/", timeout=20)
        d = json.loads(corpo.decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        return f"❌ falha na consulta: {exc}"
    if d.get("erro"):
        return f"❌ CEP {limpo} não encontrado."
    return (f"📮 {limpo}\n   {d.get('logradouro') or '(sem logradouro)'}"
            + (f", {d.get('complemento')}" if d.get("complemento") else "")
            + f"\n   bairro: {d.get('bairro')}\n   {d.get('localidade')}/{d.get('uf')}")


def clima(cidade: str) -> str:
    """Consulta a temperatura e o tempo agora numa cidade (sem chave de API).

    Args:
        cidade: nome da cidade, ex.: "São Paulo" ou "Fortaleza".
    """
    try:
        q = urllib.parse.urlencode({"name": cidade, "count": 1, "language": "pt"})
        _, _, corpo = _requisicao(f"https://geocoding-api.open-meteo.com/v1/search?{q}", timeout=20)
        geo = json.loads(corpo.decode("utf-8", "replace")).get("results") or []
        if not geo:
            return f"❌ não achei a cidade '{cidade}'"
        c = geo[0]
        params = urllib.parse.urlencode({
            "latitude": c["latitude"], "longitude": c["longitude"],
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,weather_code",
            "timezone": "auto",
        })
        _, _, corpo = _requisicao(f"https://api.open-meteo.com/v1/forecast?{params}", timeout=20)
        at = json.loads(corpo.decode("utf-8", "replace"))["current"]
    except Exception as exc:  # noqa: BLE001
        return f"❌ falha na consulta: {type(exc).__name__}: {exc}"
    icones = {0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️", 45: "🌫️", 48: "🌫️",
              51: "🌦️", 61: "🌧️", 63: "🌧️", 65: "⛈️", 71: "🌨️", 80: "🌧️", 95: "⛈️"}
    return (f"{icones.get(at.get('weather_code'), '🌡️')} {c['name']}/{c.get('country_code', '')}\n"
            f"   temperatura: {at.get('temperature_2m')}°C (sensação {at.get('apparent_temperature')}°C)\n"
            f"   umidade: {at.get('relative_humidity_2m')}% · vento: {at.get('wind_speed_10m')} km/h")


def register(reg: Registry) -> None:
    reg.add(http_get, risk="safe", plugin="net")
    reg.add(port_check, risk="safe", plugin="net")
    reg.add(ip_publico, risk="safe", plugin="net")
    reg.add(cep, risk="safe", plugin="net")
    reg.add(clima, risk="safe", plugin="net")
    reg.add(http_post, risk="write", plugin="net")
    reg.add(baixar_arquivo, risk="write", plugin="net")
