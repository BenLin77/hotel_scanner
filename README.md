# Hotel Price Scanner

這是一個 Flask 網站，用於追蹤不同訂房網站的飯店價格。

## 功能

-   根據使用者指定的日期和地點搜尋飯店。
-   定期 (例如每兩小時) 從 Agoda、Hotels.com、Booking.com 等網站爬取房價。
-   以曲線圖顯示飯店價格的歷史區間。
-   可透過 `config/settings.yaml` 設定目標網站和爬取間隔。
-   提供追蹤和取消追蹤飯店價格的功能。
-   標示最低價格來源的網站。
-   爬蟲使用無痕模式。

## 設定

1.  複製 `.env.example` 為 `.env` 並設定 `FLASK_SECRET_KEY`。
    ```bash
    cp .env.example .env
    # 在 .env 中編輯 FLASK_SECRET_KEY
    ```
2.  安裝依賴套件：
    ```bash
    uv pip install -r requirements.txt
    ```
3.  設定 `config/settings.yaml`：
    -   `target_sites`: 要爬取的訂房網站列表。
    -   `crawl_interval_hours`: 爬取價格的間隔時間 (小時)。
    -   `webdriver`: Selenium WebDriver 的設定 (瀏覽器類型、是否無頭模式)。

## 初始化資料庫

```bash
uv flask db init  # 第一次執行時
uv flask db migrate -m "Initial migration"
uv flask db upgrade
```

## 執行應用程式

```bash
uv python run.py
```

然後在瀏覽器中開啟 `http://127.0.0.1:5000`。

## 專案結構

```
hotel_scanner/
├── app/                  # Flask 應用程式模組
│   ├── __init__.py       # 應用程式工廠
│   ├── models.py         # SQLAlchemy 資料庫模型
│   ├── routes.py         # 路由定義
│   ├── forms.py          # WTForms 表單定義
│   ├── services/         # 業務邏輯服務 (爬蟲、排程等)
│   │   ├── __init__.py
│   │   ├── scraper_service.py
│   │   └── scheduler_service.py
│   ├── static/           # 靜態檔案 (CSS, JavaScript, 圖片)
│   └── templates/        # Jinja2 模板
├── config/               # 設定檔目錄
│   └── settings.yaml
├── migrations/           # Flask-Migrate 資料庫遷移腳本
├── tests/                # 測試目錄 (可選)
├── .env                  # 環境變數 (用於 FLASK_SECRET_KEY 等)
├── .env.example          # 環境變數範例
├── .flaskenv             # Flask CLI 環境變數
├── run.py                # 應用程式進入點
├── requirements.txt      # Python 依賴套件
└── README.md             # 專案說明
```

## 待辦事項與優化建議

-   **使用者認證**: 加入使用者登入註冊功能，讓每個使用者可以管理自己的追蹤列表。
-   **錯誤處理與日誌**: 增強爬蟲的錯誤處理機制，並記錄詳細日誌。
-   **代理伺服器**: 為了避免 IP 被封鎖，可以整合代理伺服器池。
-   **CAPTCHA 處理**: 研究更進階的 CAPTCHA 繞過或處理機制 (如果需要)。
-   **非同步爬蟲**: 對於 I/O 密集的爬蟲任務，可以考慮使用 `asyncio` 和 `aiohttp` 提高效率。
-   **前端框架**: 如果需要更複雜的互動，可以考慮使用 Vue.js 或 React。
-   **API 端點**: 提供 API 端點，方便其他應用程式或服務整合。
-   **通知功能**: 當追蹤的飯店價格達到特定條件時 (例如降價)，透過 Email 或其他方式通知使用者。
-   **多語言支援**: 支援多種語言界面。
-   **測試覆蓋**: 編寫單元測試和整合測試，確保程式碼品質。
-   **部署**: 撰寫 Dockerfile 並考慮使用 Gunicorn + Nginx 部署。
-   **安全性**: 確保輸入驗證、防止 XSS、CSRF 等攻擊。
