@echo off
echo Starting CoachEduAI Server...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.11 or later
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "python\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv python
)

REM Activate virtual environment
echo Activating virtual environment...
call python\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Try to start the main server first
echo Starting main server...
python main.py
if errorlevel 1 (
    echo.
    echo Main server failed, trying simple server...
    python simple_server.py
)

pause 