@echo off
cd /d %~dp0
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate
pip install -r requirements.txt
if not exist .env (
    copy .env.example .env
    echo.
    echo *** Edit the .env file and paste your Roboflow API key, then run this again. ***
    notepad .env
    pause
    exit /b
)
echo Starting API at http://127.0.0.1:8000
uvicorn main:app --host 127.0.0.1 --port 8000
