param([ValidateRange(1024,65535)][int]$Port = 8765)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Python environment missing. See README.md for setup.' }
Write-Host "Fieldwise: http://127.0.0.1:$Port — press Ctrl+C to stop."
& $python -m uvicorn fieldwise.app:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
