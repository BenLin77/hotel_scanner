# app/services/scraper_service.py
# 爬蟲相關的邏輯將會放在這裡
# 例如：
# - 初始化 Selenium WebDriver
# - 針對不同網站的爬取函數 (agoda_scraper, booking_scraper 等)
# - 解析 HTML 內容並提取價格、飯店名稱等資訊
# - 錯誤處理和重試機制

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
from datetime import datetime, timezone
from ..models import HotelPrice
from .. import db # 確保能從 app import db

def get_webdriver(config):
    """根據設定初始化並返回一個 Selenium WebDriver 實例"""
    browser_type = config.get('webdriver', {}).get('browser', 'chrome').lower()
    headless = config.get('webdriver', {}).get('headless', True)
    # driver_path = config.get('webdriver', {}).get('driver_executable_path') # 暫不使用，webdriver-manager 會自動處理

    options = None
    driver = None

    try:
        if browser_type == 'chrome':
            options = webdriver.ChromeOptions()
            if headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox') # 在某些 Linux 環境下需要
            options.add_argument('--disable-dev-shm-usage') # 克服共享內存限制
            options.add_argument('--disable-gpu') # 在無頭模式下通常建議禁用 GPU
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
            options.add_argument("--incognito") # 無痕模式
            # service = ChromeService(executable_path=driver_path) if driver_path else ChromeService(ChromeDriverManager().install())
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        elif browser_type == 'firefox':
            options = webdriver.FirefoxOptions()
            if headless:
                options.add_argument('--headless')
            options.add_argument("--private") # Firefox 的無痕模式
            # service = FirefoxService(executable_path=driver_path) if driver_path else FirefoxService(GeckoDriverManager().install())
            service = FirefoxService(GeckoDriverManager().install())
            driver = webdriver.Firefox(service=service, options=options)
        else:
            raise ValueError(f"不支援的瀏覽器類型: {browser_type}")
        
        driver.set_page_load_timeout(60) # 設置頁面加載超時
        return driver
    except Exception as e:
        print(f"初始化 WebDriver 失敗 ({browser_type}): {e}")
        if driver:
            driver.quit()
        return None

def scrape_prices_for_request(search_request, app_config):
    """針對一個 SearchRequest 爬取所有設定網站的價格"""
    print(f"開始爬取請求 {search_request.id}: {search_request.location} ({search_request.check_in_date} - {search_request.check_out_date})")
    
    driver = get_webdriver(app_config)
    if not driver:
        print(f"無法為請求 {search_request.id} 取得 WebDriver，跳過此次爬取。")
        return

    results = [] # 存儲 (hotel_name, price, currency, source_site, details_url)

    target_sites = app_config.get('target_sites', [])
    for site_config in target_sites:
        if not site_config.get('enabled', False):
            print(f"網站 {site_config.get('name')} 未啟用，跳過。")
            continue
        
        site_name = site_config.get('name')
        print(f"正在從 {site_name} 爬取...")
        
        # 這裡需要針對每個網站實作具體的爬蟲邏輯
        # 以下為偽代碼/範例，需要您根據實際網站結構調整
        if site_name == 'Agoda':
            # 範例: results.extend(scrape_agoda(driver, search_request))
            pass # 稍後實作
        elif site_name == 'Hotels.com':
            # 範例: results.extend(scrape_hotels_com(driver, search_request))
            pass # 稍後實作
        elif site_name == 'Booking.com':
            # 範例: results.extend(scrape_booking_com(driver, search_request))
            pass # 稍後實作
        # ... 其他網站
        
        # 暫時用假數據代替，直到具體爬蟲完成
        if site_name in ['Agoda', 'Booking.com', 'Hotels.com']:
            print(f"注意: {site_name} 的爬蟲尚未實作，將使用假數據。")
            results.append((
                f"範例飯店 A from {site_name}", 
                float(2000 + time.time() % 100), # 模擬價格波動
                "TWD", 
                site_name, 
                f"{site_config.get('base_url')}/example-hotel-a"
            ))
            results.append((
                f"範例飯店 B from {site_name}", 
                float(3000 + time.time() % 150), 
                "TWD", 
                site_name, 
                f"{site_config.get('base_url')}/example-hotel-b"
            ))

    driver.quit()

    if not results:
        print(f"請求 {search_request.id} 未爬取到任何價格資訊。")
        return

    # 將爬取結果存入資料庫
    # 需要 app_context 才能操作資料庫
    from flask import current_app
    with current_app.app_context():
        for hotel_name, price_val, currency, source, url in results:
            new_price_entry = HotelPrice(
                search_request_id=search_request.id,
                hotel_name=hotel_name,
                price=price_val,
                currency=currency,
                source_site=source,
                details_url=url,
                crawl_timestamp=datetime.now(timezone.utc)
            )
            db.session.add(new_price_entry)
        
        search_request.last_crawled_at = datetime.now(timezone.utc)
        db.session.add(search_request) # 更新 last_crawled_at
        
        try:
            db.session.commit()
            print(f"請求 {search_request.id} 的 {len(results)} 筆價格資訊已成功儲存。")
        except Exception as e:
            db.session.rollback()
            print(f"儲存請求 {search_request.id} 的價格資訊失敗: {e}")

# --- 以下是各網站爬蟲的範例函數 (需要詳細實作) ---

# def scrape_agoda(driver, search_request):
#     # 實作 Agoda 的爬取邏輯
#     # 1. 導航到 Agoda 網站，並輸入搜尋條件
#     # 2. 等待搜尋結果頁面加載
#     # 3. 解析頁面，提取飯店名稱、價格、URL 等
#     # 4. 返回結果列表 [(name, price, currency, 'Agoda', url), ...]
#     return []

# def scrape_hotels_com(driver, search_request):
#     # 實作 Hotels.com 的爬取邏輯
#     return []

# def scrape_booking_com(driver, search_request):
#     # 實作 Booking.com 的爬取邏輯
#     return []

# 建議：每個網站的爬蟲邏輯可能很複雜，可以考慮將它們放到各自的模組中，
# 例如 app/services/scrapers/agoda_scraper.py 等，然後在這裡導入並調用。
