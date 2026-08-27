@echo off
title HCS-01 Full Stack Launcher
echo ========================================================
echo Launching HCS-01 Backend & Frontend...
echo ========================================================

echo [1/2] Starting FastAPI Backend on Port 8000...
start "HCS-01 Backend (8000)" cmd /c "%~dp0start_backend.bat"

timeout /t 3 /nobreak >nul

echo [2/2] Starting React Frontend on Port 5173...
start "HCS-01 Frontend (5173)" cmd /c "%~dp0start_frontend.bat"

echo.
echo Both services are starting!
echo Frontend will be accessible at: http://localhost:5173
echo Backend API Docs at:            http://localhost:8000/docs
echo ========================================================
