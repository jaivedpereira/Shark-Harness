"""CLI do Shark Harness — a frente de linha de comando.

    nh run "cria um script python que soma 1..100 e roda"
    nh do run_shell --args '{"command": "ls -la"}'
    nh tools
    nh cron add --name backup --cron "0 3 * * *" --cmd "tar -czf ~/bkp.tgz ~/projetos"
    nh cron daemon
    nh web            # interface azul/preto com o tubarão
    nh info
    nh serve          # servidor MCP em stdio
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__, agent, mcp_server, scheduler
from .core import Registry, load_plugins
from .guard import AUDIT_FILE
from .paths import HOME, WORKSPACE, ensure_dirs, env, platform_name

RISKS = ("safe", "write", "exec", "danger")

# O default do --risk vem do ambiente/.env — senão o argparse sempre venceria o
# SHARK_MAX_RISK definido no .env.
RISCO_PADRAO = env("MAX_RISK", "exec")
if RISCO_PADRAO not in RISKS:
    RISCO_PADRAO = "exec"


def _colors() -> dict[str, str]:
    if not sys.stdout.isatty():
        return dict.fromkeys(("b", "d", "g", "y", "r", "c"), "")
    return {
        "b": "\033[1m", "d": "\033[2m", "g": "\033[32m",
        "y": "\033[33m", "r": "\033[31m", "c": "\033[36m",
    }


C = _colors()


SHARK = r"""
                    ▄▄▄▄▄
                  ▄███████▄
                 ▄█████████▄
        ▄▄▄▄▄▄▄▄████████████████▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄     ▄▄▄▄
     ▄████████████████████████████████████████████▄▄█████▄
   ▄██████████████████████████████████████████████████████▀
  ▀▀████████████████████████████████████████████████████▀
      ▀▀▀█████████████████████████████████████████▀▀
           ▀▀▀▀▀█████████████████████████▀▀▀
"""


def _banner() -> str:
    return (
        f"{C['c']}{SHARK}{C['d']}"
        f"  {C['b']}SHARK HARNESS{C['d']} v{__version__}  ·  agente tudo-é-plugin "
        f"({platform_name()})\n"
        f"   {C['d']}agente:{C['d']} nh run \"...\"    "
        f"{C['d']}interface:{C['d']} nh web    "
        f"{C['d']}ferramentas:{C['d']} nh tools    "
        f"{C['d']}jobs:{C['d']} nh cron list\n"
        f"   {C['d']}casa: {HOME}   ·   workspace: {WORKSPACE}{C['d']}"
    )


def _load() -> Registry:
    ensure_dirs()
    return load_plugins()


# ------------------------------------------------------------------- comandos ---


def cmd_run(args: argparse.Namespace) -> int:
    reg = _load()
    texto = " ".join(args.prompt).strip()
    if not texto:
        return _fail('informe o pedido: nh run "faça tal coisa"')
    hist: list = []
    if args.verbose:
        print(_banner())
    out = agent.run_agent(
        texto,
        reg=reg,
        max_risk=args.risk,
        verbose=args.verbose,
        history=hist,
    )
    print("\n" + out)
    return 0


def cmd_do(args: argparse.Namespace) -> int:
    reg = _load()
    try:
        payload = json.loads(args.args) if args.args.strip() else {}
    except json.JSONDecodeError as exc:
        return _fail(f"--args precisa ser JSON válido: {exc}")
    if not isinstance(payload, dict):
        return _fail("--args precisa ser um objeto JSON, ex.: '{\"command\": \"ls\"}'")
    tool = reg.get(args.tool)
    if tool is None:
        return _fail(f"ferramenta '{args.tool}' não existe. Veja: nh tools")
    if not args.force and tool.risk in ("exec", "danger"):
        print(f"{C['y']}⚠️  '{tool.name}' tem risco '{tool.risk}' — vai executar de verdade.{C['d']}")
    print(reg.dispatch(args.tool, payload))
    return 0


def cmd_tools(args: argparse.Namespace) -> int:
    reg = _load()
    icons = {"safe": "🟢", "write": "🟡", "exec": "🟠", "danger": "🔴"}
    for t in reg.subset(max_risk=args.risk):
        if args.filter and args.filter.lower() not in (t.name + t.description).lower():
            continue
        print(f"{icons.get(t.risk, '⚪')} {C['b']}{t.name}{C['d']} [{t.plugin}]{C['d']}")
        print(f"     {t.description}")
        params = t.schema.get("properties", {})
        if params:
            req = set(t.schema.get("required", []))
            for pname, spec in params.items():
                mark = "*" if pname in req else " "
                print(f"     {C['d']}{mark}{pname}: {spec.get('type', 'string')}{C['d']}"
                      + (f" — {spec['description']}" if spec.get("description") else ""))
    return 0


def cmd_cron(args: argparse.Namespace) -> int:
    reg = _load()
    act = args.action

    if act == "list":
        print(reg.dispatch("list_tasks"))
        return 0

    if act == "add":
        if not args.name or not args.cron or not (args.cmd or args.tool):
            return _fail('use: nh cron add --name X --cron "*/30 * * * *" --cmd "comando"')
        print(reg.dispatch("schedule_task", {
            "nome": args.name,
            "cron": args.cron,
            "comando": args.cmd or "",
            "ferramenta": args.tool or "",
            "args_json": args.args or "",
        }))
        return 0

    if act in ("rm", "remove"):
        print(reg.dispatch("remove_task", {"id_ou_nome": args.id}))
        return 0

    if act in ("pause", "toggle"):
        print(reg.dispatch("pause_task", {"id_ou_nome": args.id}))
        return 0

    if act == "run":
        print(reg.dispatch("run_task_now", {"id_ou_nome": args.id}))
        return 0

    if act == "explain":
        print(reg.dispatch("explain_cron", {"expressao": args.cron or ""}))
        return 0

    if act == "daemon":
        try:
            scheduler.daemon(reg, interval=args.interval, quiet=False)
        except KeyboardInterrupt:
            pass
        return 0

    return _fail(f"ação desconhecida: {act}")


def cmd_info(args: argparse.Namespace) -> int:
    reg = _load()
    print(reg.dispatch("sysinfo_report"))
    print()
    print(f"🧰 {len(reg.names())} ferramentas carregadas · risco máx exposto ao LLM: {args.risk}")
    print(f"📂 jobs: {len(scheduler.load_jobs())} agendado(s) · log: {AUDIT_FILE}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    reg = _load()
    print(reg.dispatch("audit_tail", {"linhas": args.lines}))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Diagnóstico: testa escrita de arquivo de verdade e aponta o que corrigir."""
    reg = _load()
    print(reg.dispatch("diagnostico"))
    return 0


def cmd_atualizar(args: argparse.Namespace) -> int:
    """Baixa a versão nova do projeto pelo git, sem perder config nem plugins.

    Faz `git pull --ff-only` na pasta do próprio projeto. Só atualiza código: a sua
    chave, o catálogo de modelos e as sessões vivem em ~/.shark-harness/ (fora daqui),
    e os plugins que você instalou ficam em ~/.shark-harness/plugins/.
    """
    import shutil
    import subprocess
    from pathlib import Path

    from .paths import HOME

    raiz = Path(__file__).resolve().parent.parent
    print(f"🦈 Shark Harness — atualizando {raiz}\n")

    if not shutil.which("git"):
        print("❌ Git não está instalado. Instale e tente de novo:")
        print("     Termux/Linux :  pkg install git")
        print("     Windows      :  winget install Git.Git   (depois reabra o terminal)")
        return 1

    if not (raiz / ".git").is_dir():
        print("❌ Essa pasta não foi clonada com git (não tem .git), então não dá para")
        print("   baixar atualização por aqui. Duas saídas:")
        print("     • baixar o ZIP novo e reinstalar, ou")
        print("     • clonar de uma vez e nunca mais se preocupar:")
        print("         git clone https://github.com/jaivedpereira/Shark-Harness.git")
        print("         cd Shark-Harness")
        print("         ./install.sh        (Linux/Termux)   ou   .\\install.ps1  (Windows)")
        return 1

    # mostra de onde para onde vai
    def git(*comandos: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *comandos], cwd=raiz, capture_output=True, text=True)

    antes = git("rev-parse", "--short", "HEAD").stdout.strip()
    ramo = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "main"

    sujo = git("status", "--porcelain").stdout.strip()
    if sujo:
        print("⚠️  Você tem alterações locais no projeto:")
        for linha in sujo.splitlines()[:8]:
            print(f"     {linha}")
        print("\n   Para descartar e atualizar mesmo assim:")
        print("     git checkout .")
        print("     nh atualizar\n")
        return 1

    print(f"   versão atual: {antes} (ramo {ramo})")
    print("   baixando…\n")
    r = git("pull", "--ff-only")
    saida = (r.stdout + r.stderr).strip()
    for linha in saida.splitlines()[-14:]:
        print(f"   {linha}")

    if r.returncode != 0:
        print("\n❌ O git não conseguiu atualizar. Motivos comuns:")
        print("     • sem internet no momento")
        print("     • o histórico local divergiu (git checkout . e tente de novo)")
        print("     • você mexeu no projeto à mão sem commitar")
        return 1

    depois = git("rev-parse", "--short", "HEAD").stdout.strip()
    print()
    if depois == antes:
        print("✅ Já estava na versão mais nova — nada para atualizar.")
    else:
        print(f"✅ Atualizado: {antes} → {depois}\n")
        nomes = git("diff", "--stat", antes, depois).stdout.strip()
        if nomes:
            print("   o que mudou:")
            for linha in nomes.splitlines()[-10:]:
                print(f"     {linha.strip()}")

    print("\n👉 Agora é só rodar de novo:  nh web")
    print("   (a interface antiga, se estiver aberta, continua com o código VELHO)")
    print(f"   sua chave e seu catálogo ficam em {HOME} — nada disso se perde")
    return 0


def cmd_modelo(args: argparse.Namespace) -> int:
    """Catálogo de modelos: listar, adicionar, escolher, testar e remover."""
    from . import models

    acao = getattr(args, "acao_modelo", "listar")

    if acao == "listar":
        itens = models.listar()
        ativo = models.ativo()
        if not itens:
            print("nenhum modelo no catálogo — o chat usa o modelo global do config.\n")
            print("adicione com:")
            print("  nh modelo add --apelido 'Nemotron grátis' --nivel 1 \\")
            print("      --url https://openrouter.ai/api/v1/chat/completions \\")
            print("      --modelo nvidia/nemotron-3.5-lightning:free")
            return 0
        print(f"🧠 {len(itens)} modelo(s) no catálogo:\n")
        for m in itens:
            marca = " ← em uso" if ativo and ativo.get("id") == m["id"] else ""
            chave = "com chave" if m["tem_chave"] else "⚠️ SEM CHAVE"
            print(f"  {m['nivel_emoji']} {m['id']}  {m['apelido']}{marca}")
            print(f"      {m['modelo']}")
            print(f"      {m['url']}  ·  nível {m['nivel_nome']}  ·  {chave}")
            if m.get("nota"):
                print(f"      📝 {m['nota']}")
            print()
        if not ativo:
            print("nenhum escolhido — o chat está usando o modelo global (nh config).")
        return 0

    if acao == "add":
        try:
            m = models.salvar({
                "apelido": args.apelido, "url": args.url, "modelo": args.modelo,
                "nivel": args.nivel, "nota": args.nota or "", "chave": args.chave or "",
            })
        except ValueError as exc:
            print(f"❌ {exc}")
            return 1
        print(f"✅ '{m['apelido']}' salvo no catálogo (nível {models.nivel_info(m['nivel'])['nome']}).")
        print(f"   para usar: nh modelo usar {m['id']}")
        return 0

    if acao == "usar":
        msg = models.definir_ativo(args.id or "")
        print(msg)
        return 0 if msg.startswith("✅") else 1

    if acao == "remover":
        msg = models.remover(args.id or "")
        print(msg)
        return 0 if msg.startswith("🗑️") else 1

    if acao == "testar":
        alvo = args.id or (models.ativo() or {}).get("id") or ""
        if not alvo:
            print("❌ informe o id: nh modelo testar <id>")
            return 1
        m = models.obter(alvo)
        print(f"⏳ testando '{m.get('apelido') if m else alvo}' "
              f"(3 perguntas simples, pode levar até ~100s)...\n")
        r = models.testar(alvo)
        if not r.get("ok"):
            print(f"❌ {r.get('erro')}")
            return 1
        print(f"  {r['veredito']}")
        print(f"  {r['acertos']}/{r['total']} · média {r['media_segundos']}s · "
              f"total {r.get('segundos_total')}s\n")
        for d in r.get("detalhes") or []:
            print(f"  {'✓' if d['ok'] else '✗'} {d['segundos']:>6}s  {d['resposta'][:90]}")
            if not d["ok"] and d.get("motivo"):
                print(f"              ↳ {d['motivo']}")
        return 0

    print(f"❌ ação desconhecida: {acao}")
    return 1


def cmd_uso(args: argparse.Namespace) -> int:
    """Uso do modelo: tokens consumidos e custo estimado."""
    from . import usage

    if getattr(args, "limpar", False):
        print(usage.limpar())
        return 0
    reg = _load()
    print(reg.dispatch("uso_do_modelo", {"dias": args.dias}))
    return 0


def cmd_plugin(args: argparse.Namespace) -> int:
    """Marketplace: catálogo, instalar, ativar/desativar e kits."""
    from . import market

    acao = args.action

    if acao == "catalogo":
        itens = market.disponiveis()
        if not itens:
            print("📦 catálogo vazio (ou tudo já instalado). Veja com: nh plugin listar")
            return 0
        print(f"📦 {len(itens)} plugin(s) disponíveis no catálogo:\n")
        for p in itens:
            risco = p.get("risco_max", "safe")
            marca = {"safe": "🟢", "write": "🟡", "exec": "🟠", "danger": "🔴"}.get(risco, "⚪")
            print(f"  {marca} {p['id']:10} {p['nome']} — v{p.get('versao', '?')}")
            print(f"     {p.get('descricao', '')}")
            print(f"     {len(p.get('ferramentas', []))} ferramentas · risco {risco} · "
                  f"categoria {p.get('categoria', '—')}")
            if p.get("requer"):
                print(f"     precisa de: {', '.join(p['requer'])}")
            print()
        print("Instale com:  nh plugin instalar <id>")
        return 0

    if acao == "listar":
        from .core import manifestos
        from .paths import read_config

        todos = manifestos()
        desativados = set(str(x) for x in (read_config().get("plugins_desativados") or []))
        if not todos:
            print("nenhum plugin encontrado.")
            return 0
        print(f"🧩 {len(todos)} plugin(s):\n")
        for m in todos:
            pid = m.get("id", "?")
            estado = "⏸️  desativado" if pid in desativados else "✅ ativo"
            if m.get("quebrado"):
                estado = "❌ quebrado"
            origem = m.get("origem", "?")
            print(f"  {estado:14} {pid:10} {m.get('nome', pid):20} [{origem}] "
                  f"risco {m.get('risco_max', '—')}")
            if m.get("descricao"):
                print(f"      {m['descricao']}")
        print("\nVer um só:       nh plugin info <id>")
        print("Ligar/desligar:  nh plugin ativar|desativar <id>")
        return 0

    if acao == "procurar":
        termo = (args.id or "").lower()
        if not termo:
            print("uso: nh plugin procurar <termo>")
            return 1
        achados = []
        for p in market.catalogo().get("plugins", []):
            alvo = " ".join([p.get("id", ""), p.get("nome", ""), p.get("descricao", ""),
                             " ".join(p.get("tags", [])), p.get("categoria", "")]).lower()
            if termo in alvo:
                achados.append((p, False))
        tenho = {m.get("id") for m in market.instalados()}
        for m in market.instalados():
            alvo = f"{m.get('id','')} {m.get('nome','')} {m.get('descricao','')}".lower()
            if termo in alvo:
                achados.append((m, True))
        if not achados:
            print(f"🔍 nada encontrado para '{termo}'.")
            return 0
        for p, instalado in achados:
            estado = " (já instalado)" if instalado else ""
            print(f"  {p.get('id'):10} {p.get('nome')}{estado}\n      {p.get('descricao', '')}")
        return 0

    if acao == "info":
        pid = args.id
        for m in market.instalados():
            if m.get("id") == pid:
                return _mostrar_info(m, "instalado")
        item = next((p for p in market.catalogo().get("plugins", []) if p.get("id") == pid), None)
        if item is None:
            from .core import manifestos

            for m in manifestos():
                if m.get("id") == pid:
                    return _mostrar_info(m, m.get("origem", "embutido"))
            print(f"❌ '{pid}' não existe (nem instalado, nem no catálogo).")
            return 1
        return _mostrar_info(item, "catálogo")

    if acao == "instalar":
        print(market.instalar(args.id, confirmar_exec=args.confiar))
        return 0

    if acao == "remover":
        print(market.remover(args.id))
        return 0

    if acao in ("ativar", "desativar"):
        print(market.ativar(args.id) if acao == "ativar" else market.desativar(args.id))
        return 0

    if acao == "kits":
        ks = market.kits()
        if not ks:
            print("nenhum kit no catálogo.")
            return 0
        print(f"📦 {len(ks)} kit(s) prontos:\n")
        for k in ks:
            print(f"  {k['id']:10} {k['nome']} — {k.get('descricao', '')}")
            print(f"     plugins: {', '.join(k.get('plugins', []))}")
        print("\nInstale com:  nh plugin kit <id>")
        return 0

    if acao == "kit":
        print(market.instalar_kit(args.id, confirmar_exec=args.confiar))
        return 0

    print(f"ação desconhecida: {acao}")
    return 1


def _mostrar_info(m: dict, origem: str) -> int:
    print(f"🧩 {m.get('nome', m.get('id'))}  (id: {m.get('id')})")
    print(f"   {m.get('descricao', '—')}")
    print(f"   versão.....: {m.get('versao', '—')}")
    print(f"   autor......: {m.get('autor', '—')}")
    print(f"   categoria..: {m.get('categoria', '—')}")
    print(f"   origem.....: {origem}")
    print(f"   risco máx..: {m.get('risco_max', '—')}")
    if m.get("requer"):
        print(f"   precisa de.: {', '.join(m['requer'])}")
    if m.get("plataformas"):
        print(f"   plataformas: {', '.join(m['plataformas'])}")
    if m.get("ferramentas"):
        print(f"   ferramentas: {', '.join(m['ferramentas'])}")
    if m.get("arquivo"):
        print(f"   arquivo....: {m['arquivo']}")
    if m.get("sha256"):
        print(f"   sha256.....: {m['sha256'][:32]}…")
    if m.get("tags"):
        print(f"   tags.......: {', '.join(m['tags'])}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    argv = []
    if args.list:
        argv.append("--list")
    if args.selftest:
        argv.append("--selftest")
    return mcp_server.main(argv)


def cmd_web(args: argparse.Namespace) -> int:
    from .web import serve

    if args.all:
        print(
            f"{C['y']}⚠️  expondo na rede local — a interface exige o token que vou imprimir.{C['d']}"
        )
    return serve(
        host=args.host if args.host else ("0.0.0.0" if args.all else "127.0.0.1"),
        port=args.port,
        max_risk=args.risk,
        open_browser=not args.no_open,
    )


def _fail(msg: str) -> int:
    print(f"{C['r']}✖ {msg}{C['d']}")
    return 2


# ---------------------------------------------------------------------- parser ---


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nh",
        description="🦈 Shark Harness — agente de tarefas com arquitetura tudo-é-plugin.",
        epilog='exemplo: nh run "checa o sysinfo e cria um backup do workspace"',
    )
    p.add_argument("--version", action="version", version=f"Shark Harness {__version__}")
    sub = p.add_subparsers(dest="cmd")

    r = sub.add_parser("run", help="pede algo ao agente (LLM + ferramentas)")
    r.add_argument("prompt", nargs="+")
    r.add_argument("--risk", choices=RISKS, default=RISCO_PADRAO, help="risco máximo exposto ao LLM")
    r.add_argument("--quiet", dest="verbose", action="store_false", help="só a resposta final")
    r.set_defaults(func=cmd_run)

    d = sub.add_parser("do", help="chama uma ferramenta direto, sem LLM")
    d.add_argument("tool")
    d.add_argument("--args", default="", help="JSON com os argumentos")
    d.add_argument("--force", action="store_true", help="não avisar sobre risco")
    d.set_defaults(func=cmd_do)

    t = sub.add_parser("tools", help="lista as ferramentas")
    t.add_argument("--filter", default="")
    t.add_argument("--risk", choices=RISKS, default="danger")
    t.set_defaults(func=cmd_tools)

    c = sub.add_parser("cron", help="tarefas agendadas")
    c.add_argument("action", choices=["list", "add", "rm", "pause", "run", "explain", "daemon"])
    c.add_argument("--name", default="")
    c.add_argument("--cron", default="", help='ex.: "*/30 * * * *"')
    c.add_argument("--cmd", default="", help="comando de shell do job")
    c.add_argument("--tool", default="", help="nome de ferramenta do harness")
    c.add_argument("--args", default="", help="JSON de args da ferramenta")
    c.add_argument("--id", default="", help="id ou nome do job")
    c.add_argument("--interval", type=int, default=20, help="tick do daemon em segundos")
    c.set_defaults(func=cmd_cron)

    i = sub.add_parser("info", help="estado do harness e do dispositivo")
    i.add_argument("--risk", choices=RISKS, default=RISCO_PADRAO)
    i.set_defaults(func=cmd_info)

    a = sub.add_parser("audit", help="últimas ações executadas")
    a.add_argument("lines", nargs="?", type=int, default=20)
    a.set_defaults(func=cmd_audit)

    d2 = sub.add_parser("doctor", help="diagnóstico do ambiente (testa escrita de arquivo de verdade)")
    d2.set_defaults(func=cmd_doctor)

    at = sub.add_parser("atualizar", aliases=["update"],
                        help="baixa a versão nova pelo git (não perde config, chave nem plugins)")
    at.set_defaults(func=cmd_atualizar)

    # nh modelo — catálogo de modelos (vários endpoints e níveis)
    mo = sub.add_parser("modelo", help="catálogo de modelos: listar, adicionar, escolher, testar")
    mo.set_defaults(func=cmd_modelo)
    mo_sub = mo.add_subparsers(dest="acao_modelo")
    mo_sub.add_parser("listar", help="mostra o catálogo")
    mo_add = mo_sub.add_parser("add", help="cadastra um modelo")
    mo_add.add_argument("--apelido", required=True, help="nome que aparece na interface")
    mo_add.add_argument("--url", required=True, help="endpoint completo do provedor")
    mo_add.add_argument("--modelo", required=True, help="id do modelo naquele provedor")
    mo_add.add_argument("--nivel", type=int, default=2, choices=[1, 2, 3],
                        help="1 rápido · 2 equilibrado · 3 potente")
    mo_add.add_argument("--chave", default="", help="opcional; vazio usa a chave global")
    mo_add.add_argument("--nota", default="", help="observação livre")
    mo_usar = mo_sub.add_parser("usar", help="escolhe o modelo do chat (vazio = global)")
    mo_usar.add_argument("id", nargs="?", default="")
    mo_rm = mo_sub.add_parser("remover", help="tira do catálogo")
    mo_rm.add_argument("id")
    mo_t = mo_sub.add_parser("testar", help="roda 3 perguntas e mede acerto e velocidade")
    mo_t.add_argument("id", nargs="?", default="")

    u = sub.add_parser("uso", help="uso do modelo: tokens e custo estimado")
    u.add_argument("dias", nargs="?", type=int, default=30, help="janela em dias (padrão 30)")
    u.add_argument("--limpar", action="store_true", help="apaga o histórico de uso")
    u.set_defaults(func=cmd_uso)

    pl = sub.add_parser("plugin", help="marketplace: catálogo, instalar, ativar/desativar, kits")
    pl.add_argument("action", choices=["catalogo", "listar", "procurar", "info", "instalar",
                                       "remover", "ativar", "desativar", "kits", "kit"])
    pl.add_argument("id", nargs="?", default="", help="id do plugin (ou termo, em 'procurar')")
    pl.add_argument("--confiar", action="store_true",
                    help="autoriza plugin que executa comando (risco exec/danger)")
    pl.set_defaults(func=cmd_plugin)

    s = sub.add_parser("serve", help="servidor MCP em stdio")
    s.add_argument("--list", action="store_true")
    s.add_argument("--selftest", action="store_true")
    s.set_defaults(func=cmd_serve)

    w = sub.add_parser("web", help="interface web (azul/preto com o tubarão)")
    w.add_argument("--port", type=int, default=8787)
    w.add_argument("--host", default="", help="IP para escutar (default 127.0.0.1)")
    w.add_argument("--all", action="store_true", help="escuta em 0.0.0.0 (exige token)")
    w.add_argument("--risk", choices=RISKS, default=RISCO_PADRAO)
    w.add_argument("--no-open", action="store_true", help="não abrir o navegador")
    w.set_defaults(func=cmd_web)

    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "func", None):
        print(_banner())
        print()
        parser.print_help()
        return 0

    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print("\n⏹️  interrompido")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
