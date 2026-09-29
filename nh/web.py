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
import queue
import secrets
import threading
import urllib.error
import webbrowser
from urllib.parse import unquote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import agent, providers, scheduler
from .core import Registry, load_plugins, workspace
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
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}

# só estes arquivos da pasta webui podem ser servidos (nada de path traversal)
ESTATICOS = {
    "/", "/index.html", "/style.css", "/app.js",
    "/logo.jpg", "/logo.png", "/favicon.ico", "/manifest.webmanifest",
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
        if rota == "/api/plugins":
            if not self._autorizado():
                return self._json({"error": "token inválido"}, 401)
            return self._json(self._estado_plugins())
        if rota == "/api/usage":
            if not self._autorizado():
                return self._json({"error": "token inválido"}, 401)
            dias = 30
            try:
                q = dict(pair.split("=", 1) for pair in urlparse(self.path).query.split("&") if "=" in pair)
                dias = max(1, min(int(q.get("dias", 30)), 365))
            except (ValueError, TypeError):
                dias = 30
            return self._json(self._uso(dias))
        if rota == "/api/sessoes":
            if not self._autorizado():
                return self._json({"error": "token inválido"}, 401)
            return self._json(self._sessoes())
        if rota == "/api/saude":
            if not self._autorizado():
                return self._json({"error": "token inválido"}, 401)
            return self._json(self._saude())
        if rota == "/api/modelos":
            if not self._autorizado():
                return self._json({"error": "token inválido"}, 401)
            return self._json(self._modelos())
        if rota == "/api/fs":
            if not self._autorizado():
                return self._json({"error": "token inválido"}, 401)
            q = dict(pair.split("=", 1) for pair in urlparse(self.path).query.split("&") if "=" in pair)
            return self._json(self._listar_pasta(unquote(q.get("pasta", ""))))
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
            return self._json(self._agente(body.get("prompt", ""), str(body.get("sessao") or "")))
        if rota == "/api/agente/stream":
            return self._agente_stream(body)
        if rota == "/api/config":
            return self._json(self._salvar_config(body))
        if rota == "/api/plugins":
            return self._json(self._acao_plugin(body))
        if rota == "/api/sessoes":
            return self._json(self._acao_sessao(body))
        if rota == "/api/modelos":
            return self._json(self._acao_modelo(body))
        if rota == "/api/usage":
            if str(body.get("acao") or "") == "limpar":
                from . import usage

                return self._json({"ok": True, "msg": usage.limpar(), "resumo": self._uso(30)})
            return self._json(self._uso(30))
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
                "max_rounds": int(env("MAX_ROUNDS", str(agent.MAX_ROUNDS_PADRAO)) or agent.MAX_ROUNDS_PADRAO),
                "tem_chave": bool(chave),
                # vislumbre: primeiros 6 e últimos 4 caracteres
                "chave_dica": (chave[:6] + "…" + chave[-4:]) if len(chave) > 12 else ("definida" if chave else ""),
                "origem": "ambiente" if (os.environ.get("SHARK_LLM_KEY") or os.environ.get("NH_LLM_KEY")) else ("arquivo" if cfg.get("llm_key") else ""),
            },
            "arquivo": str(CONFIG_FILE),
        }

    # ------------------------------------------------------------------ loja ---
    def _modelo_ativo_resumo(self) -> dict:
        """O modelo em uso agora, para a barra do chat mostrar de relance."""
        from . import models

        try:
            atual = models.ativo()
            if atual:
                info = models.nivel_info(atual.get("nivel"))
                return {
                    "do_catalogo": True, "id": atual.get("id"),
                    "apelido": atual.get("apelido"), "modelo": atual.get("modelo"),
                    "nivel": int(atual.get("nivel") or 2), "nivel_nome": info["nome"],
                    "nivel_emoji": info["emoji"], "url": atual.get("url"),
                    "tem_chave": models.tem_chave(atual),
                }
        except Exception:  # noqa: BLE001
            pass
        return {
            "do_catalogo": False, "id": "",
            "apelido": env("LLM_MODEL", agent.DEFAULT_MODEL).split("/")[-1],
            "modelo": env("LLM_MODEL", agent.DEFAULT_MODEL),
            "nivel": 2, "nivel_nome": "Global", "nivel_emoji": "⚙️",
            "url": env("LLM_URL", agent.DEFAULT_URL),
            "tem_chave": bool(env("LLM_KEY", "")),
        }

    def _modelos(self) -> dict:
        """Catálogo de modelos + o que está ativo agora."""
        from . import models

        atual = models.ativo()
        return {
            "modelos": models.listar(),
            "niveis": [{"nivel": n, **info} for n, info in models.NIVEIS.items()],
            "ativo": atual.get("id") if atual else "",
            "global": {
                "url": env("LLM_URL", agent.DEFAULT_URL),
                "modelo": env("LLM_MODEL", agent.DEFAULT_MODEL),
                "tem_chave": bool(env("LLM_KEY", "")),
            },
        }

    def _acao_modelo(self, body: dict) -> dict:
        """Salvar / remover / escolher / testar um modelo do catálogo."""
        from . import models

        acao = str(body.get("acao") or "")
        try:
            if acao == "salvar":
                m = models.salvar(body)
                return {"ok": True, "modelo": m,
                        "msg": f"✅ modelo '{m['apelido']}' salvo.", "lista": self._modelos()}
            if acao == "remover":
                msg = models.remover(str(body.get("id") or ""))
                return {"ok": msg.startswith("🗑️"), "msg": msg, "lista": self._modelos()}
            if acao == "ativar":
                msg = models.definir_ativo(str(body.get("id") or ""))
                return {"ok": msg.startswith("✅"), "msg": msg, "lista": self._modelos()}
            if acao == "testar":
                r = models.testar(str(body.get("id") or ""))
                return {"ok": bool(r.get("ok")), "teste": r,
                        "msg": r.get("veredito") or r.get("erro") or "teste concluído",
                        "lista": self._modelos()}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
        return {"ok": False, "erro": f"ação desconhecida: {acao}"}

    def _saude(self) -> dict:
        """Checagem de saúde: responde 'o que pode estar quebrado?' de uma vez.

        Não gasta token: a parte do provedor só testa se o endereço responde
        (conexão TCP). Quem quiser gastar de verdade usa o "Testar conexão".
        """
        import shutil
        import socket
        from urllib.parse import urlparse as _urlparse

        from .paths import HOME, has_cmd

        itens: list[dict] = []

        def item(nome: str, estado: str, detalhe: str, dica: str = "") -> None:
            itens.append({"nome": nome, "estado": estado, "detalhe": detalhe, "dica": dica})

        # 1. grava e lê um arquivo de verdade (o teste que mais pega problema)
        try:
            alvo = workspace() / ".shark-teste-escrita"
            alvo.write_text("ok", encoding="utf-8")
            lido = alvo.read_text(encoding="utf-8")
            alvo.unlink()
            if lido == "ok":
                item("Escrita de arquivo", "ok", f"grava e lê em {workspace()}")
            else:
                item("Escrita de arquivo", "aviso", "escreveu mas leu diferente")
        except Exception as exc:  # noqa: BLE001
            item("Escrita de arquivo", "erro", f"{type(exc).__name__}: {exc}",
                 "no Termux, rode 'termux-setup-storage' e confira se a pasta existe")

        # 2. espaço em disco
        try:
            uso = shutil.disk_usage(str(HOME))
            livre = uso.free / (1024 ** 3)
            pct = 100 * uso.used / uso.total
            if livre < 0.3:
                item("Espaço em disco", "erro", f"só {livre:.2f} GB livres ({pct:.0f}% usado)")
            elif livre < 1.5:
                item("Espaço em disco", "aviso", f"{livre:.1f} GB livres ({pct:.0f}% usado)")
            else:
                item("Espaço em disco", "ok", f"{livre:.1f} GB livres ({pct:.0f}% usado)")
        except Exception as exc:  # noqa: BLE001
            item("Espaço em disco", "aviso", str(exc))

        # 3. provedor de IA configurado
        url = env("LLM_URL", agent.DEFAULT_URL)
        modelo = env("LLM_MODEL", "")
        chave = env("LLM_KEY", "")
        if not url:
            item("Provedor de IA", "erro", "nenhum endereço configurado",
                 "escolha um provedor em Ajustes → Provedor de IA")
        else:
            host = _urlparse(url).hostname or ""
            local = host in ("localhost", "127.0.0.1")
            if not chave and not local:
                item("Provedor de IA", "aviso", f"{host} — sem chave configurada",
                     "cole a chave em Ajustes; sem ela o agente não roda")
            else:
                item("Provedor de IA", "ok", f"{host} · modelo {modelo or '(padrão)'}")

        # 4. o provedor responde? (só conexão, sem gastar token)
        if url:
            host = _urlparse(url).hostname or ""
            porta = _urlparse(url).port or (443 if url.startswith("https") else 80)
            if host:
                try:
                    with socket.create_connection((host, porta), timeout=6):
                        pass
                    item("Conexão com o provedor", "ok", f"{host}:{porta} respondeu")
                except Exception as exc:  # noqa: BLE001
                    item("Conexão com o provedor", "erro",
                         f"não consegui falar com {host}:{porta} ({type(exc).__name__})",
                         "confira a internet; no celular, teste abrir o site no navegador")

        # 5. git (as sessões aproveitam)
        if has_cmd("git"):
            item("Git", "ok", "instalado")
        else:
            item("Git", "aviso", "não encontrado", "instale com: pkg install git")

        # 6. plugins carregados
        try:
            total = len(self.reg.names())
            if total == 0:
                item("Ferramentas", "erro", "nenhuma ferramenta carregada")
            else:
                item("Ferramentas", "ok", f"{total} disponíveis · risco máx {self.max_risk}")
        except Exception as exc:  # noqa: BLE001
            item("Ferramentas", "aviso", str(exc))

        # 7. permissão do arquivo de config (tem chave dentro)
        try:
            if CONFIG_FILE.is_file():
                modo = CONFIG_FILE.stat().st_mode & 0o777
                if modo & 0o077:
                    item("Permissão da config", "aviso", f"modo {oct(modo)[2:]} (legível por outros)",
                         "o arquivo guarda a chave; o ideal é 600")
                else:
                    item("Permissão da config", "ok", f"modo {oct(modo)[2:]} (só o dono lê)")
            else:
                item("Permissão da config", "aviso", "ainda sem arquivo de config",
                     "configure um provedor para criar")
        except Exception as exc:  # noqa: BLE001
            item("Permissão da config", "aviso", str(exc))

        ruins = [i for i in itens if i["estado"] == "erro"]
        alertas = [i for i in itens if i["estado"] == "aviso"]
        if ruins:
            resumo = f"{len(ruins)} problema(s) para resolver"
        elif alertas:
            resumo = f"tudo essencial funcionando · {len(alertas)} aviso(s)"
        else:
            resumo = "tudo funcionando"
        return {"itens": itens, "resumo": resumo,
                "erros": len(ruins), "avisos": len(alertas)}

    def _sessoes(self) -> dict:
        """Lista as sessões (pastas de projeto) e o atalho do home do usuário."""
        from . import sessions
        from .paths import HOME

        try:
            itens = sessions.listar()
        except Exception as exc:  # noqa: BLE001
            return {"sessoes": [], "erro": f"{type(exc).__name__}: {exc}"}
        raiz = Path.home()
        return {
            "sessoes": itens,
            "inicio": str(raiz),
            "workspace_padrao": str(workspace()),
            "arquivo": str(sessions.SESSOES_FILE),
        }

    def _listar_pasta(self, pasta: str) -> dict:
        """Navegador de pastas simples: devolve subpastas de um caminho."""
        base = Path(unquote(pasta)).expanduser() if pasta else Path.home()
        if not base.is_dir():
            return {"erro": f"não é uma pasta: {base}", "pasta": str(base), "pastas": []}
        pastas = []
        try:
            for item in sorted(base.iterdir()):
                if item.name.startswith("."):
                    continue
                if item.is_dir():
                    pastas.append({"nome": item.name, "caminho": str(item)})
        except PermissionError:
            return {"erro": f"sem permissão para listar {base}", "pasta": str(base), "pastas": []}
        return {
            "pasta": str(base),
            "acima": str(base.parent) if base.parent != base else "",
            "pastas": pastas[:200],
            "tem_git": (base / ".git").is_dir(),
        }

    def _acao_sessao(self, body: dict) -> dict:
        """Cria, apaga, renomeia ou limpa o histórico de uma sessão."""
        from . import sessions

        acao = str(body.get("acao") or "")
        try:
            if acao == "criar":
                s = sessions.criar(str(body.get("nome") or ""), str(body.get("pasta") or ""),
                                   str(body.get("modelo") or ""))
                return {"ok": True, "msg": f"✅ sessão '{s['nome']}' criada em {s['pasta']}",
                        "sessao": s, "lista": self._sessoes()}
            if acao == "apagar":
                m = sessions.apagar(str(body.get("id") or ""))
                return {"ok": m.startswith("🗑️"), "msg": m, "lista": self._sessoes()}
            if acao == "renomear":
                m = sessions.renomear(str(body.get("id") or ""), str(body.get("nome") or ""))
                return {"ok": m.startswith("✅"), "msg": m, "lista": self._sessoes()}
            if acao == "limpar":
                m = sessions.limpar_historico(str(body.get("id") or ""))
                return {"ok": m.startswith("🧹"), "msg": m, "lista": self._sessoes()}
            if acao == "modelo":
                m = sessions.definir_modelo(str(body.get("id") or ""), str(body.get("modelo") or ""))
                return {"ok": m.startswith("✅"), "msg": m, "lista": self._sessoes()}
            if acao == "abrir":
                s = sessions.obter(str(body.get("id") or ""))
                if not s:
                    return {"ok": False, "erro": "sessão não encontrada."}
                return {
                    "ok": True,
                    "sessao": s,
                    "historico": s.get("historico") or [],
                    "arvore": sessions.arvore(s.get("pasta", "")),
                }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
        return {"ok": False, "erro": f"ação desconhecida: {acao}"}

    def _uso(self, dias: int = 30) -> dict:
        """Histórico de uso do modelo (tokens e custo estimado)."""
        from . import usage

        try:
            return usage.resumo(dias)
        except Exception as exc:  # noqa: BLE001
            return {"erro": f"{type(exc).__name__}: {exc}", "total": {}, "por_dia": [],
                    "modelos": [], "ferramentas": []}

    def _estado_plugins(self) -> dict:
        """Estado do marketplace: instalados, disponíveis e kits."""
        from . import market
        from .core import pasta_usuario

        try:
            instalados = market.instalados()
            disponiveis = market.disponiveis()
            kits = market.kits()
        except Exception as exc:  # noqa: BLE001
            return {"instalados": [], "catalogo": [], "kits": [],
                    "erro": f"{type(exc).__name__}: {exc}"}
        return {
            "instalados": instalados,
            "catalogo": disponiveis,
            "kits": kits,
            "pasta": str(pasta_usuario()),
        }

    def _acao_plugin(self, body: dict) -> dict:
        """Instala, remove, ativa, desativa ou instala um kit."""
        from . import market

        acao = str(body.get("acao") or "")
        pid = str(body.get("id") or "").strip()
        confiar = bool(body.get("confiar"))
        if not pid:
            return {"ok": False, "erro": "informe o id do plugin."}
        try:
            if acao == "instalar":
                msg = market.instalar(pid, confirmar_exec=confiar)
            elif acao == "remover":
                msg = market.remover(pid)
            elif acao == "ativar":
                msg = market.ativar(pid)
            elif acao == "desativar":
                msg = market.desativar(pid)
            elif acao == "kit":
                msg = market.instalar_kit(pid, confirmar_exec=confiar)
            else:
                return {"ok": False, "erro": f"ação desconhecida: {acao}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
        # as ferramentas mudaram: recarrega o registry para a interface refletir
        recarregar = acao in ("instalar", "remover", "ativar", "desativar", "kit")
        return {
            "ok": msg.startswith(("✅", "🗑️")),
            "msg": msg,
            "precisa_confiar": "⚠️" in msg and "--confiar" in msg,
            "estado": self._estado_plugins(),
            "ferramentas": len(load_plugins().names()) if recarregar else None,
        }

    def _salvar_config(self, body: dict) -> dict:
        """Grava provedor/modelo/chave no config.json (permissão 600)."""
        provider = str(body.get("provider") or "").strip()
        url = str(body.get("url") or "").strip()
        modelo = str(body.get("model") or "").strip()
        chave = body.get("api_key")
        risco = str(body.get("max_risk") or "").strip()
        rodadas = body.get("max_rounds")

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
        # quantas rodadas o agente pode gastar antes de ter que responder
        if rodadas not in (None, ""):
            try:
                n = int(rodadas)
            except (TypeError, ValueError):
                return {"ok": False, "erro": "rodadas precisa ser um número."}
            if not 2 <= n <= 60:
                return {"ok": False, "erro": "rodadas deve ficar entre 2 e 60."}
            campos["max_rounds"] = n
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
            "modelo_ativo": self._modelo_ativo_resumo(),
            "max_risk": self.max_risk,
            "tools": tools,
            "plugins": self._plugins_resumo(),
            "jobs": jobs,
            "audit": audit,
            "sysinfo": self.reg.dispatch("sysinfo_report", {}),
            "llm": {
                "url": env("LLM_URL", agent.DEFAULT_URL),
                "model": env("LLM_MODEL", agent.DEFAULT_MODEL),
                "configured": bool(env("LLM_KEY")),
            },
        }

    def _plugins_resumo(self) -> list[dict]:
        """Todos os plugins (embutidos + instalados) com o estado ligado/desligado."""
        from .core import manifestos

        fora = set(str(x) for x in (read_config().get("plugins_desativados") or []))
        por_plugin: dict[str, list[str]] = {}
        for t in self.reg.tools.values():
            por_plugin.setdefault(t.plugin or "", []).append(t.name)
        saida = []
        try:
            for m in manifestos():
                pid = str(m.get("id", ""))
                m = dict(m)
                m["ferramentas"] = sorted(por_plugin.get(pid, m.get("ferramentas", [])))
                m["ativo"] = pid not in fora
                saida.append(m)
        except Exception:  # noqa: BLE001
            pass
        return saida

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
    def _sse(self, evento: str, dados: dict) -> None:
        """Escreve um evento SSE e manda na hora (o cliente vê ao vivo)."""
        texto = f"event: {evento}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"
        self.wfile.write(texto.encode("utf-8"))
        self.wfile.flush()

    def _agente_stream(self, body: dict) -> None:
        """Igual ao /api/agent, mas transmite os passos e o texto AO VIVO (SSE).

        O agente roda numa thread e joga os eventos numa fila; esta thread só
        fica drenando a fila e escrevendo no socket. Assim o usuário vê cada
        ferramenta sendo chamada e a resposta sendo escrita, em vez de encarar
        um spinner por um minuto.
        """
        prompt = str(body.get("prompt") or "")
        sessao_id = str(body.get("sessao") or "")

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        fila: queue.Queue = queue.Queue()
        resultado: dict = {}

        def ao_vivo(evento: str, dados: dict) -> None:
            fila.put((evento, dados))

        def trabalhar() -> None:
            try:
                resultado.update(self._agente(prompt, sessao_id, ao_vivo=ao_vivo))
            except Exception as exc:  # noqa: BLE001
                ao_vivo("erro", {"mensagem": f"{type(exc).__name__}: {exc}"})
            finally:
                fila.put((None, None))

        threading.Thread(target=trabalhar, daemon=True).start()

        while True:
            evento, dados = fila.get()
            if evento is None:
                break
            try:
                self._sse(evento, dados)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return  # aba fechada / parou: o agente segue, mas ninguém escuta
        try:
            self._sse("fim", resultado)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _agente(self, prompt: str, sessao_id: str = "", ao_vivo=None) -> dict:
        """Roda o agente. Com `sessao_id`, trabalha na pasta daquela sessão."""
        if not prompt.strip():
            return {"answer": "pedido vazio", "steps": []}
        passos: list[dict] = []
        lock = threading.Lock()

        def on_step(tipo: str, nome: str, detalhe: str) -> None:
            with lock:
                passos.append({"tipo": tipo, "nome": nome, "detalhe": (detalhe or "")[:4000]})
            if ao_vivo is not None:
                ao_vivo("passo", {"tipo": tipo, "nome": nome, "detalhe": (detalhe or "")[:4000]})

        def on_texto(pedaco: str) -> None:
            if ao_vivo is not None:
                ao_vivo("delta", {"texto": pedaco})

        pasta, historico, sessao = "", None, None
        if sessao_id:
            from . import sessions

            sessao = sessions.obter(sessao_id)
            if sessao is None:
                return {"answer": "❌ sessão não encontrada.", "steps": []}
            pasta = str(sessao.get("pasta") or "")
            # histórico só de texto (user/assistant): dá continuidade sem inchar
            historico = [
                {"role": m.get("role"), "content": m.get("content")}
                for m in (sessao.get("historico") or [])
                if m.get("role") in ("user", "assistant") and m.get("content")
            ]

        # qual modelo usar: o escolhido no catálogo manda; sem catálogo, o global
        from . import models

        global_ = {"llm_url": env("LLM_URL", agent.DEFAULT_URL),
                   "llm_model": env("LLM_MODEL", agent.DEFAULT_MODEL),
                   "llm_key": env("LLM_KEY", "")}
        entrada = models.ativo()
        escolhido = models.resolver(entrada, global_)
        usar = escolhido or global_
        fila_reserva = models.reservas() if escolhido else []

        resposta = agent.run_agent(
            prompt,
            reg=self.reg,
            max_risk=self.max_risk,
            verbose=False,
            on_step=on_step,
            history=historico,
            pasta=pasta,
            on_texto=on_texto if ao_vivo is not None else None,
            url=str(usar.get("url") or ""),
            model=str(usar.get("modelo") or ""),
            api_key=str(usar.get("chave") or ""),
            reservas=fila_reserva,
        )

        if sessao is not None:
            from . import sessions

            novo = list(historico or []) + [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": resposta},
            ]
            sessions.guardar_historico(sessao_id, novo)

        return {
            "answer": resposta,
            "steps": passos,
            "sessao": {"id": sessao_id, "nome": sessao.get("nome"), "pasta": pasta} if sessao else None,
        }


def _ja_tem_harness(host: str, port: int) -> bool:
    """Diz se quem está ocupando a porta é outro Shark Harness (e não outro programa).

    Olha a página inicial: se vier a marca do harness, é nosso — o usuário só
    esqueceu uma janela aberta.
    """
    import urllib.error
    import urllib.request

    alvo = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}/"
    try:
        with urllib.request.urlopen(alvo, timeout=3) as resp:
            if "SharkHarness" in str(resp.headers.get("Server", "")):
                return True
            amostra = resp.read(4000).decode("utf-8", "replace")
            return "Shark Harness" in amostra or "shark-harness" in amostra
    except Exception:  # noqa: BLE001 — qualquer coisa = não é nosso
        return False


def _achar_porta_livre(host: str, inicio: int, tentativas: int = 12) -> int | None:
    """Procura a próxima porta livre a partir de `inicio`."""
    import socket

    for p in range(inicio + 1, inicio + 1 + tentativas):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue
    return None


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

    try:
        httpd = ThreadingHTTPServer((host, port), Handler)
    except OSError as exc:
        # porta ocupada (Errno 98 no Linux/Termux, 48 no macOS): nada de traceback
        if exc.errno not in (48, 98, 10048):
            raise
        if _ja_tem_harness(host, port):
            print(f"\n⚠️  Já tem um Shark Harness rodando em http://{host}:{port}/\n")
            print("   Você deixou uma janela antiga aberta. Ela continua no ar com o")
            print("   código VELHO — se você acabou de dar `git pull`, o certo é parar")
            print("   ela e subir de novo:\n")
            print("       pkill -f 'nh web'")
            print(f"       {'./.venv/bin/' if (Path.cwd() / '.venv' / 'bin').is_dir() else ''}nh web\n")
            print(f"   (se preferir, a janela antiga serve — mas com a versão anterior)")
            print(f"   (ou suba em outra porta: nh web --port {port + 1})\n")
            return 1
        nova = _achar_porta_livre(host, port)
        if nova is None:
            print(f"\n❌ A porta {port} está ocupada e não achei nenhuma livre perto.\n")
            print("   Veja quem está usando:")
            print(f"     python -c \"import socket;s=socket.socket();"
                  f"print(s.connect_ex(('{host}',{port})))\"")
            print(f"   Ou escolha outra porta na mão: nh web --port {port + 50}\n")
            return 1
        print(f"⚠️  A porta {port} estava ocupada — subi na {nova}.")
        print(f"    (para usar a {port}, pare o processo antigo: pkill -f 'nh web')")
        port = nova
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
