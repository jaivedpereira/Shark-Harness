@echo off
REM 🦈 Shark Harness — abre a interface web (azul/preto com o tubarao)
REM   run_web.bat                    -> http://127.0.0.1:8787
REM   run_web.bat --all              -> expoe na rede local (imprime o token)
REM   run_web.bat --port 9000        -> outra porta
cd /d "%~dp0"
if not exist ".venv\Scripts\nh.exe" (
  echo ❌ Ainda nao instalado. Rode primeiro:  install.ps1
  echo.
  pause
  exit /b 1
)
echo.
echo   🦈 abrindo a interface do Shark Harness...
echo      (esta janela precisa ficar aberta; feche para parar)
echo.
".venv\Scripts\nh.exe" web %*
pause
