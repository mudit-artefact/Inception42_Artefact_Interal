@echo off
title Client Presentation Launcher (HCS-01 + HCS-11)
echo ====================================================================
echo Launching Full Presentation Suite:
echo   1. Dalil / Bayan (HCS-01) -> http://localhost:8080
echo   2. School Verification (HCS-11) -> http://localhost:8081
echo ====================================================================

echo [1/2] Starting Dalil Concierge (HCS-01) on Port 8000 & 8080...
start "DalilHR Full Stack" cmd /c "%~dp0start_all.bat"

ping 127.0.0.1 -n 3 >nul

echo [2/2] Starting School Verification (HCS-11) on Port 8001 & 8081...
if exist "d:\hcs-11-verification\start_hcs11_all.bat" (
    start "HCS-11 Full Stack" cmd /c "d:\hcs-11-verification\start_hcs11_all.bat"
)

echo.
echo ====================================================================
echo PRESENTATION READY!
echo Tab 1 (Dalil / Bayan Concierge):    http://localhost:8080
echo Tab 2 (School Verification Portal): http://localhost:8081
echo Tab 2 (HR Reviewer Dashboard):     http://localhost:8081/?as=reviewer
echo ====================================================================
