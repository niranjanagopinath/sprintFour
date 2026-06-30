# Conseal Batch Review — dev startup script
# Run this from the repo root: .\start.ps1

$ErrorActionPreference = "Stop"
$UV = "$env:USERPROFILE\.local\bin\uv.exe"

if (-not (Test-Path $UV)) {
    Write-Host "Installing UV..." -ForegroundColor Cyan
    irm https://astral.sh/uv/install.ps1 | iex
}

# Backend
Write-Host "Starting backend (Python 3.11, port 8000)..." -ForegroundColor Cyan
$backend = Start-Process -PassThru -NoNewWindow -FilePath $UV `
    -ArgumentList "run", "--directory", "backend", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--reload" `
    -WorkingDirectory $PSScriptRoot

# Frontend
Write-Host "Starting frontend (Vite, port 5173)..." -ForegroundColor Cyan
$frontend = Start-Process -PassThru -NoNewWindow -FilePath "npm" `
    -ArgumentList "run", "dev" `
    -WorkingDirectory "$PSScriptRoot\frontend"

Write-Host ""
Write-Host "  Backend:  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:5173"  -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop both servers." -ForegroundColor Yellow

try {
    Wait-Process -Id $backend.Id
} finally {
    Stop-Process -Id $backend.Id  -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -ErrorAction SilentlyContinue
}
