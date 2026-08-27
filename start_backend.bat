@echo off
title HCS-01 FastAPI Backend (Port 8000)
echo ========================================================
echo Starting HCS-01 Policy Concierge Backend (Port 8000)
echo ========================================================
cd /d "%~dp0Backend"

if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
) else (
    python -m uvicorn app.main:app --reload --port 8000
)

pause
