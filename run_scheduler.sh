#!/usr/bin/env bash
# Liga o agendador do Shark Harness em segundo plano.
#   ./run_scheduler.sh stop    → para
#   ./run_scheduler.sh status  → mostra se está rodando
#   ./run_scheduler.sh logs    → acompanha o log
set -uo pipefail

cd "$(dirname "$0")"
NH="./.venv/bin/nh"
[ -x "$NH" ] || NH="nh"
# a pasta é a MESMA do harness (config.json, jobs.json, audit.log vivem aqui)
NH_HOME="${SHARK_HOME:-${NH_HOME:-$HOME/.shark-harness}}"
PIDFILE="$NH_HOME/scheduler.pid"
LOGFILE="$NH_HOME/scheduler.log"
mkdir -p "$NH_HOME"

case "${1:-start}" in
  start)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "⏰ já está rodando (pid $(cat "$PIDFILE")) — use '$0 status'"
      exit 0
    fi
    if [ -f .env ]; then set -a; . ./.env; set +a; fi
    nohup "$NH" cron daemon --interval "${SHARK_TICK:-${NH_TICK:-20}}" >> "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    echo "⏰ agendador iniciado (pid $(cat "$PIDFILE")) — log em $LOGFILE"
    ;;
  stop)
    if [ -f "$PIDFILE" ]; then
      kill "$(cat "$PIDFILE")" 2>/dev/null && echo "⏹️  parado"
      rm -f "$PIDFILE"
    else
      echo "nada rodando"
    fi
    ;;
  status)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "✅ rodando (pid $(cat "$PIDFILE"))"
    else
      echo "❌ parado"
    fi
    "$NH" cron list
    ;;
  logs)
    tail -f "$LOGFILE"
    ;;
  *)
    echo "uso: $0 {start|stop|status|logs}"
    exit 1
    ;;
esac
