#!/usr/bin/env bash
# 🦈 Shark Harness — atualiza pelo git e já sobe a interface.
#   Uso:  ./atualizar.sh
#         ./atualizar.sh --sem-web    (só atualiza, não abre a interface)
set -uo pipefail
cd "$(dirname "$0")" || exit 1

ABRIR=1
[ "${1:-}" = "--sem-web" ] && ABRIR=0

echo
echo "  ============================================"
echo "   SHARK HARNESS — ATUALIZANDO"
echo "  ============================================"
echo

# 1) git instalado?
if ! command -v git >/dev/null 2>&1; then
  echo "  [X] O Git não está instalado."
  echo "      Termux/Linux:  pkg install git"
  echo "      (ou: apt install git  ·  sudo dnf install git)"
  exit 1
fi

# 2) a pasta veio de um clone?
if [ ! -d .git ]; then
  echo "  [!] Esta pasta não foi clonada com git (não tem .git),"
  echo "      então não dá para baixar atualização por aqui."
  echo
  echo "  Clone de uma vez e nunca mais se preocupe:"
  echo
  echo "      cd ~"
  echo "      git clone https://github.com/jaivedpereira/Shark-Harness.git"
  echo "      cd Shark-Harness"
  echo "      bash install.sh"
  exit 1
fi

# 3) alterações locais? avisa em vez de brigar com o git
if [ -n "$(git status --porcelain)" ]; then
  echo "  [!] Você tem alterações locais em arquivos do projeto:"
  git status --porcelain | head -8 | sed 's/^/       /'
  echo
  echo "  Para descartar e atualizar mesmo assim:"
  echo "      git checkout ."
  echo "      ./atualizar.sh"
  exit 1
fi

# 4) baixa a versão nova
echo "  Baixando a versão mais nova..."
echo
if ! git pull --ff-only; then
  echo
  echo "  [X] O git não conseguiu atualizar. Motivos comuns:"
  echo "      - sem internet agora"
  echo "      - o histórico local divergiu  (rode: git checkout .)"
  echo "      - falta configurar o acesso ao repositório"
  exit 1
fi

echo
echo "  ============================================"
echo "   PRONTO! Sua chave, seu catálogo de modelos"
echo "   e suas sessões não se perdem — ficam em ~/.shark-harness/"
echo "  ============================================"
echo

# 5) sobe a interface
NH="./.venv/bin/nh"
if [ ! -x "$NH" ]; then
  echo "  [!] Ainda falta instalar o ambiente Python. Rode UMA vez:"
  echo
  echo "      bash install.sh        (Linux/Termux)"
  echo "      (no Termux NÃO instale mcp[cli] — não compila)"
  exit 0
fi

if [ "$ABRIR" -eq 1 ]; then
  echo "  Abrindo a interface... (esta janela precisa ficar aberta)"
  echo
  exec "$NH" web
fi

echo "  Para abrir:  ./run_web.sh"
