@echo off
REM  Shark Harness - agendador de tarefas no Windows
REM   run_scheduler.bat          -> liga o agendador (janela minimizada)
REM   run_scheduler.bat stop     -> para
REM   run_scheduler.bat status   -> mostra as tarefas
cd /d "%~dp0"
if not exist ".venv\Scripts\nh.exe" (
  echo [X] Ainda nao instalado. Rode primeiro:  install.ps1
  pause
  exit /b 1
)

if /i "%~1"=="stop" (
  taskkill /IM nh.exe /F >nul 2>&1
  echo [ok] agendador parado (se estava rodando)
  exit /b 0
)

if /i "%~1"=="status" (
  ".venv\Scripts\nh.exe" cron list
  exit /b 0
)

echo ligando o agendador em segundo plano...
start "shark-scheduler" /min ".venv\Scripts\nh.exe" cron daemon
echo [ok] rodando minimizado. Para parar:  run_scheduler.bat stop
".venv\Scripts\nh.exe" cron list
pause
