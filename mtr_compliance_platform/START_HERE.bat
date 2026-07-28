@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

python -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo.
    echo [錯誤] 沒有偵測到可用的 Python。
    echo 你的電腦目前只有 Windows 內建、會跳出「到 Microsoft Store 搜尋」的假指令，
    echo 還沒有安裝真正的 Python。
    echo.
    echo 請依下列步驟安裝：
    echo   1. 前往 https://www.python.org/downloads/ 下載安裝程式並執行
    echo   2. 安裝畫面最下方務必勾選 "Add python.exe to PATH"，再按安裝
    echo   3. 安裝完成後，重新雙擊本檔案
    echo   4. 如果還是出現同樣訊息，請重新開機一次再試
    echo.
    echo （如果你確定已經裝過 Python，可能是 Windows 的「App execution aliases」
    echo   把假指令排在前面：設定 -^> 應用程式 -^> 進階應用程式設定 -^>
    echo   應用程式執行別名，把 python.exe / python3.exe 兩個開關關掉再試一次）
    echo.
    pause
    exit /b 1
)

where tesseract >nul 2>nul
if errorlevel 1 (
    echo.
    echo [提醒] 找不到 Tesseract OCR，掃描/照片證書將無法辨識文字。
    echo   如需辨識掃描證書，請安裝：
    echo   https://github.com/UB-Mannheim/tesseract/wiki
    echo   （純文字 PDF 或 .txt 檔不受影響，可照常使用）
    echo.
)

if not exist ".venv" (
    echo 第一次啟動，正在設定環境，請稍候幾分鐘...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo [錯誤] 建立虛擬環境失敗，請確認 Python 是否安裝完整後重新雙擊本檔案。
        pause
        exit /b 1
    )
    ".venv\Scripts\pip" install --quiet -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [錯誤] 安裝套件失敗，請確認網路連線後重新雙擊本檔案。
        pause
        exit /b 1
    )
)

start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8811"

echo.
echo 啟動中... 瀏覽器會自動開啟 http://127.0.0.1:8811
echo 要關閉程式時，直接關掉這個黑色視窗即可。
echo.
".venv\Scripts\uvicorn" app.main:app --port 8811

pause
