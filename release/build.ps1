# Build the lattice CLI as a standalone binary for Windows.
#
# Usage:
#   .\release\build.ps1            # default build
#   .\release\build.ps1 -WithLLM   # include openai + anthropic SDKs
#
# Output: dist\lattice.exe

param(
    [switch]$WithLLM
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Root = Split-Path -Parent $ScriptDir

Write-Host "==> Ensuring build dependencies..."
pip install pyinstaller -q

if ($WithLLM) {
    Write-Host "==> Installing lattice with LLM extras..."
    pip install -e "$Root[llm]" -q
} else {
    Write-Host "==> Installing lattice..."
    pip install -e "$Root" -q
}

Write-Host "==> Building standalone binary..."
pyinstaller "$Root\release\lattice.spec" `
    --distpath "$Root\dist" `
    --workpath "$Root\build" `
    --noconfirm `
    --clean

$Binary = Join-Path $Root "dist\lattice.exe"
if (Test-Path $Binary) {
    $size = (Get-Item $Binary).Length / 1MB
    Write-Host ""
    Write-Host "==> Build complete!"
    Write-Host "    Binary: $Binary"
    Write-Host ("    Size:   {0:N1} MB" -f $size)
    Write-Host ""
    Write-Host "    Test:   $Binary --help"
} else {
    Write-Error "Build failed - binary not found at $Binary"
    exit 1
}
