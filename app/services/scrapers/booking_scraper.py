# app/services/scrapers/booking_scraper.py
import time
import random
import logging
from datetime import datetime
from typing import List, Tuple, Optional
from urllib.parse import urlencode

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class BookingScraper:
    """Booking.com 專門爬蟲"""
    
    def __init__(self, config: dict):
        self.config = config
        self.base_url = "https://www.booking.com"
        
    def scrape_hotels(self, driver: webdriver.Chrome, search_request) -> List[Tuple]:
        """
        爬取 Booking.com 的飯店資訊
        
        Returns:
            List[Tuple]: [(hotel_name, price, currency, source_site, details_url), ...]
        """
        results = []
        
        try:
            # 構建搜尋 URL
            search_url = self._build_search_url(search_request)
            logger.info(f"正在訪問 Booking.com 搜尋頁面: {search_url}")
            
            # 載入搜尋頁面
            if not self._load_search_page(driver, search_url):
                logger.error("無法載入 Booking.com 搜尋頁面")
                return results
            
            # 等待並處理可能的彈窗
            self._handle_popups(driver)
            
            # 等待搜尋結果載入
            if not self._wait_for_results(driver):
                logger.warning("Booking.com 搜尋結果載入失敗")
                return results
            
            # 解析搜尋結果
            results = self._parse_search_results(driver)
            logger.info(f"從 Booking.com 爬取到 {len(results)} 筆飯店資訊")
            
        except Exception as e:
            logger.error(f"Booking.com 爬取過程中發生錯誤: {e}", exc_info=True)
        
        return results
    
    def _build_search_url(self, search_request) -> str:
        """構建搜尋 URL"""
        # Booking.com 的搜尋參數
        params = {
            'ss': search_request.location,  # 搜尋位置
            'checkin': search_request.check_in_date.strftime('%Y-%m-%d'),
            'checkout': search_request.check_out_date.strftime('%Y-%m-%d'),
            'group_adults': 2,  # 預設 2 位成人
            'no_rooms': 1,      # 預設 1 間房
            'group_children': 0, # 預設無兒童
        }
        
        # 構建完整 URL
        search_url = f"{self.base_url}/searchresults.html?{urlencode(params)}"
        return search_url
    
    def _load_search_page(self, driver: webdriver.Chrome, url: str) -> bool:
        """載入搜尋頁面"""
        try:
            driver.get(url)
            
            # 等待頁面基本元素載入
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # 隨機延遲，模擬人類行為
            time.sleep(random.uniform(2, 4))
            
            return True
            
        except Exception as e:
            logger.error(f"載入 Booking.com 頁面失敗: {e}")
            return False
    
    def _handle_popups(self, driver: webdriver.Chrome):
        """處理彈窗"""
        try:
            # 處理 Cookie 同意彈窗
            cookie_button_selectors = [
                "[data-testid='cookie-popup-accept']",
                "#onetrust-accept-btn-handler",
                ".cookie-popup-accept",
                "button[data-gdpr-consent='accept']"
            ]
            
            for selector in cookie_button_selectors:
                try:
                    cookie_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    cookie_button.click()
                    logger.info("已點擊 Cookie 同意按鈕")
                    time.sleep(1)
                    break
                except TimeoutException:
                    continue
            
            # 處理其他可能的彈窗
            close_button_selectors = [
                "[data-testid='modal-close']",
                ".modal-close",
                ".close-popup",
                "button[aria-label='Close']"
            ]
            
            for selector in close_button_selectors:
                try:
                    close_button = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    close_button.click()
                    logger.info("已關閉彈窗")
                    time.sleep(1)
                except TimeoutException:
                    continue
                    
        except Exception as e:
            logger.debug(f"處理彈窗時發生錯誤: {e}")
    
    def _wait_for_results(self, driver: webdriver.Chrome) -> bool:
        """等待搜尋結果載入"""
        try:
            # 等待飯店列表出現
            result_selectors = [
                "[data-testid='property-card']",
                ".sr_property_block",
                ".c-sr-property-block",
                ".property-card"
            ]
            
            for selector in result_selectors:
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    logger.info(f"搜尋結果已載入，使用選擇器: {selector}")
                    return True
                except TimeoutException:
                    continue
            
            logger.warning("未找到任何搜尋結果")
            return False
            
        except Exception as e:
            logger.error(f"等待搜尋結果時發生錯誤: {e}")
            return False
    
    def _parse_search_results(self, driver: webdriver.Chrome) -> List[Tuple]:
        """解析搜尋結果"""
        results = []
        
        try:
            # 滾動頁面以載入更多結果
            self._scroll_to_load_more(driver)
            
            # 使用 BeautifulSoup 解析頁面
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # 尋找飯店卡片
            hotel_cards = self._find_hotel_cards(soup)
            
            for card in hotel_cards:
                try:
                    hotel_info = self._extract_hotel_info(card)
                    if hotel_info:
                        results.append(hotel_info)
                        
                except Exception as e:
                    logger.debug(f"解析單個飯店資訊時發生錯誤: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"解析搜尋結果時發生錯誤: {e}")
        
        return results
    
    def _find_hotel_cards(self, soup: BeautifulSoup) -> List:
        """尋找飯店卡片元素"""
        selectors = [
            "[data-testid='property-card']",
            ".sr_property_block",
            ".c-sr-property-block",
            ".property-card"
        ]
        
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                logger.info(f"找到 {len(cards)} 個飯店卡片，使用選擇器: {selector}")
                return cards
        
        logger.warning("未找到任何飯店卡片")
        return []
    
    def _extract_hotel_info(self, card) -> Optional[Tuple]:
        """從飯店卡片中提取資訊"""
        try:
            # 飯店名稱
            hotel_name = self._extract_hotel_name(card)
            if not hotel_name:
                return None
            
            # 價格資訊
            price_info = self._extract_price_info(card)
            if not price_info:
                return None
            
            price, currency = price_info
            
            # 詳情連結
            details_url = self._extract_details_url(card)
            
            return (hotel_name, price, currency, "Booking.com", details_url)
            
        except Exception as e:
            logger.debug(f"提取飯店資訊時發生錯誤: {e}")
            return None
    
    def _extract_hotel_name(self, card) -> Optional[str]:
        """提取飯店名稱"""
        name_selectors = [
            "[data-testid='title']",
            ".sr-hotel__name",
            ".property-name",
            "h3 a",
            ".c-sr-property-block__title"
        ]
        
        for selector in name_selectors:
            element = card.select_one(selector)
            if element:
                name = element.get_text(strip=True)
                if name:
                    return name
        
        return None
    
    def _extract_price_info(self, card) -> Optional[Tuple[float, str]]:
        """提取價格資訊"""
        price_selectors = [
            "[data-testid='price-and-discounted-price']",
            ".bui-price-display__value",
            ".sr-price__value",
            ".property-price",
            ".c-sr-property-block__price"
        ]
        
        for selector in price_selectors:
            price_element = card.select_one(selector)
            if price_element:
                price_text = price_element.get_text(strip=True)
                price, currency = self._parse_price_text(price_text)
                if price:
                    return (price, currency)
        
        return None
    
    def _parse_price_text(self, price_text: str) -> Tuple[Optional[float], str]:
        """解析價格文字"""
        try:
            # 移除空格和換行
            price_text = price_text.replace('\n', '').replace(' ', '')
            
            # 常見的貨幣符號
            currency_symbols = {
                'NT$': 'TWD',
                'TWD': 'TWD', 
                '$': 'USD',
                '€': 'EUR',
                '£': 'GBP',
                '¥': 'JPY'
            }
            
            currency = 'TWD'  # 預設貨幣
            
            # 尋找貨幣符號
            for symbol, curr in currency_symbols.items():
                if symbol in price_text:
                    currency = curr
                    price_text = price_text.replace(symbol, '')
                    break
            
            # 移除逗號並提取數字
            import re
            price_match = re.search(r'[\d,]+\.?\d*', price_text)
            if price_match:
                price_str = price_match.group().replace(',', '')
                return (float(price_str), currency)
            
        except Exception as e:
            logger.debug(f"解析價格失敗: {price_text}, 錯誤: {e}")
        
        return (None, 'TWD')
    
    def _extract_details_url(self, card) -> str:
        """提取詳情頁面 URL"""
        link_selectors = [
            "a[data-testid='title-link']",
            ".sr-hotel__name a",
            ".property-name a",
            "h3 a"
        ]
        
        for selector in link_selectors:
            link = card.select_one(selector)
            if link and link.get('href'):
                href = link.get('href')
                if href.startswith('/'):
                    return f"{self.base_url}{href}"
                elif href.startswith('http'):
                    return href
        
        return f"{self.base_url}/hotels"
    
    def _scroll_to_load_more(self, driver: webdriver.Chrome):
        """滾動頁面載入更多結果"""
        try:
            # 緩慢滾動，模擬人類行為
            last_height = driver.execute_script("return document.body.scrollHeight")
            
            for _ in range(3):  # 最多滾動 3 次
                # 滾動到頁面底部
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # 等待新內容載入
                time.sleep(random.uniform(2, 4))
                
                # 檢查是否有新內容
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            
            # 滾動回頂部
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
        except Exception as e:
            logger.debug(f"滾動頁面時發生錯誤: {e}") 