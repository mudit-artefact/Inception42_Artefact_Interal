@echo off
echo ========================================================
echo Starting HCS-01 Streamlit Frontend (Port 8501)
echo ========================================================
cd /d "%~dp0"
call .venv\Scripts\python.exe -m streamlit run ui/app.py
pause
