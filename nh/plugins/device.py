"""Plugin: dispositivo — o harness mexendo no aparelho de verdade.

Multiplataforma, com degradação elegante:

| ação        | Termux/Android          | Linux              | Windows            | macOS        |
|-------------|-------------------------|--------------------|--------------------|--------------|
| notificação | termux-notification     | notify-send        | PowerShell toast   | osascript    |
| screenshot  | adb / screencap         | scrot/gnome-screenshot | PowerShell      | screencapture|
| clipboard   | termux-clipboard-*      | xclip/wl-paste     | clip/PowerShell    | pbcopy/pbpaste|
| abrir link  | termux-open-url         | xdg-open           | start              | open         |
| info        | termux-* + /proc        | /proc + df         | PowerShell/CIM     | sysctl       |

Se a ferramenta de sistema não existir, a resposta diz exatamente o que falta
(ex.: "instale termux-api") em vez de estourar um erro cru.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import time

from ..core import Registry, workspace
from ..paths import has_cmd, platform_name

PLAT = platform_name()


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or p.stderr).strip()
    except FileNotFoundError:
        return 127, f"comando não encontrado: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timeout ({timeout}s)"
    except Exception as exc:  # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"


# ------------------------------------------------------------------ notificar ---


def device_notify(titulo: str, mensagem: str = "") -> str:
    """Mostra uma notificação no aparelho (celular ou PC).

    Serve para o harness avisar você de algo sem precisar abrir nada — tarefa
    concluída, site caiu, download terminou.

    Args:
        titulo: título da notificação.
        mensagem: corpo do texto.
    """
    if PLAT == "android":
        if not has_cmd("termux-notification"):
            return "❌ falta o app Termux:API. Rode: pkg install termux-api (+ instale o app Termux:API da loja)."
        rc, out = _run(["termux-notification", "--title", titulo, "--content", mensagem or titulo])
        return "✅ notificação enviada" if rc == 0 else f"ERRO: {out}"

    if PLAT == "linux":
        if has_cmd("notify-send"):
            rc, out = _run(["notify-send", titulo, mensagem or titulo])
            return "✅ notificação enviada" if rc == 0 else f"ERRO: {out}"
        return "❌ notify-send não instalado (apt install libnotify-bin)."

    if PLAT == "windows":
        ps = (
            "[reflection.assembly]::loadwithpartialname('System.Windows.Forms')|Out-Null;"
            "$n=New-Object System.Windows.Forms.NotifyIcon;"
            "$n.Icon=[System.Drawing.SystemIcons]::Information;$n.Visible=$true;"
            f"$n.ShowBalloonTip(6000,'{titulo}','{mensagem or titulo}',0);Start-Sleep 7;$n.Dispose()"
        )
        rc, out = _run(["powershell", "-NoProfile", "-Command", ps], timeout=20)
        return "✅ notificação enviada" if rc == 0 else f"ERRO: {out}"

    if PLAT == "darwin":
        rc, out = _run(["osascript", "-e", f'display notification "{mensagem}" with title "{titulo}"'])
        return "✅ notificação enviada" if rc == 0 else f"ERRO: {out}"

    return f"❌ plataforma não suportada: {PLAT}"


# ----------------------------------------------------------------- screenshot ---


def device_screenshot(salvar_em: str = "") -> str:
    """Tira um print da tela e salva num arquivo do workspace.

    Args:
        salvar_em: caminho de destino; vazio = workspace/screenshot-<hora>.png
    """
    dest = salvar_em or str(workspace() / f"screenshot-{time.strftime('%Y%m%d-%H%M%S')}.png")

    if PLAT == "android":
        # screencap funciona em alguns aparelhos; adb é o caminho confiável
        if shutil.which("screencap"):
            rc, out = _run(["screencap", "-p"], timeout=20)
            if rc == 0:
                return f"(saída binária ignorada) — use adb: adb exec-out screencap -p > {dest}"
        for tool in ("scrot", "gnome-screenshot", "import"):
            if has_cmd(tool):
                break
        rc, out = _run(["termux-camera-photo", "-c", "0", dest], timeout=30)
        if rc == 0:
            return f"📷 (câmera, não tela) salvo em {dest} — print de tela no Android exige adb/root."
        return (
            "❌ print de tela no Android sem root não é possível por API pública.\n"
            "   Alternativas: `adb exec-out screencap -p > print.png` (via USB/PC) "
            "ou instalar um app de acessibilidade."
        )

    if PLAT == "linux":
        for tool, args in (
            ("gnome-screenshot", ["-f", dest]),
            ("scrot", [dest]),
            ("import", ["-window", "root", dest]),
        ):
            if has_cmd(tool):
                rc, out = _run([tool, *args], timeout=30)
                return f"📸 salvo em {dest}" if rc == 0 else f"ERRO ({tool}): {out}"
        return "❌ instale scrot ou gnome-screenshot (ou use xdg-desktop-portal)."

    if PLAT == "windows":
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
            "$b=[System.Windows.Forms.SystemInformation]::VirtualScreen;"
            "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
            "$g=[System.Drawing.Graphics]::FromImage($bmp);"
            "$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);"
            f"$bmp.Save('{dest}')"
        )
        rc, out = _run(["powershell", "-NoProfile", "-Command", ps], timeout=40)
        return f"📸 salvo em {dest}" if rc == 0 else f"ERRO: {out}"

    if PLAT == "darwin":
        rc, out = _run(["screencapture", dest], timeout=30)
        return f"📸 salvo em {dest}" if rc == 0 else f"ERRO: {out}"

    return f"❌ plataforma não suportada: {PLAT}"


# ------------------------------------------------------------------ clipboard ---


def device_clipboard_ler() -> str:
    """Lê o texto que está na área de transferência do aparelho."""
    if PLAT == "android":
        if not has_cmd("termux-clipboard-get"):
            return "❌ falta Termux:API (pkg install termux-api)."
        rc, out = _run(["termux-clipboard-get"])
        return out if rc == 0 else f"ERRO: {out}"
    if PLAT == "windows":
        rc, out = _run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"])
        return out if rc == 0 else f"ERRO: {out}"
    if PLAT == "darwin":
        rc, out = _run(["pbpaste"])
        return out if rc == 0 else f"ERRO: {out}"
    for tool in ("wl-paste", "xclip"):
        if has_cmd(tool):
            args = ["-o"] if tool == "wl-paste" else ["-selection", "clipboard", "-o"]
            rc, out = _run([tool, *args])
            return out if rc == 0 else f"ERRO: {out}"
    return "❌ instale xclip ou wl-clipboard."


def device_clipboard_escrever(texto: str) -> str:
    """Coloca um texto na área de transferência do aparelho.

    Args:
        texto: o texto a copiar (fica pronto pra colar em qualquer app).
    """
    if PLAT == "android":
        if not has_cmd("termux-clipboard-set"):
            return "❌ falta Termux:API (pkg install termux-api)."
        rc, out = _run(["termux-clipboard-set", texto])
        return "✅ copiado" if rc == 0 else f"ERRO: {out}"
    if PLAT == "windows":
        rc, out = _run(["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{texto}'"])
        return "✅ copiado" if rc == 0 else f"ERRO: {out}"
    if PLAT == "darwin":
        try:
            subprocess.run(["pbcopy"], input=texto, text=True, timeout=10, check=True)
            return "✅ copiado"
        except Exception as exc:  # noqa: BLE001
            return f"ERRO: {exc}"
    for tool in ("wl-copy", "xclip"):
        if has_cmd(tool):
            args: list[str] = [] if tool == "wl-copy" else ["-selection", "clipboard"]
            try:
                subprocess.run([tool, *args], input=texto, text=True, timeout=10, check=True)
                return "✅ copiado"
            except Exception as exc:  # noqa: BLE001
                return f"ERRO: {exc}"
    return "❌ instale xclip ou wl-clipboard."


# ------------------------------------------------------------------ abrir link ---


def device_abrir(url: str) -> str:
    """Abre uma URL ou um app no aparelho (navegador padrão).

    Args:
        url: link (https://...) ou esquema de app (ex.: 'whatsapp://send?text=oi').
    """
    if PLAT == "android":
        if has_cmd("termux-open-url"):
            rc, out = _run(["termux-open-url", url])
            return f"✅ abrindo {url}" if rc == 0 else f"ERRO: {out}"
        rc, out = _run(["am", "start", "-a", "android.intent.action.VIEW", "-d", url])
        return f"✅ abrindo {url}" if rc == 0 else f"ERRO: {out}"
    if PLAT == "windows":
        rc, out = _run(["cmd", "/c", "start", "", url])
        return "✅ abrindo" if rc == 0 else f"ERRO: {out}"
    if PLAT == "darwin":
        rc, out = _run(["open", url])
        return "✅ abrindo" if rc == 0 else f"ERRO: {out}"
    if has_cmd("xdg-open"):
        rc, out = _run(["xdg-open", url])
        return "✅ abrindo" if rc == 0 else f"ERRO: {out}"
    return "❌ instale xdg-open."


def register(reg: Registry) -> None:
    reg.add(device_notify, risk="write", plugin="device")
    reg.add(device_screenshot, risk="write", plugin="device")
    reg.add(device_clipboard_ler, risk="safe", plugin="device")
    reg.add(device_clipboard_escrever, risk="write", plugin="device")
    reg.add(device_abrir, risk="write", plugin="device")
