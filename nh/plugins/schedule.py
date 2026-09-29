"""Plugin: agendamento — tarefas recorrentes que rodam sozinhas.

É o coração do "realizar tarefas agendadas para o usuário". O agente cria o job,
o daemon (`nh cron daemon`) executa no horário e o resultado entra no histórico.

kind="shell" → payload é um comando (ex.: backup, git pull, checar site)
kind="tool"  → payload é o NOME de uma ferramenta do harness + args em JSON
"""

from __future__ import annotations

import json

from .. import scheduler
from ..core import Registry


def schedule_task(nome: str, cron: str, comando: str = "", ferramenta: str = "", args_json: str = "") -> str:
    """Agenda uma tarefa recorrente (estilo cron) que o harness vai executar sozinho.

    Args:
        nome: nome curto e descritivo da tarefa.
        cron: 5 campos: 'minuto hora dia mês dia-semana'. Ex.: '*/30 * * * *' (a cada 30 min), '0 7 * * 1-5' (07:00 de seg a sex), '0 21 * * *' (21:00 todo dia).
        comando: comando de shell a rodar (para tarefas comuns). Deixe vazio se usar 'ferramenta'.
        ferramenta: nome de uma ferramenta do harness a chamar (ex.: 'sysinfo_report').
        args_json: JSON com os argumentos da ferramenta, ex.: '{"x": 1}'.
    """
    if bool(comando) == bool(ferramenta):
        return "ERRO: informe EXATAMENTE um dos dois — 'comando' (shell) ou 'ferramenta' (do harness)."

    args: dict = {}
    if args_json.strip():
        try:
            args = json.loads(args_json)
        except json.JSONDecodeError as exc:
            return f"ERRO: args_json inválido: {exc}"
        if not isinstance(args, dict):
            return "ERRO: args_json precisa ser um objeto JSON, ex.: '{\"x\": 1}'"

    try:
        job = scheduler.add_job(
            name=nome,
            cron=cron,
            kind="shell" if comando else "tool",
            payload=comando or ferramenta,
            args=args,
        )
    except ValueError as exc:
        return f"ERRO: {exc}"

    return (
        f"✅ tarefa agendada [{job.id}] {job.name}\n"
        f"   quando: {scheduler.describe_cron(job.cron)}  (cron: {job.cron})\n"
        f"   o que: {job.kind} → {job.payload}\n"
        f"   rode 'nh cron daemon' (ou deixe o serviço ativo) para os jobs dispararem."
    )


def list_tasks() -> str:
    """Lista todas as tarefas agendadas, com status e última execução."""
    jobs = scheduler.load_jobs()
    if not jobs:
        return "📭 nenhuma tarefa agendada. Use schedule_task para criar."
    return f"⏰ {len(jobs)} tarefa(s) agendada(s):\n\n" + "\n\n".join(j.describe() for j in jobs)


def remove_task(id_ou_nome: str) -> str:
    """Remove uma tarefa agendada pelo id ou pelo nome exato.

    Args:
        id_ou_nome: id de 8 caracteres (ex.: 'a1b2c3d4') ou o nome da tarefa.
    """
    jobs = scheduler.load_jobs()
    alvo = next((j for j in jobs if j.id == id_ou_nome or j.name == id_ou_nome), None)
    if alvo is None:
        return f"❌ não achei tarefa com id/nome '{id_ou_nome}'. Use list_tasks para ver."
    scheduler.remove_job(alvo.id)
    return f"🗑️ removida [{alvo.id}] {alvo.name}"


def pause_task(id_ou_nome: str) -> str:
    """Pausa ou reativa uma tarefa (alterna o estado).

    Args:
        id_ou_nome: id ou nome da tarefa.
    """
    jobs = scheduler.load_jobs()
    alvo = next((j for j in jobs if j.id == id_ou_nome or j.name == id_ou_nome), None)
    if alvo is None:
        return f"❌ não achei tarefa '{id_ou_nome}'."
    updated = scheduler.toggle_job(alvo.id)
    estado = "▶️ ativa" if updated and updated.enabled else "⏸️ pausada"
    return f"{estado}: [{alvo.id}] {alvo.name}"


def run_task_now(id_ou_nome: str) -> str:
    """Executa uma tarefa agendada IMEDIATAMENTE (não espera o horário).

    Args:
        id_ou_nome: id ou nome da tarefa.
    """
    jobs = scheduler.load_jobs()
    alvo = next((j for j in jobs if j.id == id_ou_nome or j.name == id_ou_nome), None)
    if alvo is None:
        return f"❌ não achei tarefa '{id_ou_nome}'."
    from ..core import load_plugins

    reg = load_plugins()
    out = scheduler.run_job(alvo, reg)
    return f"▶️ [{alvo.id}] {alvo.name} executada agora:\n{out}"


def explain_cron(expressao: str) -> str:
    """Traduz uma expressão cron para português (ajuda a conferir se está certa).

    Args:
        expressao: a expressão cron de 5 campos, ex.: '*/15 9-18 * * 1-5'.
    """
    try:
        scheduler.parse_cron(expressao)
    except ValueError as exc:
        return f"❌ {exc}"
    return f"'{expressao}' = {scheduler.describe_cron(expressao)}"


def register(reg: Registry) -> None:
    reg.add(schedule_task, risk="write", plugin="schedule")
    reg.add(list_tasks, risk="safe", plugin="schedule")
    reg.add(remove_task, risk="write", plugin="schedule")
    reg.add(pause_task, risk="write", plugin="schedule")
    reg.add(run_task_now, risk="exec", plugin="schedule")
    reg.add(explain_cron, risk="safe", plugin="schedule")
