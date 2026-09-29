"""Loop de agente — o LLM escolhe ferramentas e o harness executa.

Zero dependências externas: usa urllib da stdlib, então roda no Termux com
apenas Python. Qualquer endpoint OpenAI-compatível serve (DeepSeek, OpenCode/Zen,
Groq, OpenRouter, Ollama local...).

Config por env:
  SHARK_LLM_URL     endpoint OpenAI-compatível (default: OpenRouter)
  SHARK_LLM_KEY     token do provedor (sem ele o chat não responde)
  SHARK_LLM_MODEL   modelo (default: nvidia/nemotron-3.5-lightning:free)
  SHARK_MAX_RISK    risco máximo exposto ao modelo: safe|write|exec|danger (default exec)
  SHARK_MAX_ROUNDS  rodadas do loop de ferramentas (default 14)

O prefixo legado `NH_` continua aceito em todas elas. Também vale o que estiver em
`~/.shark-harness/config.json` (a aba Configurações da interface escreve lá).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .core import Registry, load_plugins
from .paths import env

# Default verificado funcionando de ponta a ponta (o tier grátis do zen exige
# rodar de dentro do OpenCode e os pagos pedem saldo — ver README).
DEFAULT_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning:free"

# Alguns provedores ficam atrás de Cloudflare e recusam o UA padrão do urllib
# ("Python-urllib/3.11") com `error code: 1010`. Um UA comum resolve.
USER_AGENT = "shark-harness/0.1 (+https://github.com/jaivedpereira/Shark-Harness)"

# Rounds padrão. Cada chamada de ferramenta gasta uma rodada — 8 era apertado demais
# para tarefa de depuração (escrever script -> rodar -> corrigir -> rodar) e o agente
# terminava com "limite atingido" em vez de entregar algo. Ver SHARK_MAX_ROUNDS.
MAX_ROUNDS_PADRAO = 14

SYSTEM = """Você é o Shark Harness: um agente que executa tarefas reais no dispositivo do usuário.

Como trabalhar:
- Use as ferramentas em vez de adivinhar. Nunca invente saída de comando.
- ANTES de escrever código do zero, veja se o sistema já tem ferramenta pronta:
  use `which` (ex.: which pdfimages; which ffmpeg; which convert) e prefira a que existe.
  Escrever um extrator de PDF na mão é o caminho mais longo e o que mais falha —
  `pdfimages` resolve em um comando.
- Se a tarefa tem muitos passos pequenos, escreva UM script que faz tudo de uma vez
  e rode ele: isso gasta 1 rodada em vez de 10.
- Você tem um número LIMITADO de rodadas (cada chamada de ferramenta gasta uma).
  Se o pedido é grande, resolva a parte principal primeiro.
- Se estiver perto do limite, ENTREGUE o que já conseguiu e diga o que ficou pendente.
  Nunca termine de mãos vazias.
- Se um comando falhar, tente UMA alternativa óbvia; se falhar de novo, explique e pare
  em vez de insistir na mesma abordagem.
- Quando terminar, responda em português, curto e direto: o que fez e o resultado real.
- Se uma ferramenta for bloqueada pela guarda, explique e proponha alternativa segura.
- Você tem permissão para criar, ler e modificar arquivos do usuário e rodar comandos
  não destrutivos. Não tente contornar a guarda de segurança.
"""


def _post(url: str, payload: dict, api_key: str = "", timeout: int = 180) -> dict:
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _tool_result_text(msg: dict) -> str:
    content = msg.get("content")
    if isinstance(content, str) and content.strip():
        return content
    # alguns modelos devolvem content vazio/None quando só querem "encerrar";
    # sem isso o usuário recebia a palavra "None" na tela
    return ("Terminei, mas o modelo não escreveu uma resposta final. "
            "Os resultados das ferramentas estão nos passos acima.")


def run_agent(
    user_text: str,
    *,
    reg: Registry | None = None,
    model: str = "",
    url: str = "",
    api_key: str = "",
    max_rounds: int = 0,
    max_risk: str = "",
    verbose: bool = True,
    history: list | None = None,
    on_step=None,
) -> str:
    """Roda o agente: manda o pedido ao LLM e executa as ferramentas que ele escolher.

    Devolve a resposta final em texto. `history` opcional mantém o contexto entre
    chamadas (lista de mensagens no formato OpenAI).

    `on_step(tipo, nome, detalhe)` é chamado a cada evento — usado pela interface
    web para mostrar os passos ao vivo. Tipos: 'chamada', 'resultado', 'resposta',
    'erro', 'info'.
    """
    reg = reg or load_plugins()
    url = url or env("LLM_URL", DEFAULT_URL)
    model = model or env("LLM_MODEL", DEFAULT_MODEL)
    api_key = api_key or env("LLM_KEY")
    max_risk = max_risk or env("MAX_RISK", "exec")

    if not max_rounds:
        try:
            max_rounds = int(env("MAX_ROUNDS", str(MAX_ROUNDS_PADRAO)) or MAX_ROUNDS_PADRAO)
        except ValueError:
            max_rounds = MAX_ROUNDS_PADRAO
    max_rounds = max(2, min(int(max_rounds), 60))

    tools = [t.as_openai() for t in reg.subset(max_risk=max_risk)]
    messages: list = history if history is not None else [{"role": "system", "content": SYSTEM}]
    messages.append({"role": "user", "content": user_text})

    def show(*parts: str) -> None:
        if verbose:
            print(*parts, flush=True)

    def step(tipo: str, nome: str = "", detalhe: str = "") -> None:
        if callable(on_step):
            try:
                on_step(tipo, nome, detalhe)
            except Exception:  # noqa: BLE001 — a UI nunca deve quebrar o agente
                pass

    show(f"🤖 modelo: {model} · {len(tools)} ferramentas expostas (risco ≤ {max_risk})")
    step("info", model, f"{len(tools)} ferramentas (risco ≤ {max_risk}) · até {max_rounds} rodadas")

    # consumo acumulado da conversa (a UI mostra no rodapé de cada resposta)
    uso_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    ferramentas_usadas: list[str] = []

    def _fechar_uso(rodadas: int) -> None:
        """Grava o consumo no histórico local (a aba de uso lê daí)."""
        try:
            from . import usage

            usage.registrar(
                model,
                uso_total["prompt_tokens"],
                uso_total["completion_tokens"],
                rodadas=rodadas,
                ferramentas=ferramentas_usadas,
            )
        except Exception:  # noqa: BLE001 — telemetria nunca derruba a tarefa
            pass

    for rodada in range(1, max_rounds + 1):
        ultima = rodada >= max_rounds

        # perto do fim, avisa o modelo para começar a fechar
        if max_rounds - rodada == 2:
            messages.append({"role": "system", "content":
                             "Restam poucas rodadas. Comece a concluir: se não der para terminar "
                             "tudo, entregue o que já tem e diga o que ficou pendente."})

        payload = {"model": model, "messages": messages, "tools": tools, "tool_choice": "auto"}
        if ultima:
            # A ÚLTIMA rodada não oferece ferramentas: obriga o modelo a ESCREVER a
            # resposta com o que já conseguiu, em vez de terminar no erro de limite.
            messages.append({"role": "system", "content":
                             "Última rodada: não há mais chamadas de ferramenta. Responda agora, "
                             "em português, com o resultado que você já obteve e o que ficou pendente."})
            payload["tools"] = []
            payload["tool_choice"] = "none"
        try:
            resp = _post(url, payload, api_key)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:400]
            dica = ""
            if "1010" in body:
                dica = ("\n💡 1010 = Cloudflare bloqueou a requisição (UA/IP). "
                        "Tente rodar de outra rede ou de um endpoint local (Ollama).")
            elif exc.code in (401, 403):
                dica = "\n💡 confira a chave em Configurações (ou SHARK_LLM_KEY) e se o modelo existe nesse provedor."
            msg = f"ERRO HTTP {exc.code} no LLM: {body}{dica}"
            step("erro", "llm", msg)
            return msg
        except Exception as exc:  # noqa: BLE001
            msg = f"ERRO chamando o LLM ({url}): {type(exc).__name__}: {exc}"
            step("erro", "llm", msg)
            return msg

        choices = resp.get("choices") or []
        if not choices:
            return f"ERRO: resposta sem 'choices': {json.dumps(resp)[:300]}"
        # soma o consumo desta rodada (nem todo provedor devolve 'usage')
        _uso = resp.get("usage") or {}
        for _k in uso_total:
            try:
                uso_total[_k] += int(_uso.get(_k) or 0)
            except (TypeError, ValueError):
                pass
        msg = choices[0].get("message", {})
        calls = msg.get("tool_calls") or []

        if not calls:
            text = _tool_result_text(msg)
            messages.append({"role": "assistant", "content": text})
            show("✅ pronto")
            # atenção: step(tipo, nome, detalhe) — o JSON vai no DETALHE
            step("tokens", "", json.dumps({
                **uso_total,
                "rodadas": rodada,
                "modelo": model,
                "ferramentas": ferramentas_usadas,
            }, ensure_ascii=False))
            _fechar_uso(rodada)
            step("resposta", "", text)
            return text

        if ultima:
            # não devia acontecer (mandamos tools=[]), mas nunca ficamos em silêncio
            texto = ("⚠️ Usei todas as rodadas sem fechar a resposta. "
                     "Me peça para continuar de onde parou.")
            _fechar_uso(rodada)
            step("erro", "loop", texto)
            return texto

        messages.append(msg)  # ecoa a decisão do modelo (inclui os tool_calls)
        for call in calls:
            fn = call.get("function") or {}
            name = fn.get("name", "")
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {}
            show(f"  🔧 [{rodada}] {name}({json.dumps(args, ensure_ascii=False)[:140]})")
            step("chamada", name, json.dumps(args, ensure_ascii=False))
            if name not in ferramentas_usadas:
                ferramentas_usadas.append(name)
            result = reg.dispatch(name, args if isinstance(args, dict) else {})
            show("     " + str(result).replace("\n", "\n     ")[:600])
            step("resultado", name, str(result))
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id", ""),
                "name": name,
                "content": str(result),
            })

    # rede de segurança: com a última rodada reservada para a resposta isto não
    # deveria ser alcançado, mas se for, o usuário recebe um convite a continuar
    limite = ("⚠️ Parei no limite de rodadas antes de fechar. "
              "Peça para continuar de onde parou e eu sigo.")
    _fechar_uso(max_rounds)
    step("erro", "loop", limite)
    return limite


__all__ = ["run_agent", "SYSTEM"]
