@echo off
title HCS-01 Full Stack Launcher
echo ========================================================
echo Launching HCS-01 Backend ^& Frontend...
echo ========================================================

echo [1/2] Starting FastAPI Backend on Port 8000...
start "HCS-01 Backend (8000)" cmd /c "%~dp0start_backend.bat"

ping 127.0.0.1 -n 4 >nul

echo [2/2] Starting React Frontend on Port 8080...
start "HCS-01 Frontend (8080)" cmd /c "%~dp0start_frontend.bat"

echo.
echo Both services are starting!
echo Frontend will be accessible at: http://localhost:8080
echo Backend API Docs at:            http://localhost:8000/docs
echo ========================================================

