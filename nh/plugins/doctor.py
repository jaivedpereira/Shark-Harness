"""Plugin: doctor — diagnóstico do ambiente, com teste de escrita real.

É o primeiro lugar a rodar quando "não consigo criar arquivo". Em vez de adivinhar,
ele TENTA criar, apagar e reler, e diz exatamente qual caminho falhou e por quê —
com a dica de correção específica de cada plataforma (ex.: Termux precisa de
`termux-setup-storage` para escrever em /sdcard).
"""


from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from ..core import Registry
from ..paths import CONFIG_FILE, HOME, JOBS_FILE, WORKSPACE, has_cmd, platform_name

MANIFEST = {
    "id": "doctor",
    "nome": "Diagnóstico",
    "versao": "1.0.0",
    "autor": "jaivedpereira",
    "categoria": "núcleo",
    "descricao": "Testar se a escrita de arquivo funciona e checar o ambiente inteiro.",
    "risco_max": "write",
    "plataformas": ["linux", "windows", "darwin", "android"],
    "requer": [],
    "tags": ["diagnóstico", "debug", "ambiente"],
}


def _teste_escrita(pasta: Path) -> tuple[bool, str]:
    """Tenta criar, escrever, ler e apagar um arquivo. Devolve (ok, detalhe)."""
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        return False, f"não deu para criar a pasta: {type(exc).__name__}: {exc}"
    alvo = pasta / ".shark-teste-escrita.txt"
    try:
        alvo.write_text("teste do shark harness", encoding="utf-8")
        lido = alvo.read_text(encoding="utf-8")
        alvo.unlink()
        if lido != "teste do shark harness":
            return False, "escreveu mas releu diferente"
        return True, "criou, leu e apagou"
    except PermissionError as exc:
        return False, f"permissão negada ({exc.filename or pasta})"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def diagnostico() -> str:
    """Checa o ambiente inteiro e aponta o que está faltando, com como corrigir.

    Use sempre que algo "não funciona": ele testa escrita de arquivo, pastas de
    configuração, chave da IA, ferramentas de sistema e o agendador.
    """
    plat = platform_name()
    linhas: list[str] = []
    problemas: list[str] = []

    def item(ok: bool, rotulo: str, detalhe: str = "", dica: str = "") -> None:
        marca = "✅" if ok else "❌"
        linhas.append(f"{marca} {rotulo}" + (f" — {detalhe}" if detalhe else ""))
        if not ok and dica:
            problemas.append(f"   → {dica}")

    linhas.append("🩺 DIAGNÓSTICO DO SHARK HARNESS")
    linhas.append(f"   plataforma: {plat} · {platform.system()} {platform.release()} · {platform.machine()}")
    linhas.append(f"   python:     {sys.version.split()[0]}  ({sys.executable})")

    # ── 1. home e workspace (o que costuma quebrar no Termux) ──────────────
    linhas.append("")
    linhas.append("▸ PASTAS")
    home_ok, home_det = _teste_escrita(HOME)
    item(home_ok, f"pasta de config  {HOME}", home_det,
         f"não consigo escrever em {HOME}. Defina outra com: export SHARK_HOME=$HOME/.shark")

    ws_ok, ws_det = _teste_escrita(WORKSPACE)
    item(ws_ok, f"workspace         {WORKSPACE}", ws_det,
         "sem workspace gravável o `write_file` falha. Exporte: export SHARK_WORKSPACE=$HOME/shark-workspace")

    if plat == "android":
        teste_sd = Path("/sdcard")
        if teste_sd.exists():
            sd_ok, sd_det = _teste_escrita(teste_sd / "SharkHarness")
            item(sd_ok, "acesso ao /sdcard", sd_det,
                 "rode `termux-setup-storage` e autorize o acesso, depois: mkdir -p ~/storage/shared/SharkHarness")
        else:
            item(False, "acesso ao /sdcard", "não existe",
                 "rode `termux-setup-storage` e aceite a permissão do Android")

    # ── 2. IA ─────────────────────────────────────────────────────────────
    linhas.append("")
    linhas.append("▸ INTELIGÊNCIA (LLM)")
    from ..agent import DEFAULT_MODEL, DEFAULT_URL
    from ..paths import env

    url = env("LLM_URL", DEFAULT_URL)
    modelo = env("LLM_MODEL", DEFAULT_MODEL)
    chave = env("LLM_KEY")
    origem = ("variável de ambiente" if (os.environ.get("SHARK_LLM_KEY") or os.environ.get("NH_LLM_KEY"))
              else ("config.json" if CONFIG_FILE.exists() and _tem_chave_no_arquivo() else ""))
    item(bool(chave), "chave da API", f"{origem or 'nenhuma'}" + (f" · {chave[:6]}…{chave[-4:]}" if len(chave) > 12 else ""),
         "sem chave o chat não responde. Abra a interface → Configurações, ou export SHARK_LLM_KEY=...")
    linhas.append(f"   endpoint: {url}")
    linhas.append(f"   modelo:   {modelo}")
    item(True, "chave grátis", "openrouter.ai/keys tem modelos :free" if "openrouter" in url else "veja a aba Configurações")

    # ── 3. ambiente ───────────────────────────────────────────────────────
    linhas.append("")
    linhas.append("▸ AMBIENTE")
    if plat == "android":
        item(has_cmd("termux-notification"), "Termux:API (notificação/clipboard)",
             "instalado" if has_cmd("termux-notification") else "não encontrado",
             "rode: pkg install termux-api — e instale o app Termux:API pela F-Droid")
    item(has_cmd("git"), "git", "ok" if has_cmd("git") else "não instalado",
         "pkg install git (Termux) ou git-scm.com (Windows)")
    item(has_cmd("node"), "node", "ok" if has_cmd("node") else "não instalado (só afeta run_node)",
         "pkg install nodejs")
    item(bool(os.access(str(WORKSPACE), os.W_OK)), "permissão de escrita no workspace", str(WORKSPACE))

    # ── 4. agendador e auditoria ──────────────────────────────────────────
    linhas.append("")
    linhas.append("▸ AGENDADOR E REGISTRO")
    from .. import scheduler

    jobs = scheduler.load_jobs()
    item(True, "tarefas agendadas", f"{len(jobs)}" + (
        f" ({sum(1 for j in jobs if j.enabled)} ativas)" if jobs else ""))
    from ..guard import AUDIT_FILE

    n_audit = 0
    if AUDIT_FILE.exists():
        try:
            n_audit = sum(1 for _ in AUDIT_FILE.open(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            pass
    item(True, "log de auditoria", f"{n_audit} entradas em {AUDIT_FILE}")

    # ── 5. ferramentas ────────────────────────────────────────────────────
    linhas.append("")
    linhas.append("▸ FERRAMENTAS")
    from ..core import load_plugins

    reg = load_plugins()
    item(True, "ferramentas carregadas", f"{len(reg.names())}")
    from ..mcp_server import MCP_AVAILABLE

    item(True, "servidor MCP", "disponível" if MCP_AVAILABLE else "sem SDK (use no PC: pip install 'mcp[cli]')")

    if problemas:
        linhas.append("")
        linhas.append("🔧 O QUE CORRIGIR")
        linhas.extend(problemas)
    else:
        linhas.append("")
        linhas.append("🎉 Tudo certo — pode usar.")

    return "\n".join(linhas)


def _tem_chave_no_arquivo() -> bool:
    from ..paths import read_config

    return bool(read_config().get("llm_key"))


def testar_escrita(caminho: str = "") -> str:
    """Testa criar/ler/apagar um arquivo num caminho específico e diz o resultado.

    Use para descobrir exatamente por que uma pasta não aceita escrita.

    Args:
        caminho: pasta a testar (vazio = workspace atual).
    """
    alvo = Path(caminho).expanduser() if caminho else WORKSPACE
    ok, det = _teste_escrita(alvo)
    if ok:
        return f"✅ escrita funcionando em {alvo} ({det})"
    return (f"❌ NÃO consigo escrever em {alvo}\n   motivo: {det}\n"
            f"   dica: confira a permissão da pasta ou defina SHARK_WORKSPACE para outro lugar.")


def register(reg: Registry) -> None:
    reg.add(diagnostico, risk="safe", plugin="doctor")
    reg.add(testar_escrita, risk="write", plugin="doctor")
