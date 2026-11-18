@echo off
echo Starting RØVE backend and frontend...
cd /d "%~dp0backend\backend"
if not exist .venv (
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
) 
start "ROVE backend" cmd /k "cd /d %~dp0backend\backend && call .venv\Scripts\activate.bat && uvicorn app.main:app --port 8765 --reload"
cd /d "%~dp0frontend\frontend"
if not exist node_modules call npm install
start "ROVE frontend" cmd /k "cd /d %~dp0frontend\frontend && npm run dev"
timeout /t 8 >nul
start http://localhost:5173
