@echo off
title HCS-01 React Frontend (Port 8080)
echo ========================================================
echo Starting HCS-01 Policy Concierge React Frontend (Port 8080)
echo ========================================================
cd /d "%~dp0Frontend"

if exist "%LOCALAPPDATA%\Programs\node-v22.14.0-win-x64\node.exe" (
    set "PATH=%LOCALAPPDATA%\Programs\node-v22.14.0-win-x64;%PATH%"
)

call npm.cmd run dev
pause
