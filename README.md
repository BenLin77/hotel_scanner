# Hotel Price Scanner

這是一個進階的 Flask 網站，用於追蹤不同訂房網站的飯店價格，具備強大的爬蟲功能和完整的監控系統。

## ✨ 主要功能

### 核心功能
- 🏨 **多站點價格追蹤**: 支援 Agoda、Booking.com、Hotels.com 等主流訂房網站
- 📅 **靈活搜尋條件**: 根據使用者指定的日期、地點和房間需求搜尋飯店
- ⏰ **自動定期爬取**: 可設定每 2 小時自動爬取最新價格
- 📊 **視覺化圖表**: 以曲線圖顯示飯店價格的歷史變化趨勢
- 💰 **最低價提醒**: 自動標示最低價格來源網站

### 進階功能
- 🛡️ **反檢測技術**: 使用 undetected-chromedriver 和隨機 User-Agent
- 🔄 **智能重試機制**: 指數退避重試，提高爬取成功率
- 🌐 **代理池支援**: 支援 HTTP/SOCKS5 代理輪換，避免 IP 封鎖
- 📈 **效能監控**: 即時監控爬取效能和成功率
- 🚨 **智能警報**: 當爬取失敗率過高時自動發送通知
- 💾 **資料優化**: 批次處理和快取機制，提升資料庫效能

## 🚀 快速開始

### 1. 環境準備

```bash
# 複製專案
git clone <your-repo-url>
cd hotel_scanner

# 設定環境變數
cp .env.example .env
# 編輯 .env 檔案，設定 FLASK_SECRET_KEY

# 安裝依賴套件
uv pip install -r requirements.txt
```

### 2. 設定配置

編輯 `config/settings.yaml` 來自訂您的爬蟲設定：

```yaml
# 基本爬蟲設定
crawl_interval_hours: 2        # 爬取間隔（小時）
max_concurrent_requests: 3     # 最大並發數

# 反檢測設定
anti_detection:
  random_user_agent: true      # 隨機 User-Agent
  simulate_human_behavior: true # 模擬人類行為
  random_delays: true          # 隨機延遲

# 代理設定（可選）
proxy_settings:
  enabled: false               # 啟用代理池
  proxies:
    - "http://proxy1:8080"
    - "socks5://proxy2:1080"
```

### 3. 初始化資料庫

```bash
uv flask db init              # 第一次執行
uv flask db migrate -m "Initial migration"
uv flask db upgrade
```

### 4. 啟動應用程式

```bash
uv python run.py
```

訪問 `http://127.0.0.1:5000` 開始使用！

## 📁 專案結構

```
hotel_scanner/
├── app/                           # Flask 應用程式核心
│   ├── __init__.py               # 應用程式工廠
│   ├── models.py                 # SQLAlchemy 資料模型
│   ├── routes.py                 # 路由定義
│   ├── forms.py                  # WTForms 表單
│   ├── services/                 # 業務邏輯服務
│   │   ├── scraper_service.py    # 改進的爬蟲服務
│   │   ├── enhanced_scraper.py   # 增強版爬蟲（包含並發）
│   │   ├── scheduler_service.py  # 排程服務
│   │   └── scrapers/            # 專門爬蟲模組
│   │       ├── booking_scraper.py
│   │       ├── agoda_scraper.py
│   │       └── hotels_scraper.py
│   ├── utils/                    # 輔助工具
│   │   ├── scraper_helpers.py    # 爬蟲輔助工具
│   │   └── monitoring.py         # 監控和效能追蹤
│   ├── static/                   # 靜態檔案
│   └── templates/                # Jinja2 模板
├── config/                       # 設定檔
│   └── settings.yaml            # 主要設定檔
├── logs/                        # 日誌檔案
├── migrations/                  # 資料庫遷移腳本
├── .env                        # 環境變數
├── run.py                      # 應用程式進入點
└── requirements.txt            # Python 依賴套件
```

## 🔧 核心改善功能

### 1. 反爬蟲檢測
- **undetected-chromedriver**: 避免被網站檢測為機器人
- **隨機 User-Agent**: 模擬不同瀏覽器和裝置
- **人類行為模擬**: 隨機滾動、點擊和延遲
- **視窗大小隨機化**: 避免被識別為自動化工具

### 2. 重試和錯誤處理
- **指數退避重試**: 使用 tenacity 庫實現智能重試
- **特定錯誤重試**: 只對網路錯誤和超時進行重試
- **錯誤分類**: 區分臨時錯誤和永久錯誤
- **優雅降級**: 當某個網站失敗時繼續爬取其他網站

### 3. 效能優化
- **並發爬取**: 支援多線程同時爬取不同網站
- **連接池**: 重用 HTTP 連接，減少建立連接的開銷
- **批次資料庫操作**: 減少資料庫 I/O 次數
- **智能快取**: 避免重複爬取相同資料

### 4. 監控和警報
- **即時效能監控**: 追蹤爬取成功率、響應時間等指標
- **自動警報**: 當錯誤率超過閾值時發送通知
- **歷史統計**: 保存爬取歷史，分析長期趨勢
- **健康檢查**: 定期檢查各網站的可用性

## 🛠️ 進階配置

### 代理設定
```yaml
proxy_settings:
  enabled: true
  rotation: true
  proxies:
    - "http://username:password@proxy1:8080"
    - "socks5://proxy2:1080"
  proxy_timeout: 30
```

### 通知設定
```yaml
notifications:
  email:
    enabled: true
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    username: "your-email@gmail.com"
    password: "your-app-password"
    recipients: ["admin@example.com"]
    
  discord:
    enabled: true
    webhook_url: "https://discord.com/api/webhooks/..."
```

### 監控設定
```yaml
monitoring:
  enabled: true
  metrics_interval: 300
  alert_thresholds:
    error_rate: 0.1        # 錯誤率超過 10% 時警報
    response_time: 30      # 響應時間超過 30 秒時警報
```

## 📊 使用範例

### 基本使用
1. 在網站首頁輸入搜尋條件（地點、入住/退房日期）
2. 點擊「開始追蹤」按鈕
3. 系統會立即進行一次爬取，並設定定期爬取排程
4. 在結果頁面查看價格趨勢圖表

### API 使用
```python
from app.services.enhanced_scraper import EnhancedScraperService

# 初始化爬蟲
config = load_config()
scraper = EnhancedScraperService(config)

# 爬取單一請求
results = scraper.scrape_single_request(search_request, config)

# 並發爬取多個請求
results = scraper.scrape_with_concurrency(search_requests, config)
```

## 🔍 故障排除

### 常見問題

1. **ChromeDriver 相關錯誤**
   ```bash
   # 更新 ChromeDriver
   uv pip install --upgrade webdriver-manager
   ```

2. **代理連接失敗**
   - 檢查代理伺服器是否正常運作
   - 確認代理認證資訊正確
   - 嘗試使用不同的代理伺服器

3. **爬取成功率低**
   - 增加延遲時間範圍
   - 啟用代理池
   - 檢查目標網站是否有變更

4. **記憶體使用過多**
   - 減少並發數量
   - 啟用批次處理
   - 定期重啟 WebDriver

## 📈 效能建議

1. **爬取頻率**: 建議不要設定過於頻繁的爬取間隔（最少 2 小時）
2. **並發數量**: 根據您的伺服器效能調整 `max_concurrent_requests`
3. **代理使用**: 在大量爬取時建議使用代理池
4. **監控設定**: 定期檢查監控面板，及時發現問題

## 🤝 貢獻指南

歡迎提交 Issue 和 Pull Request！請確保：
- 程式碼符合 PEP 8 規範
- 新功能包含適當的測試
- 更新相關文檔

## 📄 授權條款

本專案採用 MIT 授權條款。

## 🆙 升級記錄

### v2.0.0 (最新)
- ✅ 新增反爬蟲檢測功能
- ✅ 實作智能重試機制
- ✅ 加入效能監控系統
- ✅ 支援代理池輪換
- ✅ 優化資料庫效能
- ✅ 完善錯誤處理機制

### v1.0.0
- ✅ 基本爬蟲功能
- ✅ Flask 網站框架
- ✅ 資料庫儲存
- ✅ 簡單排程功能
