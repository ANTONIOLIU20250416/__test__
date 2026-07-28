#!/bin/bash
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo ""
    echo "[錯誤] 找不到 Python，請先安裝："
    echo "  https://www.python.org/downloads/"
    echo "  安裝完後再重新雙擊本檔案。"
    echo ""
    read -p "按 Enter 鍵關閉視窗..."
    exit 1
fi

if ! command -v tesseract >/dev/null 2>&1; then
    echo ""
    echo "[提醒] 找不到 Tesseract OCR，掃描/照片證書將無法辨識文字。"
    echo "  如需辨識掃描證書，請安裝（終端機輸入）：brew install tesseract tesseract-lang"
    echo "  （純文字 PDF 或 .txt 檔不受影響，可照常使用）"
    echo ""
fi

if [ ! -d ".venv" ]; then
    echo "第一次啟動，正在設定環境，請稍候幾分鐘..."
    python3 -m venv .venv
    .venv/bin/pip install --quiet -r requirements.txt
    if [ $? -ne 0 ]; then
        echo ""
        echo "[錯誤] 安裝套件失敗，請確認網路連線後重新雙擊本檔案。"
        read -p "按 Enter 鍵關閉視窗..."
        exit 1
    fi
fi

( sleep 3; open http://127.0.0.1:8811 2>/dev/null || xdg-open http://127.0.0.1:8811 2>/dev/null ) &

echo ""
echo "啟動中... 瀏覽器會自動開啟 http://127.0.0.1:8811"
echo "要關閉程式時，直接關掉這個視窗即可（或按 Ctrl+C）。"
echo ""
.venv/bin/uvicorn app.main:app --port 8811
