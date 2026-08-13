@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo [錯誤] 找不到 venv 虛擬環境。
    echo 請先依照 README 的安裝步驟執行：
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

if "%ANTHROPIC_API_KEY%"=="" (
    echo 提示：目前沒有偵測到 ANTHROPIC_API_KEY 環境變數，
    echo 稍後開啟的網頁左側可以直接貼上 API 金鑰使用。
    echo.
)

echo 正在啟動「圖面判讀檢核表產生器」，瀏覽器會自動開啟...
echo 若要關閉程式，回到這個黑色視窗按 Ctrl+C，或直接關閉此視窗。
echo.

streamlit run app.py

pause
