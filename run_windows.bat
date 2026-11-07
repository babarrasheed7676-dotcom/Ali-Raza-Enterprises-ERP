@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 goto error
)
call ".venv\Scripts\activate.bat"
echo Installing/updating required packages...
python -m pip install --upgrade pip
if errorlevel 1 goto error
pip install -r requirements.txt
if errorlevel 1 goto error
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo.
  echo Created .env from .env.example.
  echo IMPORTANT: Edit .env and enter your PostgreSQL password, then run this file again.
  notepad .env
  pause
  exit /b 0
)
echo Starting Ali Raza Enterprises ERP at http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
if errorlevel 1 goto error
exit /b 0
:error
echo.
echo Setup did not complete. Read README.md and check that Python 3.11+ is installed.
pause
exit /b 1
