"""Plugin: sessions — o agente enxergando e falando das sessões de projeto.

A sessão em si é gerenciada pela interface (`nh/sessions.py`); aqui ficam as
ferramentas para o agente responder "onde eu estou?" e "quais projetos tenho?".
"""

from __future__ import annotations

from ..core import Registry, workspace
from ..sessions import listar, por_pasta

MANIFEST = {
    "id": "sessions",
    "nome": "Sessões de projeto",
    "versao": "1.0.0",
    "autor": "jaivedpereira",
    "categoria": "núcleo",
    "descricao": "Mostra a pasta da sessão atual e lista os projetos já abertos.",
    "risco_max": "safe",
    "plataformas": ["linux", "windows", "darwin", "android"],
    "requer": [],
    "tags": ["sessão", "projeto", "pasta"],
}


def sessao_atual() -> str:
    """Mostra em qual pasta de projeto o agente está trabalhando agora."""
    w = workspace()
    s = por_pasta(str(w))
    if s:
        return (f"📂 sessão '{s.get('nome')}' (id {s.get('id')})\n"
                f"   pasta: {w}\n"
                f"   conversa: {len(s.get('historico') or [])} mensagem(ns) guardada(s)\n"
                f"   todas as ferramentas de arquivo e comando usam esta pasta")
    return f"📂 sem sessão aberta — trabalhando no workspace padrão: {w}"


def listar_sessoes() -> str:
    """Lista as sessões (pastas de projeto) já criadas na interface."""
    itens = listar()
    if not itens:
        return "nenhuma sessão criada ainda — crie uma na aba Sessões da interface."
    linhas = [f"📂 {len(itens)} sessão(ões):"]
    for s in itens:
        aviso = "" if s.get("existe") else "  ⚠️ a pasta sumiu"
        linhas.append(f"   {s['id']}  {s['nome'][:24]:24} {s['pasta']} "
                      f"({s.get('mensagens', 0)} msg){aviso}")
    return "\n".join(linhas)


def register(reg: Registry) -> None:
    reg.add(sessao_atual, risk="safe", plugin="sessions")
    reg.add(listar_sessoes, risk="safe", plugin="sessions")
