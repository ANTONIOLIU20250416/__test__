@echo off
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo [ERROR] Cannot find the venv folder here.
    echo Please run the setup steps first:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

where streamlit >nul 2>nul
if errorlevel 1 (
    echo [ERROR] streamlit is not installed in this venv.
    echo Run this once, then try again:
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

if "%ANTHROPIC_API_KEY%"=="" (
    echo NOTE: ANTHROPIC_API_KEY is not set as an environment variable.
    echo You can paste your API key into the sidebar of the web page instead.
    echo.
)

echo Starting the drawing checklist tool, your browser will open shortly...
echo To stop it later, come back to this window and press Ctrl+C, or just close this window.
echo.

streamlit run app.py

pause
