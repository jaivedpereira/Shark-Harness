@echo off
chcp 65001 >nul
REM 🦈 Shark Harness — atualiza o projeto pelo Git e ja sobe a interface.
REM   Basta dar dois cliques neste arquivo.
cd /d "%~dp0"

echo.
echo   ============================================
echo    SHARK HARNESS - ATUALIZANDO
echo   ============================================
echo.

REM 1) o git esta instalado?
where git >nul 2>nul
if errorlevel 1 (
  echo   [X] O Git nao esta instalado nesta maquina.
  echo.
  echo   Instale com este comando (depois FECHE e ABRA o terminal de novo):
  echo.
  echo       winget install Git.Git
  echo.
  echo   Ou baixe de: https://git-scm.com/download/win
  echo.
  pause
  exit /b 1
)

REM 2) a pasta veio de um clone do git?
if not exist ".git" (
  echo   [!] Esta pasta nao foi clonada com Git (nao tem a pasta .git^),
  echo       entao nao da para baixar atualizacao por aqui.
  echo.
  echo   Clonando na pasta de usuario, de uma vez por todas:
  echo.
  cd /d "%USERPROFILE%"
  git clone https://github.com/jaivedpereira/Shark-Harness.git
  if errorlevel 1 (
    echo.
    echo   [X] Nao consegui clonar. Confira a internet e tente de novo.
    pause
    exit /b 1
  )
  echo.
  echo   [OK] Baixado em: %USERPROFILE%\Shark-Harness
  echo.
  echo   Agora entre na pasta nova e rode o install.ps1 UMA vez:
  echo       cd %USERPROFILE%\Shark-Harness
  echo       .\install.ps1
  echo.
  pause
  exit /b 0
)

REM 3) mexeu no projeto a mao? avisa em vez de brigar com o git
git status --porcelain > "%TEMP%\shark_status.txt"
for %%A in ("%TEMP%\shark_status.txt") do set TAM=%%~zA
del "%TEMP%\shark_status.txt" >nul 2>nul
if not "%TAM%"=="0" (
  echo   [!] Voce tem alteracoes locais em arquivos do projeto.
  echo       O git nao vai atualizar por cima delas.
  echo.
  echo   Para descartar e atualizar mesmo assim, rode:
  echo       git checkout .
  echo       nh atualizar
  echo.
  pause
  exit /b 1
)

REM 4) o pulo do gato: baixa a versao nova
echo   Baixando a versao mais nova...
echo.
git pull --ff-only
if errorlevel 1 (
  echo.
  echo   [X] O git nao conseguiu atualizar. Motivos comuns:
  echo       - sem internet agora
  echo       - o historico local divergiu  ^(rode: git checkout .^)
  echo       - o repositorio pediu usuario/senha
  echo.
  pause
  exit /b 1
)

echo.
echo   ============================================
echo    PRONTO! Sua chave, seu catalogo de modelos
echo    e suas sessoes NAO se perdem nada disso.
echo   ============================================
echo.

REM 5) ja pergunta se quer abrir a interface
if not exist ".venv\Scripts\nh.exe" (
  echo   [!] Ainda falta instalar o ambiente Python. Rode UMA vez:
  echo.
  echo       .\install.ps1
  echo.
  pause
  exit /b 0
)

choice /c SN /m "   Abrir a interface agora (S/N)"
if errorlevel 2 exit /b 0

echo.
echo   Abrindo... ^(esta janela precisa ficar aberta^)
echo.
".venv\Scripts\nh.exe" web
pause
