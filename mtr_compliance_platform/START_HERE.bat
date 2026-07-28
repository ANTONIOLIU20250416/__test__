@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [錯誤] 找不到 Python，請先安裝：
    echo   https://www.python.org/downloads/
    echo   安裝時務必勾選 "Add python.exe to PATH"，安裝完後再重新雙擊本檔案。
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
