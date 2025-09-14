# Gemini 啟動說明

本文檔旨在說明如何啟動、設定及管理 Gemini 應用程式。

## 目錄
1. [基本啟動](#基本啟動)
2. [帶有參數的啟動](#帶有參數的啟動)
3. [檢查運行狀態](#檢查運行狀態)
4. [停止應用程式](#停止應用程式)
5. [日誌查看](#日誌查看)

---

### 基本啟動

這是最簡單的啟動方式，使用預設配置。

```bash
./gemini start
```

### 帶有參數的啟動

您可以透過傳遞參數來自訂 Gemini 的行為。

**範例：**

- **指定設定檔：**
  ```bash
  ./gemini start --config /path/to/your/config.toml
  ```

- **在前台運行（用於調試）：**
  ```bash
  ./gemini start --foreground
  ```

- **設定日誌級別：**
  ```bash
  ./gemini start --log-level debug
  ```

### 檢查運行狀態

要確認 Gemini 是否正在運行，請使用以下指令：

```bash
./gemini status
```

如果正在運行，您將會看到類似以下的輸出：
```
Gemini is running (PID: 12345)
```

### 停止應用程式

要停止正在運行的 Gemini 實例，請使用：

```bash
./gemini stop
```

### 日誌查看

日誌檔案對於問題排查非常重要。

- **即時查看日誌：**
  ```bash
  tail -f /var/log/gemini/gemini.log
  ```
  *(請將路徑替換為您的實際日誌路徑)*

---

若有任何問題，請參考官方文件或聯繫技術支援。
