@echo off
echo ========================================================
echo Starting HCS-01 FastAPI Backend (Port 8000)
echo ========================================================
cd /d "%~dp0"
call .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
pause
