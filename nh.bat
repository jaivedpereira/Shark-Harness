@echo off
REM 🦈 Shark Harness — atalho para rodar o `nh` no Windows.
REM   nh.bat info
REM   nh.bat tools
REM   nh.bat run "checa o sistema e cria um backup"
REM   nh.bat cron list
cd /d "%~dp0"
if not exist ".venv\Scripts\nh.exe" (
  echo ❌ Ainda nao instalado. Rode primeiro:  install.ps1
  echo.
  pause
  exit /b 1
)
".venv\Scripts\nh.exe" %*
