@echo off
setlocal enabledelayedexpansion

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH
    pause
    exit /b 1
)

REM Run the Python launcher with proper cleanup
python run.py %*

REM Preserve exit code
set EXIT_CODE=!errorlevel!

REM Only pause if no arguments were passed (interactive mode)
if "%~1"=="" (
    pause
)

exit /b !EXIT_CODE!
