@echo off
REM arcade-heartbeat launcher
REM Activates virtual environment and starts the application

echo Starting arcade-heartbeat...
echo.

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found!
    echo.
    echo Please run these commands first:
    echo   py -3.11 -m venv venv
    echo   .\venv\Scripts\Activate
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM Activate venv and run
call venv\Scripts\activate.bat
python -m heartbeat

REM Keep window open on error
if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
