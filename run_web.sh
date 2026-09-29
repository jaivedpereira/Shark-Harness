#!/usr/bin/env bash
# Sobe a interface do Shark Harness carregando as chaves de um .env (se existir).
#   ./run_web.sh            → http://127.0.0.1:8787
#   ./run_web.sh --all      → expõe na rede (imprime o token)
set -uo pipefail

cd "$(dirname "$0")"
set -a
[ -f .env ] && . ./.env
[ -f "$HOME/.hermes/.env" ] && . "$HOME/.hermes/.env"   # conveniência: reaproveita chaves existentes
set +a

# apelidos: aceita OPENROUTER_API_KEY / OPENCODE_ZEN_API_KEY como SHARK_LLM_KEY
export SHARK_LLM_KEY="${SHARK_LLM_KEY:-${OPENROUTER_API_KEY:-${NH_LLM_KEY:-}}}"
export SHARK_LLM_URL="${SHARK_LLM_URL:-${NH_LLM_URL:-https://openrouter.ai/api/v1/chat/completions}}"
export SHARK_LLM_MODEL="${SHARK_LLM_MODEL:-${NH_LLM_MODEL:-nvidia/nemotron-3.5-lightning:free}}"

NH="./.venv/bin/nh"
[ -x "$NH" ] || NH="nh"

exec "$NH" web "$@"
