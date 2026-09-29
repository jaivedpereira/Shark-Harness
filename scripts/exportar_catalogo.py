"""Exporta o catálogo real de ferramentas do Shark Harness para JSON.

Usado para gerar o PDF — assim o documento sai da fonte de verdade (o registry),
não de uma lista escrita à mão que envelhece.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nh.core import load_plugins  # noqa: E402
from nh.paths import WORKSPACE, HOME, platform_name  # noqa: E402

# descrição "para que serve" em linguagem de gente, por plugin
PROPOSITO = {
    "shell": ("Terminal do dispositivo", "Rodar comandos no PC, Linux ou Termux — instalar pacote, usar git, mover arquivo, chamar qualquer programa."),
    "code": ("Programar e testar", "Escrever e executar Python/Node na hora, sem criar arquivo na mão. É o que faz o harness 'saber programar'."),
    "files": ("Arquivos de verdade", "Ler, escrever, listar, procurar por nome e procurar DENTRO dos arquivos, criar pasta e apagar."),
    "net": ("Internet e APIs", "Consultar APIs, baixar arquivo, testar se um serviço está no ar, ver o IP, buscar CEP e previsão do tempo."),
    "archive": ("Backup e integridade", "Compactar em zip/tar.gz, extrair, conferir o hash de um download e descobrir o que está ocupando espaço."),
    "proc": ("Processos e serviços", "Ver o que está rodando, ver os processos do próprio harness e encerrar o que travou."),
    "schedule": ("Tarefas agendadas", "Criar tarefas que rodam sozinhas no horário definido (cron), listar, pausar, rodar agora e remover."),
    "device": ("Controle do aparelho", "Notificação, print de tela, área de transferência e abrir link/app — no celular (Termux:API) ou no PC."),
    "doctor": ("Diagnóstico", "Testar se a escrita de arquivo funciona e checar o ambiente inteiro, apontando o que corrigir."),
    "sysinfo": ("Saúde do sistema", "RAM, disco, bateria, uptime, relógio — para saber se cabe tarefa pesada."),
    "meta": ("Auto-conhecimento", "Listar as ferramentas, ver os parâmetros de uma e ler o histórico de auditoria."),
}

RISCO_TXT = {
    "safe": "Só leitura",
    "write": "Escreve",
    "exec": "Executa",
    "danger": "Apaga/perigoso",
}

reg = load_plugins()
tools = []
for nome in reg.names():
    t = reg.get(nome)
    props = t.schema.get("properties", {})
    req = set(t.schema.get("required", []))
    tools.append({
        "nome": t.name,
        "plugin": t.plugin or "core",
        "risco": t.risk,
        "risco_txt": RISCO_TXT.get(t.risk, t.risk),
        "descricao": t.description,
        "params": [
            {
                "nome": p,
                "tipo": spec.get("type", "string"),
                "obrigatorio": p in req,
                "desc": spec.get("description", ""),
            }
            for p, spec in props.items()
        ],
    })

plugins = {}
for t in tools:
    plugins.setdefault(t["plugin"], {"nome": t["plugin"], "qtd": 0, "riscos": {}})
    plugins[t["plugin"]]["qtd"] += 1
    plugins[t["plugin"]]["riscos"][t["risco"]] = plugins[t["plugin"]]["riscos"].get(t["risco"], 0) + 1

for pid, info in plugins.items():
    titulo, porque = PROPOSITO.get(pid, (pid, ""))
    info["titulo"] = titulo
    info["proposito"] = porque

dados = {
    "total_ferramentas": len(tools),
    "total_plugins": len(plugins),
    "plataforma": platform_name(),
    "workspace": str(WORKSPACE),
    "home": str(HOME),
    "tools": tools,
    "plugins": list(plugins.values()),
}

destino = RAIZ / "catalogo_tools.json"
destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"✅ {len(tools)} ferramentas em {len(plugins)} plugins → {destino}")
for p in sorted(plugins.values(), key=lambda x: -x["qtd"]):
    print(f"   {p['nome']:10} {p['qtd']:2}  {p['titulo']}")
