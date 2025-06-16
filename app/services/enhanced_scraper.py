"""
增強版爬蟲服務 - 包含更好的錯誤處理、重試機制和效能優化
"""

import asyncio
import time
import random
import logging
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urlencode

# 核心爬蟲相關套件
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
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

@dataclass
class ScrapingResult:
    """爬取結果的資料類別"""
    hotel_name: str
    price: float
    currency: str
    source_site: str
    details_url: str
    room_type: Optional[str] = None
    rating: Optional[float] = None
    location: Optional[str] = None

class EnhancedScraperService:
    """增強版爬蟲服務"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.ua = UserAgent()
        self.session = requests.Session()
        self.driver_pool = []
        self.max_workers = config.get('max_concurrent_requests', 3)
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
        
        # 設定代理（如果有配置）
        proxy_config = self.config.get('proxy_settings', {})
        if proxy_config.get('enabled') and proxy_config.get('proxies'):
            proxy = random.choice(proxy_config['proxies'])
            self.session.proxies = {'http': proxy, 'https': proxy}
    
    def get_webdriver(self) -> Optional[webdriver.Chrome]:
        """獲取 WebDriver 實例"""
        webdriver_config = self.config.get('webdriver', {})
        
        try:
            if webdriver_config.get('use_undetected', True):
                options = uc.ChromeOptions()
                
                # 基本選項
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                
                if webdriver_config.get('headless', True):
                    options.add_argument('--headless=new')
                
                # 視窗大小
                window_size = webdriver_config.get('window_size', [1920, 1080])
                options.add_argument(f'--window-size={window_size[0]},{window_size[1]}')
                
                # 隨機 User-Agent
                if self.config.get('anti_detection', {}).get('random_user_agent', True):
                    options.add_argument(f'--user-agent={self.ua.random}')
                
                # 代理設定
                proxy_config = self.config.get('proxy_settings', {})
                if proxy_config.get('enabled') and proxy_config.get('proxies'):
                    proxy = random.choice(proxy_config['proxies'])
                    options.add_argument(f'--proxy-server={proxy}')
                
                driver = uc.Chrome(options=options, version_main=None)
                
                # 移除 webdriver 特徵
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                # 設定超時
                driver.set_page_load_timeout(webdriver_config.get('page_load_timeout', 60))
                driver.implicitly_wait(webdriver_config.get('implicit_wait', 10))
                
                return driver
                
        except Exception as e:
            logger.error(f"初始化 WebDriver 失敗: {e}")
            
        return None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((TimeoutException, WebDriverException))
    )
    def _safe_get_page(self, driver: webdriver.Chrome, url: str) -> bool:
        """安全地載入頁面，包含重試機制"""
        try:
            # 隨機延遲
            if self.config.get('anti_detection', {}).get('random_delays', True):
                time.sleep(random.uniform(1, 3))
            
            driver.get(url)
            
            # 等待頁面載入完成
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # 模擬人類行為
            if self.config.get('anti_detection', {}).get('simulate_human_behavior', True):
                self._simulate_human_behavior(driver)
            
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
            if scroll_height > 0:
                for _ in range(random.randint(1, 2)):
                    scroll_to = random.randint(0, min(scroll_height, 1000))
                    driver.execute_script(f"window.scrollTo(0, {scroll_to});")
                    time.sleep(random.uniform(0.5, 1))
                
                # 回到頂部
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(random.uniform(0.5, 1))
            
        except Exception as e:
            logger.debug(f"模擬人類行為時發生錯誤: {e}")
    
    def scrape_with_concurrency(self, search_requests: List, app_config: Dict) -> Dict:
        """並發爬取多個搜尋請求"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任務
            future_to_request = {
                executor.submit(self.scrape_single_request, request, app_config): request
                for request in search_requests
            }
            
            # 收集結果
            for future in as_completed(future_to_request):
                request = future_to_request[future]
                try:
                    result = future.result()
                    results[request.id] = result
                except Exception as e:
                    logger.error(f"爬取請求 {request.id} 失敗: {e}")
                    results[request.id] = []
        
        return results
    
    def scrape_single_request(self, search_request, app_config: Dict) -> List[ScrapingResult]:
        """爬取單一搜尋請求"""
        logger.info(f"開始爬取請求 {search_request.id}: {search_request.location}")
        
        driver = self.get_webdriver()
        if not driver:
            logger.error(f"無法為請求 {search_request.id} 取得 WebDriver")
            return []
        
        all_results = []
        
        try:
            target_sites = app_config.get('target_sites', [])
            
            for site_config in target_sites:
                if not site_config.get('enabled', False):
                    continue
                
                site_name = site_config.get('name')
                logger.info(f"正在從 {site_name} 爬取...")
                
                try:
                    # 根據網站調用對應的爬蟲方法
                    site_results = self._scrape_site_enhanced(
                        driver, site_name, site_config, search_request
                    )
                    all_results.extend(site_results)
                    
                    # 站點間延遲
                    delay_range = site_config.get('search_delay', [3, 8])
                    time.sleep(random.uniform(delay_range[0], delay_range[1]))
                    
                except Exception as e:
                    logger.error(f"爬取 {site_name} 時發生錯誤: {e}", exc_info=True)
                    continue
        
        finally:
            driver.quit()
        
        # 儲存結果到資料庫
        if all_results:
            self._save_results_to_db(search_request, all_results)
        
        return all_results
    
    def _scrape_site_enhanced(self, driver: webdriver.Chrome, site_name: str, 
                             site_config: Dict, search_request) -> List[ScrapingResult]:
        """增強版網站爬取"""
        results = []
        
        try:
            if site_name.lower() == 'booking.com':
                results = self._scrape_booking_enhanced(driver, search_request, site_config)
            elif site_name.lower() == 'agoda':
                results = self._scrape_agoda_enhanced(driver, search_request, site_config)
            elif site_name.lower() == 'hotels.com':
                results = self._scrape_hotels_enhanced(driver, search_request, site_config)
            else:
                # 生成示範資料
                results = self._generate_enhanced_fake_data(site_name, site_config)
        
        except Exception as e:
            logger.error(f"爬取 {site_name} 時發生錯誤: {e}", exc_info=True)
        
        return results
    
    def _scrape_booking_enhanced(self, driver: webdriver.Chrome, search_request, 
                                site_config: Dict) -> List[ScrapingResult]:
        """Booking.com 增強版爬取"""
        base_url = site_config.get('base_url', 'https://www.booking.com')
        
        # 構建搜尋 URL
        params = {
            'ss': search_request.location,
            'checkin': search_request.check_in_date.strftime('%Y-%m-%d'),
            'checkout': search_request.check_out_date.strftime('%Y-%m-%d'),
            'group_adults': 2,
            'no_rooms': 1,
            'group_children': 0,
        }
        
        search_url = f"{base_url}/searchresults.html?{urlencode(params)}"
        
        if not self._safe_get_page(driver, search_url):
            return []
        
        # 處理彈窗
        self._handle_popups(driver)
        
        # 等待結果載入
        if not self._wait_for_booking_results(driver):
            return []
        
        # 解析結果
        return self._parse_booking_results(driver)
    
    def _handle_popups(self, driver: webdriver.Chrome):
        """處理各種彈窗"""
        popup_selectors = [
            # Cookie 彈窗
            "[data-testid='cookie-popup-accept']",
            "#onetrust-accept-btn-handler",
            ".cookie-accept",
            # 關閉彈窗
            "[data-testid='modal-close']",
            ".modal-close",
            ".close-button",
            "button[aria-label='Close']"
        ]
        
        for selector in popup_selectors:
            try:
                element = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                element.click()
                logger.debug(f"已處理彈窗: {selector}")
                time.sleep(1)
            except TimeoutException:
                continue
            except Exception as e:
                logger.debug(f"處理彈窗時發生錯誤: {e}")
    
    def _wait_for_booking_results(self, driver: webdriver.Chrome) -> bool:
        """等待 Booking.com 搜尋結果載入"""
        selectors = [
            "[data-testid='property-card']",
            ".sr_property_block",
            ".property-card"
        ]
        
        for selector in selectors:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                return True
            except TimeoutException:
                continue
        
        return False
    
    def _parse_booking_results(self, driver: webdriver.Chrome) -> List[ScrapingResult]:
        """解析 Booking.com 搜尋結果"""
        results = []
        
        try:
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # 尋找飯店卡片
            hotel_cards = soup.select("[data-testid='property-card'], .sr_property_block")
            
            for card in hotel_cards[:10]:  # 限制結果數量
                try:
                    hotel_name = self._extract_text(card, [
                        "[data-testid='title']",
                        ".sr-hotel__name",
                        "h3"
                    ])
                    
                    if not hotel_name:
                        continue
                    
                    price_text = self._extract_text(card, [
                        "[data-testid='price-and-discounted-price']",
                        ".bui-price-display__value",
                        ".sr-price"
                    ])
                    
                    if price_text:
                        price, currency = self._parse_price(price_text)
                        if price:
                            results.append(ScrapingResult(
                                hotel_name=hotel_name,
                                price=price,
                                currency=currency,
                                source_site="Booking.com",
                                details_url=f"https://www.booking.com/hotel-example"
                            ))
                
                except Exception as e:
                    logger.debug(f"解析飯店卡片時發生錯誤: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"解析 Booking.com 結果時發生錯誤: {e}")
        
        return results
    
    def _extract_text(self, element, selectors: List[str]) -> Optional[str]:
        """從元素中提取文字"""
        for selector in selectors:
            found = element.select_one(selector)
            if found:
                text = found.get_text(strip=True)
                if text:
                    return text
        return None
    
    def _parse_price(self, price_text: str) -> Tuple[Optional[float], str]:
        """解析價格文字"""
        import re
        
        try:
            # 移除空格和換行
            cleaned_text = re.sub(r'\s+', '', price_text)
            
            # 貨幣映射
            currency_map = {
                'NT$': 'TWD', 'TWD': 'TWD', '$': 'USD', 
                '€': 'EUR', '£': 'GBP', '¥': 'JPY'
            }
            
            currency = 'TWD'  # 預設
            
            # 找出貨幣
            for symbol, curr in currency_map.items():
                if symbol in cleaned_text:
                    currency = curr
                    cleaned_text = cleaned_text.replace(symbol, '')
                    break
            
            # 提取數字
            price_match = re.search(r'[\d,]+\.?\d*', cleaned_text)
            if price_match:
                price_str = price_match.group().replace(',', '')
                return (float(price_str), currency)
        
        except Exception as e:
            logger.debug(f"解析價格失敗: {price_text}")
        
        return (None, 'TWD')
    
    def _scrape_agoda_enhanced(self, driver: webdriver.Chrome, search_request, 
                              site_config: Dict) -> List[ScrapingResult]:
        """Agoda 增強版爬取（示範實作）"""
        logger.info("Agoda 爬蟲邏輯尚未完全實作，返回示範資料")
        return self._generate_enhanced_fake_data("Agoda", site_config)
    
    def _scrape_hotels_enhanced(self, driver: webdriver.Chrome, search_request, 
                               site_config: Dict) -> List[ScrapingResult]:
        """Hotels.com 增強版爬取（示範實作）"""
        logger.info("Hotels.com 爬蟲邏輯尚未完全實作，返回示範資料")
        return self._generate_enhanced_fake_data("Hotels.com", site_config)
    
    def _generate_enhanced_fake_data(self, site_name: str, site_config: Dict) -> List[ScrapingResult]:
        """生成增強版假資料"""
        hotels = [
            f"豪華商務飯店 - {site_name}",
            f"市中心精品旅館 - {site_name}",
            f"度假村大酒店 - {site_name}"
        ]
        
        results = []
        for hotel in hotels:
            price = round(random.uniform(1500, 5000), 2)
            rating = round(random.uniform(3.5, 4.8), 1)
            
            results.append(ScrapingResult(
                hotel_name=hotel,
                price=price,
                currency="TWD",
                source_site=site_name,
                details_url=f"{site_config.get('base_url', '')}/hotel-example",
                rating=rating,
                room_type="標準雙人房"
            ))
        
        return results
    
    def _save_results_to_db(self, search_request, results: List[ScrapingResult]):
        """將爬取結果儲存到資料庫"""
        try:
            batch_size = self.config.get('database', {}).get('batch_size', 100)
            
            for i in range(0, len(results), batch_size):
                batch = results[i:i + batch_size]
                
                for result in batch:
                    new_price_entry = HotelPrice(
                        search_request_id=search_request.id,
                        hotel_name=result.hotel_name,
                        price=result.price,
                        currency=result.currency,
                        source_site=result.source_site,
                        details_url=result.details_url,
                        crawl_timestamp=datetime.now(timezone.utc)
                    )
                    db.session.add(new_price_entry)
                
                # 批次提交
                db.session.commit()
            
            # 更新搜尋請求
            search_request.last_crawled_at = datetime.now(timezone.utc)
            db.session.add(search_request)
            db.session.commit()
            
            logger.info(f"成功儲存 {len(results)} 筆價格資訊到資料庫")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"儲存資料到資料庫失敗: {e}")
            raise

# 向後相容的函數
def scrape_prices_for_request(search_request, app_config):
    """向後相容的爬取函數"""
    enhanced_scraper = EnhancedScraperService(app_config)
    return enhanced_scraper.scrape_single_request(search_request, app_config) 