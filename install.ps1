# 🦈 Shark Harness — instalador para Windows
#
#   Uso (PowerShell, dentro da pasta do projeto):
#       .\install.ps1
#       .\install.ps1 -WithMcp     # adiciona o servidor MCP
#
#   Se der erro de política de execução, rode antes:
#       Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

param([switch]$WithMcp)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

Write-Host ""
Write-Host "  🦈  SHARK HARNESS — instalando em $raiz" -ForegroundColor Cyan
Write-Host ""

# ── 1. achar o Python ──────────────────────────────────────────────────────
$python = $null
foreach ($cand in @("python", "py", "python3")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $python = $cand; break }
}
if (-not $python) {
    Write-Host "  ❌ Python não encontrado." -ForegroundColor Red
    Write-Host ""
    Write-Host "     Instale o Python 3 em:  https://www.python.org/downloads/"
    Write-Host "     ⚠️  Na primeira tela do instalador MARQUE a caixinha"
    Write-Host "         'Add python.exe to PATH' — depois feche e reabra o PowerShell."
    exit 1
}
$versao = (& $python --version) 2>&1
Write-Host "  ✅ $versao encontrado"

# ── 2. ambiente virtual ────────────────────────────────────────────────────
if (-not (Test-Path ".venv")) {
    Write-Host "  → criando ambiente virtual (.venv)"
    & $python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ❌ falhou ao criar o .venv" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  ✅ ambiente virtual já existe"
}

$pip = Join-Path $raiz ".venv\Scripts\pip.exe"
$nh  = Join-Path $raiz ".venv\Scripts\nh.exe"

# ── 3. instalar o pacote ───────────────────────────────────────────────────
Write-Host "  → instalando o Shark Harness"
& $pip install --quiet --upgrade pip
& $pip install --quiet -e .
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ falhou a instalação do pacote" -ForegroundColor Red
    exit 1
}

# ── 4. MCP (opcional) ──────────────────────────────────────────────────────
if ($WithMcp) {
    Write-Host "  → instalando o SDK do MCP"
    & $pip install --quiet "mcp[cli]"
}

# ── 5. .env opcional ───────────────────────────────────────────────────────
if ((-not (Test-Path ".env")) -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  📝 criei um .env — abra e cole sua chave do LLM em SHARK_LLM_KEY"
}

Write-Host ""
Write-Host "  ✅ PRONTO!" -ForegroundColor Green
Write-Host ""
Write-Host "  Teste:            .\nh.bat info"
Write-Host "  Ver ferramentas:  .\nh.bat tools"
Write-Host "  Interface web:    .\run_web.bat"
Write-Host "  Agente:           .\nh.bat run `"checa o sistema`""
Write-Host ""
