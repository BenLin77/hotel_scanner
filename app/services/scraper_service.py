# app/services/scraper_service.py
# 爬蟲相關的邏輯將會放在這裡
# 例如：
# - 初始化 Selenium WebDriver
# - 針對不同網站的爬取函數 (agoda_scraper, booking_scraper 等)
# - 解析 HTML 內容並提取價格、飯店名稱等資訊
# - 錯誤處理和重試機制

import time
import random
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin

# 核心爬蟲相關套件
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
import undetected_chromedriver as uc

# 其他工具
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from bs4 import BeautifulSoup
import requests

# Flask相關
from flask import current_app
from ..models import HotelPrice
from .. import db

# 設定日誌
logger = logging.getLogger(__name__)

class ScraperService:
    """改進的爬蟲服務類"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.ua = UserAgent()
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        """設定 requests session"""
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def get_webdriver(self, use_undetected: bool = True) -> Optional[webdriver.Chrome]:
        """
        獲取 WebDriver 實例，支援反檢測功能
        
        Args:
            use_undetected: 是否使用 undetected-chromedriver
        """
        browser_type = self.config.get('webdriver', {}).get('browser', 'chrome').lower()
        headless = self.config.get('webdriver', {}).get('headless', True)
        
        try:
            if browser_type == 'chrome':
                if use_undetected:
                    options = uc.ChromeOptions()
                    options.add_argument('--no-sandbox')
                    options.add_argument('--disable-dev-shm-usage')
                    options.add_argument('--disable-gpu')
                    options.add_argument('--disable-blink-features=AutomationControlled')
                    options.add_experimental_option("excludeSwitches", ["enable-automation"])
                    options.add_experimental_option('useAutomationExtension', False)
                    
                    if headless:
                        options.add_argument('--headless=new')
                    
                    # 使用 undetected chromedriver
                    driver = uc.Chrome(options=options, version_main=None)
                    
                    # 移除 webdriver 特徵
                    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    
                else:
                    options = webdriver.ChromeOptions()
                    if headless:
                        options.add_argument('--headless')
                    
                    options.add_argument('--no-sandbox')
                    options.add_argument('--disable-dev-shm-usage')
                    options.add_argument('--disable-gpu')
                    options.add_argument(f"user-agent={self.ua.random}")
                    options.add_argument("--incognito")
                    
                    service = ChromeService(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=options)
                
            elif browser_type == 'firefox':
                options = webdriver.FirefoxOptions()
                if headless:
                    options.add_argument('--headless')
                options.add_argument("--private")
                
                service = FirefoxService(GeckoDriverManager().install())
                driver = webdriver.Firefox(service=service, options=options)
            
            else:
                raise ValueError(f"不支援的瀏覽器類型: {browser_type}")
            
            # 設定超時
            driver.set_page_load_timeout(60)
            driver.implicitly_wait(10)
            
            # 設定視窗大小（避免移動版網站）
            driver.set_window_size(1920, 1080)
            
            return driver
            
        except Exception as e:
            logger.error(f"初始化 WebDriver 失敗 ({browser_type}): {e}")
            return None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((TimeoutException, WebDriverException))
    )
    def _safe_get_page(self, driver: webdriver.Chrome, url: str) -> bool:
        """
        安全地載入頁面，包含重試機制
        
        Returns:
            bool: 是否成功載入頁面
        """
        try:
            # 隨機延遲，模擬人類行為
            time.sleep(random.uniform(2, 5))
            
            driver.get(url)
            
            # 等待頁面載入完成
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # 額外的隨機延遲
            time.sleep(random.uniform(1, 3))
            
            return True
            
        except TimeoutException:
            logger.warning(f"頁面載入超時: {url}")
            return False
        except Exception as e:
            logger.error(f"載入頁面失敗 {url}: {e}")
            return False
    
    def _simulate_human_behavior(self, driver: webdriver.Chrome):
        """模擬人類瀏覽行為"""
        try:
            # 隨機滾動
            scroll_height = driver.execute_script("return document.body.scrollHeight")
            for _ in range(random.randint(1, 3)):
                scroll_to = random.randint(0, scroll_height)
                driver.execute_script(f"window.scrollTo(0, {scroll_to});")
                time.sleep(random.uniform(0.5, 1.5))
            
            # 回到頂部
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(random.uniform(0.5, 1))
            
        except Exception as e:
            logger.debug(f"模擬人類行為時發生錯誤: {e}")

    def scrape_prices_for_request(self, search_request, app_config: Dict):
        """改進的價格爬取函數"""
        logger.info(f"開始爬取請求 {search_request.id}: {search_request.location} "
                   f"({search_request.check_in_date} - {search_request.check_out_date})")
        
        driver = self.get_webdriver(use_undetected=True)
        if not driver:
            logger.error(f"無法為請求 {search_request.id} 取得 WebDriver，跳過此次爬取")
            return

        results = []
        
        try:
            target_sites = app_config.get('target_sites', [])
            
            for site_config in target_sites:
                if not site_config.get('enabled', False):
                    logger.info(f"網站 {site_config.get('name')} 未啟用，跳過")
                    continue
                
                site_name = site_config.get('name')
                logger.info(f"正在從 {site_name} 爬取...")
                
                try:
                    # 根據網站調用對應的爬蟲函數
                    site_results = self._scrape_site(driver, site_name, site_config, search_request)
                    results.extend(site_results)
                    
                    # 站點間隨機延遲
                    time.sleep(random.uniform(3, 8))
                    
                except Exception as e:
                    logger.error(f"爬取 {site_name} 時發生錯誤: {e}", exc_info=True)
                    continue
        
        finally:
            driver.quit()

        if not results:
            logger.warning(f"請求 {search_request.id} 未爬取到任何價格資訊")
            return

        # 儲存結果到資料庫
        self._save_results_to_db(search_request, results)

    def _scrape_site(self, driver: webdriver.Chrome, site_name: str, 
                    site_config: Dict, search_request) -> List[Tuple]:
        """
        針對特定網站進行爬取
        
        Returns:
            List[Tuple]: [(hotel_name, price, currency, source_site, details_url), ...]
        """
        results = []
        
        try:
            if site_name.lower() == 'agoda':
                results = self._scrape_agoda(driver, search_request, site_config)
            elif site_name.lower() == 'booking.com':
                results = self._scrape_booking(driver, search_request, site_config)
            elif site_name.lower() == 'hotels.com':
                results = self._scrape_hotels_com(driver, search_request, site_config)
            else:
                logger.warning(f"未實作的網站: {site_name}")
                # 暫時使用假資料
                results = self._generate_fake_data(site_name, site_config)
                
        except Exception as e:
            logger.error(f"爬取 {site_name} 時發生錯誤: {e}", exc_info=True)
        
        return results

    def _scrape_agoda(self, driver: webdriver.Chrome, search_request, 
                     site_config: Dict) -> List[Tuple]:
        """Agoda 爬取邏輯"""
        # 構建搜尋 URL
        base_url = site_config.get('base_url', 'https://www.agoda.com')
        
        # 這裡需要根據 Agoda 的實際 URL 格式來構建
        # 由於沒有實際的 API 文檔，這裡使用基本的搜尋邏輯
        search_url = f"{base_url}/search"
        
        if not self._safe_get_page(driver, search_url):
            return []
        
        # 模擬人類行為
        self._simulate_human_behavior(driver)
        
        # 這裡需要實際的 Agoda 頁面解析邏輯
        # 暫時返回假資料
        logger.info("Agoda 爬蟲邏輯尚未完全實作，返回示範資料")
        return self._generate_fake_data("Agoda", site_config)

    def _scrape_booking(self, driver: webdriver.Chrome, search_request, 
                       site_config: Dict) -> List[Tuple]:
        """Booking.com 爬取邏輯"""
        # 類似 Agoda 的邏輯
        logger.info("Booking.com 爬蟲邏輯尚未完全實作，返回示範資料")
        return self._generate_fake_data("Booking.com", site_config)

    def _scrape_hotels_com(self, driver: webdriver.Chrome, search_request, 
                          site_config: Dict) -> List[Tuple]:
        """Hotels.com 爬取邏輯"""
        # 類似其他網站的邏輯
        logger.info("Hotels.com 爬蟲邏輯尚未完全實作，返回示範資料")
        return self._generate_fake_data("Hotels.com", site_config)

    def _generate_fake_data(self, site_name: str, site_config: Dict) -> List[Tuple]:
        """生成假資料用於測試"""
        base_url = site_config.get('base_url', '')
        fake_hotels = [
            f"豪華飯店 A - {site_name}",
            f"商務飯店 B - {site_name}",
            f"精品飯店 C - {site_name}"
        ]
        
        results = []
        for hotel in fake_hotels:
            price = round(random.uniform(1500, 5000), 2)
            results.append((
                hotel,
                price,
                "TWD",
                site_name,
                f"{base_url}/hotel-example"
            ))
        
        return results

    def _save_results_to_db(self, search_request, results: List[Tuple]):
        """將爬取結果儲存到資料庫"""
        try:
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
            db.session.add(search_request)
            
            db.session.commit()
            logger.info(f"請求 {search_request.id} 的 {len(results)} 筆價格資訊已成功儲存")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"儲存請求 {search_request.id} 的價格資訊失敗: {e}")
            raise

# 向後相容的函數
def scrape_prices_for_request(search_request, app_config):
    """向後相容的爬取函數"""
    scraper = ScraperService(app_config)
    return scraper.scrape_prices_for_request(search_request, app_config)
