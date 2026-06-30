@echo off
title Conseal Backend
cd /d "%~dp0backend"

echo [1/3] Freeing port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 "') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo [2/3] Starting backend on http://127.0.0.1:8000 ...
echo.
"%USERPROFILE%\.local\bin\uv.exe" run uvicorn main:app --host 127.0.0.1 --port 8001 --reload
pause
