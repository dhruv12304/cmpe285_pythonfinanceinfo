@echo off
REM Run script for Python Finance Info (Windows).
REM
REM   run.bat                 interactive mode
REM   run.bat ADBE MSFT       look up these symbols once and exit
REM   run.bat --test          run the unit tests (no internet needed)

setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Error: Python was not found. Install Python 3.9+ from https://www.python.org/downloads/
    exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"
if errorlevel 1 (
    echo Error: Python 3.9 or newer is required.
    exit /b 1
)

if "%~1"=="--test" goto :test

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 exit /b 1
)

fc /b requirements.txt .venv\.requirements.installed >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies ...
    .venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        .venv\Scripts\python.exe -c "import yfinance" >nul 2>nul
        if errorlevel 1 (
            echo Error: could not install dependencies. Check your internet connection and try again.
            exit /b 1
        )
        echo Warning: could not update dependencies. Using the installed versions.
    ) else (
        copy /y requirements.txt .venv\.requirements.installed >nul
    )
)

.venv\Scripts\python.exe main.py %*
exit /b %errorlevel%

:test
python -m unittest discover -s tests -v
exit /b %errorlevel%
