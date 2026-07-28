@echo off
setlocal
cd /d "%~dp0"

python -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Python was not found, or the "python" command is not working.
    echo.
    echo Please install Python:
    echo   1. Go to https://www.python.org/downloads/ and run the installer
    echo   2. On the first screen, check the box "Add python.exe to PATH"
    echo   3. After installing, close this window and double-click this file again
    echo   4. If it still shows this message, restart your computer and try once more
    echo.
    echo See the Chinese setup guide file included in this folder for details.
    echo.
    pause
    exit /b 1
)

where tesseract >nul 2>nul
if errorlevel 1 (
    echo.
    echo [NOTE] Tesseract OCR was not found. Scanned or photographed certificates
    echo   cannot be read yet. To enable that, install it from:
    echo   https://github.com/UB-Mannheim/tesseract/wiki
    echo   ^(Plain digital PDFs or .txt files are not affected and work fine now.^)
    echo.
)

if not exist ".venv" (
    echo First-time setup - this may take a few minutes, please wait...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo [ERROR] Could not create the Python virtual environment.
        echo   Please check your Python installation and try again.
        pause
        exit /b 1
    )
    ".venv\Scripts\pip" install --quiet -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Installing required packages failed.
        echo   Please check your internet connection and double-click this file again.
        pause
        exit /b 1
    )
)

start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8811"

echo.
echo Starting... your browser will open automatically at http://127.0.0.1:8811
echo To stop the program later, just close this window.
echo.
".venv\Scripts\uvicorn" app.main:app --port 8811

pause
