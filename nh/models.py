"""Catálogo de modelos — vários modelos, cada um no seu endpoint e com um nível.

O harness nasceu com UM modelo só (LLM_URL/LLM_MODEL/LLM_KEY). Aqui você cadastra
quantos quiser, cada um com:

  • apelido    — o nome que aparece na interface ("Nemotron grátis")
  • endpoint   — a URL completa do provedor (pode ser outro provedor por modelo)
  • modelo     — o id do modelo naquele provedor
  • chave      — opcional; vazio usa a chave global
  • nível      — 1 rápido · 2 equilibrado · 3 potente
  • observação — uma nota livre ("bom pra código", "cai muito")

O nível serve para três coisas: agrupar os modelos na escolha, ordenar os
**reservas** (se o escolhido falha, tenta o próximo do mesmo nível antes de subir
para os mais potentes) e deixar explícito o que você espera daquele modelo.

Fica tudo em `~/.shark-harness/config.json` (junto do resto da configuração), então
sobrevive a `git pull` e reinstalação.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid

from .paths import env as ler_env
from .paths import read_config, update_config

NIVEIS = {
    1: {"nome": "Rápido", "emoji": "⚡",
        "descricao": "respostas curtas e baratas — bom para o dia a dia e tarefas simples"},
    2: {"nome": "Equilibrado", "emoji": "⚖️",
        "descricao": "meio termo entre qualidade e velocidade — bom padrão"},
    3: {"nome": "Potente", "emoji": "🧠",
        "descricao": "raciocínio forte para tarefa difícil — mais lento e mais caro"},
}


def nivel_info(nivel) -> dict:
    """Dados do nível (nome, emoji, descrição), tolerando valor inválido."""
    try:
        n = int(nivel)
    except (TypeError, ValueError):
        n = 2
    return NIVEIS.get(n, NIVEIS[2])


# ------------------------------------------------------------------ leitura ---
def listar(incluir_sensiveis: bool = False) -> list[dict]:
    """Todos os modelos cadastrados, ordenados por nível e depois por nome."""
    itens = read_config().get("modelos") or []
    if not isinstance(itens, list):
        return []
    saida = []
    for m in itens:
        if not isinstance(m, dict):
            continue
        m = dict(m)
        info = nivel_info(m.get("nivel"))
        m["nivel"] = int(m.get("nivel") or 2)
        m["nivel_nome"] = info["nome"]
        m["nivel_emoji"] = info["emoji"]
        # a chave nunca sai inteira: só o suficiente para o usuário reconhecer
        chave = str(m.get("chave") or "")
        m["tem_chave_propria"] = bool(chave)
        # a interface usa isto para avisar "sem chave" sem precisar tentar e falhar
        m["tem_chave"] = bool(chave) or bool(str(ler_env("LLM_KEY") or "").strip())
        if not incluir_sensiveis:
            m["chave"] = ""
            m["chave_mascarada"] = mascarar(chave)
        saida.append(m)
    saida.sort(key=lambda x: (x["nivel"], str(x.get("apelido") or "").lower()))
    return saida


def obter(mid: str) -> dict | None:
    """Um modelo pelo id."""
    for m in listar(incluir_sensiveis=True):
        if m.get("id") == mid:
            return m
    return None


def ativo() -> dict | None:
    """O modelo escolhido para o chat (None = usa o modelo global do config)."""
    mid = str(read_config().get("modelo_ativo") or "")
    if not mid:
        return None
    return obter(mid)


def mascarar(chave: str) -> str:
    """`sk-or-…8469`: o suficiente para reconhecer, sem expor."""
    c = str(chave or "")
    if not c:
        return ""
    if len(c) <= 12:
        return "•" * len(c)
    return f"{c[:6]}…{c[-4:]}"


# ------------------------------------------------------------------ escrita ---
def salvar(dados: dict) -> dict:
    """Cria ou atualiza um modelo. Sem `id`, cria novo."""
    apelido = str(dados.get("apelido") or "").strip()
    url = str(dados.get("url") or "").strip()
    modelo = str(dados.get("modelo") or "").strip()
    if not url:
        raise ValueError("informe o endpoint (URL do provedor)")
    if not modelo:
        raise ValueError("informe o nome do modelo")

    try:
        nivel = int(dados.get("nivel") or 2)
    except (TypeError, ValueError):
        nivel = 2
    nivel = min(3, max(1, nivel))

    itens = list(read_config().get("modelos") or [])
    mid = str(dados.get("id") or "").strip()
    chave_nova = dados.get("chave")
    registro = {
        "id": mid or uuid.uuid4().hex[:8],
        "apelido": apelido or modelo.split("/")[-1],
        "url": url,
        "modelo": modelo,
        "nivel": nivel,
        "nota": str(dados.get("nota") or "").strip(),
        "criado": time.time(),
    }

    for i, m in enumerate(itens):
        if isinstance(m, dict) and m.get("id") == registro["id"]:
            registro["criado"] = m.get("criado") or registro["criado"]
            # chave: só troca se veio uma nova; string vazia = manter a que estava
            if chave_nova is None or str(chave_nova).strip() == "":
                registro["chave"] = m.get("chave") or ""
            else:
                registro["chave"] = str(chave_nova).strip()
            itens[i] = registro
            break
    else:
        registro["chave"] = str(chave_nova or "").strip()
        itens.append(registro)

    update_config(modelos=itens)
    return registro


def remover(mid: str) -> str:
    """Tira um modelo do catálogo."""
    atuais = list(read_config().get("modelos") or [])
    restantes = [m for m in atuais if not (isinstance(m, dict) and m.get("id") == mid)]
    if len(restantes) == len(atuais):
        return f"❌ modelo '{mid}' não existe no catálogo."
    update_config(modelos=restantes)
    if str(read_config().get("modelo_ativo") or "") == mid:
        update_config(modelo_ativo="")  # volta a usar o global
    return "🗑️ modelo removido do catálogo."


def definir_ativo(mid: str) -> str:
    """Escolhe o modelo do chat (vazio = volta ao modelo global do config)."""
    if not mid:
        update_config(modelo_ativo="")
        return "✅ voltou a usar o modelo global."
    m = obter(mid)
    if m is None:
        return f"❌ modelo '{mid}' não está no catálogo."
    update_config(modelo_ativo=mid)
    ok = tem_chave(m)
    aviso = "" if ok else (" ⚠️ sem chave: cole a chave global em Ajustes "
                           "ou uma própria para este modelo.")
    return f"✅ chat usando {m.get('apelido')} ({m.get('modelo')}){aviso}"


# ------------------------------------------------------------------ reservas ---
def resolver(m: dict | None, global_: dict | None = None) -> dict | None:
    """Transforma um item do catálogo no que a chamada precisa: url, modelo e chave.

    O que não estiver no item cai para a configuração global — passando pela
    cadeia de precedência (`SHARK_LLM_KEY` → config.json → .env), então funciona
    igual se a chave está no ambiente ou salva pela interface.
    """
    if not m:
        return None
    return {
        "id": m.get("id"),
        "apelido": m.get("apelido"),
        "nivel": int(m.get("nivel") or 2),
        "url": m.get("url") or ler_env("LLM_URL") or (global_ or {}).get("llm_url") or "",
        "modelo": (m.get("modelo") or ler_env("LLM_MODEL")
                   or (global_ or {}).get("llm_model") or ""),
        "chave": m.get("chave") or ler_env("LLM_KEY") or (global_ or {}).get("llm_key") or "",
    }


def tem_chave(m: dict | None = None) -> bool:
    """Se esse modelo tem chave para chamar (a própria ou a global)."""
    if m and str(m.get("chave") or "").strip():
        return True
    return bool(str(ler_env("LLM_KEY") or "").strip())


def reservas(excluir_id: str = "", ativo_resolvido: dict | None = None) -> list[dict]:
    """Os outros modelos do catálogo, em ordem de tentativa.

    A ordem importa: primeiro os do MESMO nível do que falhou (troca justa),
    depois os mais potentes (se algo tem que dar conta, que seja o forte) e por
    último os mais rápidos.
    """
    todos = listar(incluir_sensiveis=True)
    if not todos:
        return []
    atual_id = excluir_id or str(read_config().get("modelo_ativo") or "")
    nivel_atual = 2
    for m in todos:
        if m.get("id") == atual_id:
            nivel_atual = int(m.get("nivel") or 2)
    outros = [m for m in todos if m.get("id") != atual_id]
    outros.sort(key=lambda m: (abs(int(m.get("nivel") or 2) - nivel_atual),
                               -int(m.get("nivel") or 2)))
    saida = []
    for m in outros:
        d = resolver(m)
        if d and d["url"] and d["modelo"]:
            saida.append(d)
    return saida


# -------------------------------------------------------------------- teste ---
PERGUNTAS = [
    {"pergunta": "Responda apenas com o número: quanto é 17 + 26?",
     "esperado": ["43"], "limite": 12},
    {"pergunta": "Responda apenas com a palavra: qual é a cor do céu num dia limpo?",
     "esperado": ["azul", "blue"], "limite": 20},
    {"pergunta": "Escreva exatamente esta frase, sem mais nada: o tubarão é azul",
     "esperado": ["tubarão é azul", "tubarao e azul"], "limite": 40},
]

# como o modelo erra, em português claro — é isso que o usuário precisa saber
DIAGNOSTICO = {
    "vazio": "respondeu vazio",
    "raciocinio": "vazou o raciocínio em vez de responder",
    "lingua": "respondeu em inglês",
    "errado": "respondeu outra coisa",
    "erro": "erro na chamada",
}


def _classificar(texto: str, esperados: list[str], limite: int) -> tuple[bool, str]:
    """Diz se a resposta serve e, quando não serve, por quê."""
    t = (texto or "").strip()
    if not t:
        return False, "vazio"
    baixo = t.lower()
    if len(t) > max(limite * 6, 90):
        # a pergunta pedia uma palavra e veio um textão: é raciocínio vazando
        return False, "raciocinio"
    if not any(e in baixo for e in esperados):
        if any(p in baixo for p in ("here's", "thinking process", "i need to", "the user asks")):
            return False, "raciocinio"
        if any(p in baixo for p in ("i'm sorry", "i cannot", "as an ai")):
            return False, "errado"
        return False, "errado"
    return True, ""


def testar(mid: str, timeout: int = 30, orcamento: int = 100) -> dict:
    """Roda 3 perguntas simples e mede acerto + velocidade do modelo.

    É um teste grosseiro de propósito, mas pega o que mais atrapalha no dia a dia:
    não responder, vazar o raciocínio, responder em inglês, inventar e demorar.
    Gasta quase nada (no máximo ~180 tokens).

    `orcamento` é o teto de tempo do teste inteiro: modelo que passa disso já está
    reprovado por lentidão, então as perguntas que faltam nem são feitas.
    """
    from .agent import _post, _erro_do_provedor

    entrada = resolver(obter(mid) or {})
    if not entrada or not entrada["url"]:
        return {"ok": False, "erro": "modelo sem endpoint configurado."}
    if not entrada.get("chave"):
        return {"ok": False, "erro": "sem chave — cole a chave global em Ajustes "
                                     "ou uma chave própria neste modelo."}

    resultados = []
    acertos = 0
    tempos = []
    inicio = time.time()
    for i, caso in enumerate(PERGUNTAS):
        # já estourou o orçamento: nem vale continuar
        if time.time() - inicio > orcamento:
            resultados.append({
                "pergunta": caso["pergunta"], "ok": False,
                "motivo": "não testado — o modelo é lento demais",
                "resposta": "(o teste já tinha passado do tempo limite)",
                "segundos": 0,
            })
            continue
        payload = {
            "model": entrada["modelo"],
            "messages": [{"role": "user", "content": caso["pergunta"]}],
            "max_tokens": 60,
        }
        t0 = time.time()
        try:
            resp = _post(entrada["url"], payload, entrada["chave"], timeout=timeout)
            dur = time.time() - t0
            erro = _erro_do_provedor(resp)
            if erro:
                resultados.append({"pergunta": caso["pergunta"], "ok": False,
                                   "motivo": DIAGNOSTICO["erro"], "resposta": erro[:160],
                                   "segundos": round(dur, 1)})
                continue
            escolhas = resp.get("choices") or []
            texto = ""
            if escolhas:
                texto = str((escolhas[0].get("message") or {}).get("content") or "").strip()
            acertou, motivo = _classificar(texto, caso["esperado"], caso["limite"])
            if acertou:
                acertos += 1
                tempos.append(dur)
            resultados.append({
                "pergunta": caso["pergunta"], "ok": acertou,
                "motivo": DIAGNOSTICO.get(motivo, ""),
                "resposta": texto[:200] or "(vazio)",
                "segundos": round(dur, 1),
            })
        except urllib.error.HTTPError as exc:
            corpo = exc.read().decode("utf-8", "replace")[:140]
            dica = ""
            if exc.code == 404:
                dica = "esse modelo não existe nesse provedor (ou saiu do plano grátis)"
            elif exc.code in (401, 403):
                dica = "a chave foi recusada"
            elif exc.code == 429:
                dica = "rate-limit: tente de novo em alguns segundos"
            resultados.append({"pergunta": caso["pergunta"], "ok": False,
                               "motivo": f"HTTP {exc.code}" + (f" — {dica}" if dica else ""),
                               "resposta": corpo[:140], "segundos": 0})
        except Exception as exc:  # noqa: BLE001
            resultados.append({"pergunta": caso["pergunta"], "ok": False,
                               "motivo": f"{type(exc).__name__}",
                               "resposta": str(exc)[:140], "segundos": 0})

    media = sum(tempos) / len(tempos) if tempos else 0
    total = round(time.time() - inicio, 1)
    if acertos == len(PERGUNTAS) and media <= 8:
        veredito = "✅ respondendo certo e rápido"
    elif acertos == len(PERGUNTAS):
        veredito = f"🐢 certo, mas lento (média {media:.0f}s por resposta)"
    elif acertos:
        veredito = "⚠️ acerta só parte das vezes"
    else:
        veredito = "❌ não deu conta nem do básico"
    return {
        "ok": True, "acertos": acertos, "total": len(PERGUNTAS),
        "media_segundos": round(media, 1), "segundos_total": total,
        "veredito": veredito, "detalhes": resultados,
    }
