# 圖面判讀 AI 代理 (Drawing QA Agent)

讀取工程圖面（PDF / PNG / JPG），用 Claude 判讀圖面上的**尺寸標註**與**量測要求**
（線性尺寸、直徑/半徑、角度、螺紋、GD&T 幾何公差、表面粗糙度、硬度等），
並自動產生一份可直接用於產品品質確認的 **Excel 檢核表**。

## 安裝

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # 判讀圖面需要呼叫 Claude API
```

## 使用方式

### 1. 判讀圖面並產生檢核表

```bash
python -m drawing_qa_agent analyze 圖面.pdf -o checklist.xlsx --inspector "Antonio"
```

- 支援 PDF（單次最多 5 頁）與 PNG/JPG/WEBP 圖片。
- 可加 `--save-json result.json`，把 Claude 判讀出的結構化資料另存一份，方便覆核或重跑。
- 可加 `--model` 指定模型（預設讀環境變數 `DRAWING_QA_MODEL`，否則用 `claude-sonnet-5`）。

### 2. 已有判讀結果 JSON，只想重新產生 Excel（不呼叫 API）

```bash
python -m drawing_qa_agent from-json result.json -o checklist.xlsx
```

### 3. 先看範例輸出格式

```bash
python -m drawing_qa_agent demo -o demo_checklist.xlsx
```

## 產出的 Excel 內容

- **圖面基本資料**：圖號、品名、材質、版次、未注公差說明、檢驗員、檢驗日期、判讀警示。
- **尺寸檢核表**：每一個尺寸/量測要求一列，欄位包含標稱值、上下公差、管制上下限、
  是否為關鍵尺寸、建議量測工具、3 組實測值欄位，以及會依實測值自動判定「合格 / 不合格 /
  需人工比對」的公式欄。合格會標綠、不合格會標紅，方便現場檢驗人員直接列印使用。

## 判讀邏輯與限制

- 判讀提示詞（`prompts.py`）要求 Claude 逐一列出圖面上所有標註尺寸與量測要求，
  並在無法確定時記錄在 `warnings`，而不是直接省略——所有輸出都應視為
  **AI 初判結果，需由品保工程師覆核後才能正式作為檢驗依據**。
- 若圖面標有整體「未注公差」表（如 ISO 2768），會記錄在 `drawing_info.general_tolerance`，
  並讓沒有單獨標公差的尺寸套用之。
- 目前一次判讀限制在 5 頁 PDF 以內；圖面複雜或页数較多建議拆分後分別判讀再合併 JSON。

## 程式結構

```
drawing_qa_agent/
  schema.py      資料模型 (Dimension / DrawingInfo / DrawingAnalysis)
  prompts.py      給 Claude 的判讀提示詞與輸出 JSON 格式定義
  extractor.py     呼叫 Claude vision 判讀圖面，含 PDF -> 圖片轉換
  checklist.py     用 openpyxl 把判讀結果轉成 Excel 檢核表
  cli.py           command line 介面 (analyze / from-json / demo)
tests/
  sample_analysis.json  範例判讀結果（球閥閥體），供 demo 與測試使用
  test_checklist.py     單元測試
```

## 測試

```bash
pytest tests/ -q
```
