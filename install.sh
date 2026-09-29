#!/usr/bin/env bash
# Instala o Shark Harness e (opcionalmente) o SDK do MCP.
#   ./install.sh          → núcleo + CLI (funciona no Termux)
#   ./install.sh --with-mcp → adiciona o servidor MCP (NÃO no Termux)
set -euo pipefail

cd "$(dirname "$0")"
echo "🧰 instalando Shark Harness em $(pwd)"

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null || { echo "❌ python3 não encontrado"; exit 1; }

if [ ! -d .venv ]; then
  echo "→ criando venv"
  "$PY" -m venv .venv
fi

echo "→ instalando o pacote (modo editável)"
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -e .

if [ "${1:-}" = "--with-mcp" ]; then
  if [ -d /data/data/com.termux ]; then
    echo "⚠️  Termux detectado: pulando mcp[cli] (rpds-py não compila em Android)."
    echo "    Use o MCP no PC. A CLI e o agente funcionam sem ele."
  else
    echo "→ instalando o SDK do MCP"
    ./.venv/bin/pip install -q "mcp[cli]"
  fi
fi

echo
echo "✅ pronto. Teste com:"
echo "   ./.venv/bin/nh info"
echo "   ./.venv/bin/nh tools"
echo "   ./.venv/bin/python tests/test_core.py"
echo
echo "Dica: para o comando global, rode"
echo "   ln -s \"\$(pwd)/.venv/bin/nh\" ~/.local/bin/nh"
