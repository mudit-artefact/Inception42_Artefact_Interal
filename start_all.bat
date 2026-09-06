@echo off
title DalilHR Full Stack Launcher (Backend + Frontend)
echo ========================================================
echo Launching DalilHR Backend (Port 8000) ^& Frontend...
echo ========================================================

echo [1/2] Starting DalilHR Concierge Backend on Port 8000...
start "DalilHR Backend (8000)" cmd /c "%~dp0start_backend.bat"

ping 127.0.0.1 -n 3 >nul

echo [2/2] Starting React Frontend on Port 8080...
start "DalilHR Frontend (8080)" cmd /c "%~dp0start_frontend.bat"

echo.
echo Services are starting!
echo Frontend Portal:      http://localhost:8080
echo Backend API Docs:     http://localhost:8000/docs
echo ========================================================

