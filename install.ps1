# Shark Harness - instalador para Windows
#
#   Uso (PowerShell, dentro da pasta do projeto):
#       .\install.ps1
#       .\install.ps1 -WithMcp     # adiciona o servidor MCP
#
#   Se der erro de politica de execucao, rode antes:
#       Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#
# NOTA: este arquivo e 100% ASCII de proposito. O Windows PowerShell 5.1 le
# arquivos UTF-8 SEM BOM como ANSI, e caracteres como emoji, acento ou travessao
# viram bytes que quebram o parser (erro "Token '}' inesperado"). Sem acento, sem
# emoji, sem travessao = roda em qualquer PowerShell.

param([switch]$WithMcp)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

Write-Host ""
Write-Host "  SHARK HARNESS - instalando em $raiz" -ForegroundColor Cyan
Write-Host ""

# -- 1. achar o Python -----------------------------------------------------
$python = $null
foreach ($cand in @("python", "py", "python3")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $python = $cand; break }
}
if (-not $python) {
    Write-Host "  [X] Python nao encontrado." -ForegroundColor Red
    Write-Host ""
    Write-Host "      Instale o Python 3 em:  https://www.python.org/downloads/"
    Write-Host "      IMPORTANTE: na primeira tela do instalador marque a caixinha"
    Write-Host "      'Add python.exe to PATH' - depois FECHE e ABRA o PowerShell."
    Write-Host ""
    exit 1
}
$versao = (& $python --version) 2>&1
Write-Host "  [ok] $versao encontrado"

# -- 2. ambiente virtual ---------------------------------------------------
if (-not (Test-Path ".venv")) {
    Write-Host "  -> criando ambiente virtual (.venv)"
    & $python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [X] falhou ao criar o .venv" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  [ok] ambiente virtual ja existe"
}

$pip = Join-Path $raiz ".venv\Scripts\pip.exe"
$nh  = Join-Path $raiz ".venv\Scripts\nh.exe"

if (-not (Test-Path $pip)) {
    Write-Host "  [X] nao achei o pip dentro do .venv" -ForegroundColor Red
    Write-Host "      apague a pasta .venv e rode este instalador de novo."
    exit 1
}

# -- 3. instalar o pacote --------------------------------------------------
Write-Host "  -> instalando o Shark Harness"
& $pip install --quiet --upgrade pip
& $pip install --quiet -e .
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [X] falhou a instalacao do pacote" -ForegroundColor Red
    exit 1
}

# -- 4. MCP (opcional) -----------------------------------------------------
if ($WithMcp) {
    Write-Host "  -> instalando o SDK do MCP"
    & $pip install --quiet "mcp[cli]"
}

# -- 5. .env opcional ------------------------------------------------------
if ((-not (Test-Path ".env")) -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  [nota] criei um .env - abra e cole sua chave em SHARK_LLM_KEY"
}

# -- 6. confere se o comando respondeu -------------------------------------
if (Test-Path $nh) {
    & $nh --version
}

Write-Host ""
Write-Host "  PRONTO!" -ForegroundColor Green
Write-Host ""
Write-Host "  Teste:            .\nh.bat info"
Write-Host "  Ver ferramentas:  .\nh.bat tools"
Write-Host "  Interface web:    .\run_web.bat"
Write-Host "  Agente:           .\nh.bat run `"checa o sistema`""
Write-Host "  Atualizar:        .\atualizar.bat"
Write-Host ""
