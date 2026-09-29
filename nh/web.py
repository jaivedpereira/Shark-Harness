"""Interface web do Shark Harness — servida com a stdlib (zero dependências).

    nh web                 → http://127.0.0.1:8787  (só local)
    nh web --host 0.0.0.0  → expõe na rede (exige token, gerado e impresso)

O servidor usa o MESMO registry das outras frentes: a UI lista as ferramentas,
monta o formulário a partir do JSON Schema, executa de verdade e mostra o log de
auditoria. Trocar de frente não muda o que o agente pode fazer.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import urllib.error
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import agent, providers, scheduler
from .core import Registry, load_plugins
from .guard import AUDIT_FILE
from .paths import CONFIG_FILE, env, platform_name, read_config, update_config

WEBUI = Path(__file__).parent / "webui"

PLATFORM_LABEL = {
    "android": ("🤖", "Termux / Android"),
    "windows": ("🪟", "Windows"),
    "linux": ("🐧", "Linux"),
    "darwin": ("🍎", "macOS"),
}

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
}

# só estes arquivos da pasta webui podem ser servidos (nada de path traversal)
ESTATICOS = {
    "/", "/index.html", "/style.css", "/app.js",
    "/logo.jpg", "/logo.png", "/favicon.ico",
}


class Handler(BaseHTTPRequestHandler):
    reg: Registry
    token: str = ""
    max_risk: str = "exec"
    server_version = "SharkHarness"

    # ------------------------------------------------------------- utilidades
    def _json(self, obj, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, name: str) -> None:
        p = (WEBUI / name).resolve()
        if not str(p).startswith(str(WEBUI.resolve())) or not p.is_file():
            return self._json({"error": "não encontrado"}, 404)
        data = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(p.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception:  # noqa: BLE001
            return {}

    def _autorizado(self) -> bool:
        """Só exige token quando o servidor está exposto fora do localhost."""
        if not self.token:
            return True
        enviado = (
            self.headers.get("X-NH-Token")
            or (self.headers.get("Authorization") or "").replace("Bearer ", "")
        )
        if enviado == self.token:
            return True
        from urllib.parse import parse_qs, urlparse

        return parse_qs(urlparse(self.path).query).get("token", [""])[0] == self.token

    def log_message(self, *args) -> None:  # silencioso
        pass

    # ------------------------------------------------------------------ rotas
    def do_GET(self) -> None:  # noqa: N802
        from urllib.parse import urlparse

        rota = urlparse(self.path).path
        if rota in ESTATICOS:
            return self._file("index.html" if rota == "/" else rota.lstrip("/"))
        if rota == "/api/state":
            if not self._autorizado():
                return self._json({"error": "token inválido"}, 401)
            return self._json(self._estado())
        if rota == "/api/config":
            if not self._autorizado():
                return self._json({"error": "token inválido"}, 401)
            return self._json(self._config_atual())
        return self._json({"error": "rota desconhecida"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        from urllib.parse import urlparse

        if not self._autorizado():
            return self._json({"error": "token inválido"}, 401)
        rota = urlparse(self.path).path
        body = self._body()
        if rota == "/api/tool":
            nome = body.get("name", "")
            args = body.get("args") or {}
            return self._json({"result": self.reg.dispatch(nome, args)})
        if rota == "/api/cron":
            return self._json({"result": self._cron(body)})
        if rota == "/api/agent":
            return self._json(self._agente(body.get("prompt", "")))
        if rota == "/api/config":
            return self._json(self._salvar_config(body))
        if rota == "/api/config/testar":
            return self._json(self._testar_llm())
        return self._json({"error": "rota desconhecida"}, 404)

    # -------------------------------------------------------------- config LLM
    def _config_atual(self) -> dict:
        """Estado da configuração. A CHAVE NUNCA volta inteira — só um vislumbre."""
        cfg = read_config()
        chave = env("LLM_KEY")
        url = env("LLM_URL", agent.DEFAULT_URL)
        modelo = env("LLM_MODEL", agent.DEFAULT_MODEL)
        provider = cfg.get("provider") or providers.detectar(url)
        info = providers.achar(provider)
        return {
            "providers": providers.listar(),
            "atual": {
                "provider": provider,
                "label": (info or {}).get("label", "Personalizado"),
                "url": url,
                "model": modelo,
                "max_risk": env("MAX_RISK", self.max_risk),
                "tem_chave": bool(chave),
                # vislumbre: primeiros 6 e últimos 4 caracteres
                "chave_dica": (chave[:6] + "…" + chave[-4:]) if len(chave) > 12 else ("definida" if chave else ""),
                "origem": "ambiente" if (os.environ.get("SHARK_LLM_KEY") or os.environ.get("NH_LLM_KEY")) else ("arquivo" if cfg.get("llm_key") else ""),
            },
            "arquivo": str(CONFIG_FILE),
        }

    def _salvar_config(self, body: dict) -> dict:
        """Grava provedor/modelo/chave no config.json (permissão 600)."""
        provider = str(body.get("provider") or "").strip()
        url = str(body.get("url") or "").strip()
        modelo = str(body.get("model") or "").strip()
        chave = body.get("api_key")
        risco = str(body.get("max_risk") or "").strip()

        info = providers.achar(provider)
        if info and not url:
            url = info["url"]  # preenche a URL do provedor escolhido

        if not url:
            return {"ok": False, "erro": "informe a URL do provedor (ou escolha um da lista)."}
        if not url.startswith(("http://", "https://")):
            return {"ok": False, "erro": "a URL precisa começar com http:// ou https://"}
        if not modelo:
            return {"ok": False, "erro": "informe o nome do modelo."}
        if risco and risco not in ("safe", "write", "exec", "danger"):
            return {"ok": False, "erro": "risco inválido (use safe, write, exec ou danger)."}

        campos = {
            "provider": provider or providers.detectar(url),
            "llm_url": url,
            "llm_model": modelo,
        }
        if risco:
            campos["max_risk"] = risco
        # chave vazia = "não mexi na chave"; "remover" limpa; string nova grava
        if isinstance(chave, str) and chave.strip() and chave.strip() != "••••":
            campos["llm_key"] = chave.strip()
        elif chave == "remover":
            campos["llm_key"] = None

        try:
            update_config(**campos)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "erro": f"não consegui gravar: {exc}"}

        # o agente lê env() a cada chamada, então já vale sem reiniciar
        aviso = ""
        if os.environ.get("SHARK_LLM_KEY") or os.environ.get("NH_LLM_KEY"):
            aviso = ("Atenção: existe uma variável de ambiente LLM_KEY definida — "
                     "ela tem prioridade sobre o que você salvou aqui.")
        return {
            "ok": True,
            "msg": f"✅ configuração salva em {CONFIG_FILE}",
            "aviso": aviso,
            "atual": self._config_atual()["atual"],
        }

    def _testar_llm(self) -> dict:
        """Faz uma chamada mínima ao provedor para validar URL + chave + modelo."""
        url = env("LLM_URL", agent.DEFAULT_URL)
        modelo = env("LLM_MODEL", agent.DEFAULT_MODEL)
        chave = env("LLM_KEY")
        try:
            resp = agent._post(
                url,
                {
                    "model": modelo,
                    "messages": [{"role": "user", "content": "responda apenas: ok"}],
                    "max_tokens": 5,
                },
                chave,
                timeout=45,
            )
        except urllib.error.HTTPError as exc:
            corpo = exc.read().decode("utf-8", "replace")[:200]
            dica = ""
            if exc.code in (401, 403):
                dica = " — a chave parece inválida ou sem permissão."
            elif exc.code == 402:
                dica = " — a conta está sem saldo."
            elif exc.code == 404:
                dica = " — confira o nome do modelo nesse provedor."
            elif exc.code == 429:
                dica = " — rate-limit do provedor, tente de novo em instantes."
            return {"ok": False, "erro": f"HTTP {exc.code}: {corpo}{dica}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}

        resposta = ""
        try:
            resposta = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "msg": f"✅ conexão OK — o modelo respondeu: “{str(resposta).strip()[:40]}”"}

    # ----------------------------------------------------------------- estado
    def _estado(self) -> dict:
        plat = platform_name()
        icone, nome = PLATFORM_LABEL.get(plat, ("🖥️", plat))
        tools = [
            {
                "name": t.name,
                "description": t.description,
                "risk": t.risk,
                "plugin": t.plugin,
                "schema": t.schema,
            }
            for t in self.reg.subset(max_risk="danger")
        ]
        jobs = []
        for j in scheduler.load_jobs():
            jobs.append({
                **j.__dict__,
                "human": scheduler.describe_cron(j.cron),
            })
        audit = []
        if AUDIT_FILE.exists():
            try:
                linhas = AUDIT_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]
                audit = [json.loads(x) for x in linhas if x.strip()]
            except Exception:  # noqa: BLE001
                audit = []
        return {
            "platform": {"name": nome, "icon": icone, "raw": plat},
            "max_risk": self.max_risk,
            "tools": tools,
            "jobs": jobs,
            "audit": audit,
            "sysinfo": self.reg.dispatch("sysinfo_report", {}),
            "llm": {
                "url": env("LLM_URL", agent.DEFAULT_URL),
                "model": env("LLM_MODEL", agent.DEFAULT_MODEL),
                "configured": bool(env("LLM_KEY")),
            },
        }

    # -------------------------------------------------------------------- cron
    def _cron(self, body: dict) -> str:
        act = body.get("action")
        if act == "explain":
            return self.reg.dispatch("explain_cron", {"expressao": body.get("cron", "")})
        if act == "add":
            return self.reg.dispatch("schedule_task", {
                "nome": body.get("name", ""),
                "cron": body.get("cron", ""),
                "comando": body.get("payload", "") if body.get("kind") == "shell" else "",
                "ferramenta": body.get("payload", "") if body.get("kind") == "tool" else "",
                "args_json": body.get("args", ""),
            })
        if act in ("rm", "pause", "run"):
            fn = {"rm": "remove_task", "pause": "pause_task", "run": "run_task_now"}[act]
            return self.reg.dispatch(fn, {"id_ou_nome": body.get("id", "")})
        return f"ação desconhecida: {act}"

    # ------------------------------------------------------------------ agente
    def _agente(self, prompt: str) -> dict:
        if not prompt.strip():
            return {"answer": "pedido vazio", "steps": []}
        passos: list[dict] = []
        lock = threading.Lock()

        def on_step(tipo: str, nome: str, detalhe: str) -> None:
            with lock:
                passos.append({"tipo": tipo, "nome": nome, "detalhe": detalhe[:4000]})

        resposta = agent.run_agent(
            prompt,
            reg=self.reg,
            max_risk=self.max_risk,
            verbose=False,
            on_step=on_step,
        )
        return {"answer": resposta, "steps": passos}


def serve(
    host: str = "127.0.0.1",
    port: int = 8787,
    *,
    max_risk: str = "exec",
    open_browser: bool = True,
    quiet: bool = False,
) -> int:
    reg = load_plugins()
    Handler.reg = reg
    Handler.max_risk = max_risk
    Handler.token = "" if host in ("127.0.0.1", "localhost") else secrets.token_urlsafe(16)

    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}/"

    if not quiet:
        print("🦈  SHARK HARNESS")
        print(f"    interface  : {url}")
        print(f"    ferramentas: {len(reg.subset(max_risk='danger'))} · risco máx exposto: {max_risk}")
        if Handler.token:
            print(f"    ⚠️  exposto na rede — use o token: {Handler.token}")
            print(f"        abra: {url}?token={Handler.token}")
        print("    pare com Ctrl+C")

    if Handler.token and not quiet:
        url = f"{url}?token={Handler.token}"
    if open_browser and not quiet:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  interface parada")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())
