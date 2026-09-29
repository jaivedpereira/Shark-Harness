"""Registro de uso do modelo — quanto de token cada execução gastou.

É append-only em `~/.shark-harness/usage.jsonl`: uma linha JSON por execução do
agente. Serve para responder "quanto eu já gastei hoje?", "qual modelo eu mais
uso?" e "quanto isso custaria no plano pago?".

Nada aqui é enviado para fora: o arquivo é local, igual o log de auditoria.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from .paths import HOME

USAGE_FILE = HOME / "usage.jsonl"

# Preço em dólar por 1 MILHÃO de tokens (entrada, saída). Só para estimativa —
# quem manda é a fatura do provedor. Modelo sem entrada aqui não tem preço estimado.
PRECOS: dict[str, tuple[float, float]] = {
    "openai/gpt-4o": (2.50, 10.00),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4.1": (2.00, 8.00),
    "openai/gpt-4.1-mini": (0.40, 1.60),
    "deepseek/deepseek-chat": (0.27, 1.10),
    "deepseek/deepseek-reasoner": (0.55, 2.19),
    "anthropic/claude-3.5-sonnet": (3.00, 15.00),
    "anthropic/claude-3.7-sonnet": (3.00, 15.00),
    "google/gemini-flash-1.5": (0.075, 0.30),
    "google/gemini-2.0-flash-001": (0.10, 0.40),
    "qwen/qwen-2.5-72b-instruct": (0.23, 0.40),
    "meta-llama/llama-3.3-70b-instruct": (0.12, 0.30),
    "mistralai/mistral-nemo": (0.02, 0.04),
}


def preco(modelo: str) -> tuple[float, float] | None:
    """Preço (entrada, saída) por 1M tokens, ou None se não houver tabela."""
    m = str(modelo or "").lower()
    if m.endswith(":free") or "-free" in m:
        return (0.0, 0.0)
    if m in PRECOS:
        return PRECOS[m]
    # tenta casar pelo nome sem o prefixo do provedor
    curto = m.split("/")[-1]
    for chave, valor in PRECOS.items():
        if chave.split("/")[-1] == curto:
            return valor
    return None


def estimar_custo(modelo: str, tokens_entrada: int, tokens_saida: int) -> float | None:
    """Custo estimado em dólar (None quando não há tabela de preço do modelo)."""
    p = preco(modelo)
    if p is None:
        return None
    return (tokens_entrada / 1_000_000) * p[0] + (tokens_saida / 1_000_000) * p[1]


def registrar(modelo: str, tokens_entrada: int, tokens_saida: int, *,
              rodadas: int = 0, ferramentas: list[str] | None = None,
              origem: str = "") -> None:
    """Grava uma execução no histórico. Nunca levanta erro (não pode quebrar o agente)."""
    entrada = int(tokens_entrada or 0)
    saida = int(tokens_saida or 0)
    if entrada <= 0 and saida <= 0:
        return  # o provedor não informou consumo: não inventamos
    linha = {
        "ts": time.time(),
        "quando": datetime.now().isoformat(timespec="seconds"),
        "modelo": str(modelo or "?"),
        "entrada": entrada,
        "saida": saida,
        "total": entrada + saida,
        "rodadas": int(rodadas or 0),
        "ferramentas": list(ferramentas or []),
        "origem": origem or "",
    }
    try:
        HOME.mkdir(parents=True, exist_ok=True)
        with USAGE_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — telemetria nunca derruba o trabalho
        pass


def ler(dias: int = 30) -> list[dict]:
    """Lê o histórico dos últimos N dias."""
    if not USAGE_FILE.is_file():
        return []
    limite = time.time() - max(1, int(dias)) * 86400
    saida: list[dict] = []
    try:
        for linha in USAGE_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            linha = linha.strip()
            if not linha:
                continue
            try:
                d = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if float(d.get("ts") or 0) >= limite:
                saida.append(d)
    except Exception:  # noqa: BLE001
        return []
    return saida


def _soma(itens: list[dict]) -> dict:
    entrada = sum(int(i.get("entrada") or 0) for i in itens)
    saida = sum(int(i.get("saida") or 0) for i in itens)
    custo = 0.0
    sem_preco = False
    for i in itens:
        c = estimar_custo(str(i.get("modelo") or ""), int(i.get("entrada") or 0),
                          int(i.get("saida") or 0))
        if c is None:
            sem_preco = True
        else:
            custo += c
    return {
        "execucoes": len(itens),
        "entrada": entrada,
        "saida": saida,
        "total": entrada + saida,
        "custo": round(custo, 6),
        "custo_conhecido": not sem_preco or bool(itens),
        "tem_modelo_sem_preco": sem_preco,
    }


def resumo(dias: int = 30) -> dict:
    """Resumo pronto para a interface: hoje, 7 dias, total, por modelo e por dia."""
    tudo = ler(dias)
    hoje_iso = date.today().isoformat()
    de_hoje = [i for i in tudo if str(i.get("quando", "")).startswith(hoje_iso)]
    limite7 = (datetime.now() - timedelta(days=7)).timestamp()
    ultimos7 = [i for i in tudo if float(i.get("ts") or 0) >= limite7]

    por_modelo: dict[str, list[dict]] = {}
    for i in tudo:
        por_modelo.setdefault(str(i.get("modelo") or "?"), []).append(i)

    modelos = []
    for nome, itens in sorted(por_modelo.items(), key=lambda kv: -len(kv[1])):
        s = _soma(itens)
        s["modelo"] = nome
        p = preco(nome)
        s["preco_conhecido"] = p is not None
        modelos.append(s)

    # últimos 14 dias, dia a dia (para o gráfico de barras)
    por_dia: list[dict] = []
    for volta in range(13, -1, -1):
        dia = (date.today() - timedelta(days=volta)).isoformat()
        itens = [i for i in tudo if str(i.get("quando", "")).startswith(dia)]
        por_dia.append({"dia": dia, **_soma(itens)})

    ferramentas: dict[str, int] = {}
    for i in tudo:
        for f in i.get("ferramentas") or []:
            ferramentas[f] = ferramentas.get(f, 0) + 1

    return {
        "arquivo": str(USAGE_FILE),
        "dias": dias,
        "hoje": _soma(de_hoje),
        "semana": _soma(ultimos7),
        "total": _soma(tudo),
        "modelos": modelos,
        "por_dia": por_dia,
        "ferramentas": sorted(ferramentas.items(), key=lambda kv: -kv[1])[:10],
        "moeda": "US$",
    }


def limpar() -> str:
    """Apaga o histórico de uso (não mexe em mais nada)."""
    if not USAGE_FILE.is_file():
        return "nada para limpar — o histórico já está vazio."
    n = len(ler(3650))
    USAGE_FILE.unlink()
    return f"🗑️ histórico de uso apagado ({n} registro(s))."


__all__ = ["registrar", "ler", "resumo", "preco", "estimar_custo", "limpar", "USAGE_FILE"]
