"""Agendador do Shark Harness — cron próprio, sem depender de crontab do sistema.

Por que não usar `crontab`? Porque no Termux ele não existe de verdade e no
Windows também não. Um agendador embutido funciona igual nas três plataformas e
ainda permite agendar *ferramentas do harness* (não só comandos de shell).

Formato do campo cron: `minuto hora dia-do-mês mês dia-da-semana`
  */5 * * * *      → a cada 5 minutos
  30 7 * * 1-5     → 07:30 de segunda a sexta
  0 9,18 * * *     → 09:00 e 18:00 todo dia
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from .paths import JOBS_FILE, ensure_dirs

WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]


@dataclass
class Job:
    name: str
    cron: str
    kind: str  # "shell" (comando) | "tool" (ferramenta do harness)
    payload: str  # o comando, ou o nome da ferramenta
    args: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    last_run: str = ""
    last_status: str = ""
    runs: int = 0

    def describe(self) -> str:
        estado = "✅ ativo" if self.enabled else "⏸️ pausado"
        alvo = self.payload if self.kind == "shell" else f"{self.payload}({self.args})"
        return (
            f"[{self.id}] {self.name} — {self.cron} ({describe_cron(self.cron)})\n"
            f"     {estado} · {self.kind}: {alvo}\n"
            f"     execuções: {self.runs} · último: {self.last_run or 'nunca'}"
            + (f" ({self.last_status})" if self.last_status else "")
        )


# ------------------------------------------------------------- cron parsing ---


def _parse_field(field_: str, lo: int, hi: int) -> set[int]:
    """Expande um campo cron em um conjunto de inteiros válidos."""
    out: set[int] = set()
    for chunk in field_.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        step = 1
        if "/" in chunk:
            base, _, step_s = chunk.partition("/")
            try:
                step = max(1, int(step_s))
            except ValueError:
                step = 1
            chunk = base or "*"
        if chunk == "*":
            start, end = lo, hi
        elif "-" in chunk:
            a, _, b = chunk.partition("-")
            try:
                start, end = int(a), int(b)
            except ValueError:
                continue
        else:
            try:
                start = end = int(chunk)
            except ValueError:
                continue
        rng = range(start, end + 1, step)
        out |= {v for v in rng if lo <= v <= hi}
    return out or set(range(lo, hi + 1))


def parse_cron(expr: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    """Valida e expande a expressão. Levanta ValueError se estiver malformada."""
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(
            "cron precisa de 5 campos: 'minuto hora dia mês dia-da-semana' "
            "(ex.: '*/30 * * * *')"
        )
    minute = _parse_field(parts[0], 0, 59)
    hour = _parse_field(parts[1], 0, 23)
    dom = _parse_field(parts[2], 1, 31)
    month = _parse_field(parts[3], 1, 12)
    # cron usa 0=domingo; aqui 0=segunda (python weekday). 7 também é domingo.
    dow_raw = _parse_field(parts[4], 0, 7)
    dow = {(d - 1) % 7 for d in dow_raw}
    return minute, hour, dom, month, dow


def matches(expr: str, when: datetime | None = None) -> bool:
    """A expressão bate com este minuto?"""
    when = when or datetime.now()
    minute, hour, dom, month, dow = parse_cron(expr)
    return (
        when.minute in minute
        and when.hour in hour
        and when.day in dom
        and when.month in month
        and when.weekday() in dow
    )


def describe_cron(expr: str) -> str:
    """Traduz a expressão para algo legível em PT-BR."""
    try:
        minute, hour, dom, month, dow = parse_cron(expr)
    except ValueError:
        return "expressão inválida"

    def fmt_min(vals: set[int], total: int) -> str:
        if len(vals) == total:
            return "todo"
        s = sorted(vals)
        if len(s) == 1:
            return f"no minuto {s[0]}"
        if len(s) <= 6:
            return "nos minutos " + ", ".join(str(x) for x in s)
        return "em minutos selecionados"

    if len(minute) == 60 and len(hour) == 24:
        base = "a cada minuto"
    elif len(hour) == 24:
        base = f"a cada {sorted(minute)[1] if len(minute) > 1 and sorted(minute)[1] else 5} min" if len(minute) < 60 else "a cada minuto"
    elif len(minute) == 1 and len(hour) <= 6:
        base = "às " + ", ".join(f"{h:02d}:{sorted(minute)[0]:02d}" for h in sorted(hour))
    else:
        base = f"{fmt_min(minute, 60)} de {len(hour)} hora(s)"

    if len(dow) < 7:
        base += " · " + ", ".join(WEEKDAYS[d] for d in sorted(dow))
    if len(dom) < 31:
        base += " · dia(s) " + ", ".join(str(d) for d in sorted(dom))
    return base


# ---------------------------------------------------------------- armazenamento ---


def load_jobs() -> list[Job]:
    ensure_dirs()
    if not JOBS_FILE.exists():
        return []
    try:
        raw = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    jobs = []
    for item in raw if isinstance(raw, list) else []:
        try:
            jobs.append(Job(**{k: v for k, v in item.items() if k in Job.__dataclass_fields__}))
        except Exception:
            continue
    return jobs


def save_jobs(jobs: list[Job]) -> None:
    ensure_dirs()
    JOBS_FILE.write_text(
        json.dumps([asdict(j) for j in jobs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_job(name: str, cron: str, kind: str, payload: str, args: dict[str, Any] | None = None) -> Job:
    parse_cron(cron)  # valida antes de gravar
    job = Job(name=name, cron=cron, kind=kind, payload=payload, args=args or {})
    jobs = load_jobs()
    jobs.append(job)
    save_jobs(jobs)
    return job


def remove_job(job_id: str) -> bool:
    jobs = load_jobs()
    rest = [j for j in jobs if j.id != job_id]
    if len(rest) == len(jobs):
        return False
    save_jobs(rest)
    return True


def toggle_job(job_id: str, enabled: bool | None = None) -> Job | None:
    jobs = load_jobs()
    target = next((j for j in jobs if j.id == job_id), None)
    if target is None:
        return None
    target.enabled = (not target.enabled) if enabled is None else bool(enabled)
    save_jobs(jobs)
    return target


# ------------------------------------------------------------------ execução ---


def run_job(job: Job, reg=None) -> str:
    """Executa o job agora. `reg` é o Registry (necessário para kind='tool')."""
    started = time.time()
    if job.kind == "shell":
        from .plugins.shell import run_shell

        result = run_shell(job.payload, timeout=300)
    elif job.kind == "tool":
        if reg is None:
            result = "ERRO: job do tipo 'tool' precisa do registry (rode pelo daemon/CLI)."
        else:
            result = reg.dispatch(job.payload, job.args)
    else:
        result = f"ERRO: kind desconhecido '{job.kind}' (use 'shell' ou 'tool')."

    dur = round(time.time() - started, 2)
    ok = not str(result).startswith(("ERRO", "🛑", "❌", "⏱️"))
    jobs = load_jobs()
    for j in jobs:
        if j.id == job.id:
            j.last_run = time.strftime("%Y-%m-%d %H:%M:%S")
            j.last_status = f"{'ok' if ok else 'falha'} em {dur}s"
            j.runs += 1
    save_jobs(jobs)
    return result


def due_jobs(now: datetime, jobs: list[Job] | None = None) -> list[Job]:
    """Jobs ativos cujo cron bate neste minuto e que ainda não rodaram nele."""
    jobs = jobs if jobs is not None else load_jobs()
    out = []
    for job in jobs:
        if not job.enabled:
            continue
        try:
            if not matches(job.cron, now):
                continue
        except ValueError:
            continue
        if job.last_run[:16] == now.strftime("%Y-%m-%d %H:%M"):
            continue  # já rodou neste minuto
        out.append(job)
    return out


def daemon(reg, interval: int = 20, quiet: bool = False) -> None:
    """Loop do agendador. Roda até receber Ctrl+C."""
    log = (lambda *a: None) if quiet else print
    log(f"⏰ Shark Harness scheduler ativo (tick {interval}s) — {len(load_jobs())} job(s) registrados")
    while True:
        try:
            now = datetime.now()
            for job in due_jobs(now):
                log(f"▶️  {now:%H:%M} rodando [{job.id}] {job.name}")
                out = run_job(job, reg)
                log("   " + str(out).replace("\n", "\n   ")[:400])
            time.sleep(interval)
        except KeyboardInterrupt:
            log("\n⏹️  scheduler parado")
            return


__all__ = [
    "Job", "load_jobs", "save_jobs", "add_job", "remove_job", "toggle_job",
    "run_job", "due_jobs", "daemon", "matches", "parse_cron", "describe_cron",
]
