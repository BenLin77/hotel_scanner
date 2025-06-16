"""
爬蟲輔助工具模組

提供爬蟲過程中需要的各種輔助功能
"""

import re
import time
import random
import logging
from typing import Optional, Tuple, List, Dict
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta

import requests
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class PriceParser:
    """價格解析器"""
    
    # 貨幣符號映射
    CURRENCY_SYMBOLS = {
        'NT$': 'TWD', 'TWD': 'TWD', '台幣': 'TWD',
        '$': 'USD', 'USD': 'USD', '美元': 'USD',
        '€': 'EUR', 'EUR': 'EUR', '歐元': 'EUR',
        '£': 'GBP', 'GBP': 'GBP', '英鎊': 'GBP',
        '¥': 'JPY', 'JPY': 'JPY', '日元': 'JPY',
        '元': 'CNY', 'CNY': 'CNY', '人民幣': 'CNY'
    }
    
    @classmethod
    def parse_price_text(cls, price_text: str) -> Tuple[Optional[float], str]:
        """
        解析價格文字，返回價格和貨幣
        
        Args:
            price_text: 包含價格的文字
            
        Returns:
            Tuple[price, currency]: 價格和貨幣代碼
        """
        if not price_text:
            return None, 'TWD'
        
        try:
            # 清理文字
            cleaned_text = re.sub(r'\s+', '', price_text)
            cleaned_text = cleaned_text.replace('\n', '').replace('\t', '')
            
            # 預設貨幣
            currency = 'TWD'
            
            # 尋找貨幣符號
            for symbol, curr in cls.CURRENCY_SYMBOLS.items():
                if symbol in cleaned_text:
                    currency = curr
                    cleaned_text = cleaned_text.replace(symbol, '')
                    break
            
            # 提取數字（支援千分位逗號）
            price_pattern = r'[\d,]+\.?\d*'
            price_match = re.search(price_pattern, cleaned_text)
            
            if price_match:
                price_str = price_match.group().replace(',', '')
                price_value = float(price_str)
                return price_value, currency
                
        except Exception as e:
            logger.debug(f"解析價格失敗: {price_text}, 錯誤: {e}")
        
        return None, 'TWD'
    
    @classmethod
    def normalize_price(cls, price: float, currency: str, target_currency: str = 'TWD') -> float:
        """
        將價格轉換為目標貨幣（簡單版本，實際應該使用即時匯率）
        
        Args:
            price: 原始價格
            currency: 原始貨幣
            target_currency: 目標貨幣
            
        Returns:
            轉換後的價格
        """
        # 這裡使用固定匯率，實際應用中應該使用即時匯率 API
        exchange_rates = {
            'USD': 31.5,   # 1 USD = 31.5 TWD
            'EUR': 34.2,   # 1 EUR = 34.2 TWD
            'GBP': 39.8,   # 1 GBP = 39.8 TWD
            'JPY': 0.21,   # 1 JPY = 0.21 TWD
            'CNY': 4.35,   # 1 CNY = 4.35 TWD
            'TWD': 1.0     # 1 TWD = 1 TWD
        }
        
        if currency == target_currency:
            return price
        
        if currency in exchange_rates and target_currency in exchange_rates:
            # 先轉換為 TWD，再轉換為目標貨幣
            twd_price = price * exchange_rates[currency]
            return twd_price / exchange_rates[target_currency]
        
        return price

class UserAgentRotator:
    """User-Agent 輪換器"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.used_agents = set()
        self.max_cache_size = 100
    
    def get_random_user_agent(self) -> str:
        """獲取隨機 User-Agent"""
        try:
            # 如果快取太大，清理一些舊的
            if len(self.used_agents) > self.max_cache_size:
                self.used_agents.clear()
            
            # 嘗試獲取新的 User-Agent
            for _ in range(10):  # 最多嘗試 10 次
                agent = self.ua.random
                if agent not in self.used_agents:
                    self.used_agents.add(agent)
                    return agent
            
            # 如果都用過了，返回一個隨機的
            return self.ua.random
            
        except Exception:
            # 如果 fake_useragent 失敗，返回預設的
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class DelayController:
    """延遲控制器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.last_request_time = {}
    
    def wait_if_needed(self, site_name: str):
        """如果需要的話進行等待"""
        try:
            # 獲取站點特定的延遲配置
            site_config = self._get_site_config(site_name)
            delay_range = site_config.get('search_delay', [2, 5])
            
            current_time = time.time()
            last_time = self.last_request_time.get(site_name, 0)
            
            # 計算需要等待的時間
            min_interval = delay_range[0]
            elapsed = current_time - last_time
            
            if elapsed < min_interval:
                wait_time = random.uniform(min_interval - elapsed, delay_range[1] - elapsed)
                if wait_time > 0:
                    logger.debug(f"為站點 {site_name} 等待 {wait_time:.2f} 秒")
                    time.sleep(wait_time)
            
            self.last_request_time[site_name] = time.time()
            
        except Exception as e:
            logger.debug(f"延遲控制失敗: {e}")
            # 預設延遲
            time.sleep(random.uniform(1, 3))
    
    def _get_site_config(self, site_name: str) -> Dict:
        """獲取站點配置"""
        target_sites = self.config.get('target_sites', [])
        for site in target_sites:
            if site.get('name', '').lower() == site_name.lower():
                return site
        return {}

class ProxyManager:
    """代理管理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.proxies = config.get('proxy_settings', {}).get('proxies', [])
        self.current_proxy_index = 0
        self.failed_proxies = set()
    
    def get_next_proxy(self) -> Optional[str]:
        """獲取下一個可用代理"""
        if not self.proxies:
            return None
        
        available_proxies = [p for p in self.proxies if p not in self.failed_proxies]
        
        if not available_proxies:
            # 所有代理都失敗了，重置失敗列表
            logger.warning("所有代理都失敗，重置代理列表")
            self.failed_proxies.clear()
            available_proxies = self.proxies
        
        if available_proxies:
            proxy = available_proxies[self.current_proxy_index % len(available_proxies)]
            self.current_proxy_index += 1
            return proxy
        
        return None
    
    def mark_proxy_failed(self, proxy: str):
        """標記代理為失敗"""
        self.failed_proxies.add(proxy)
        logger.warning(f"代理 {proxy} 標記為失敗")
    
    def test_proxy(self, proxy: str, timeout: int = 10) -> bool:
        """測試代理是否可用"""
        try:
            proxies = {
                'http': proxy,
                'https': proxy
            }
            
            response = requests.get(
                'http://httpbin.org/ip',
                proxies=proxies,
                timeout=timeout
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.debug(f"代理測試失敗 {proxy}: {e}")
            return False

class URLBuilder:
    """URL 構建器"""
    
    @staticmethod
    def build_booking_search_url(location: str, check_in: str, check_out: str, 
                                adults: int = 2, rooms: int = 1) -> str:
        """構建 Booking.com 搜尋 URL"""
        from urllib.parse import urlencode
        
        params = {
            'ss': location,
            'checkin': check_in,
            'checkout': check_out,
            'group_adults': adults,
            'no_rooms': rooms,
            'group_children': 0,
        }
        
        base_url = "https://www.booking.com/searchresults.html"
        return f"{base_url}?{urlencode(params)}"
    
    @staticmethod
    def build_agoda_search_url(location: str, check_in: str, check_out: str) -> str:
        """構建 Agoda 搜尋 URL（簡化版）"""
        # Agoda 的 URL 結構比較複雜，這裡提供基本版本
        base_url = "https://www.agoda.com/search"
        return f"{base_url}?city={location}&checkIn={check_in}&checkOut={check_out}"

class DataValidator:
    """資料驗證器"""
    
    @staticmethod
    def is_valid_hotel_name(name: str) -> bool:
        """驗證飯店名稱是否有效"""
        if not name or len(name.strip()) < 2:
            return False
        
        # 過濾掉明顯的垃圾資料
        spam_keywords = ['廣告', 'ad', 'advertisement', 'spam', '點擊這裡']
        name_lower = name.lower()
        
        return not any(keyword in name_lower for keyword in spam_keywords)
    
    @staticmethod
    def is_valid_price(price: float, currency: str = 'TWD') -> bool:
        """驗證價格是否合理"""
        if price <= 0:
            return False
        
        # 根據貨幣設定合理的價格範圍
        price_ranges = {
            'TWD': (500, 50000),    # 台幣 500-50000
            'USD': (20, 2000),      # 美元 20-2000
            'EUR': (20, 2000),      # 歐元 20-2000
            'GBP': (20, 2000),      # 英鎊 20-2000
            'JPY': (2000, 200000), # 日元 2000-200000
        }
        
        min_price, max_price = price_ranges.get(currency, (0, float('inf')))
        return min_price <= price <= max_price
    
    @staticmethod
    def clean_hotel_name(name: str) -> str:
        """清理飯店名稱"""
        if not name:
            return ""
        
        # 移除多餘的空白
        cleaned = re.sub(r'\s+', ' ', name.strip())
        
        # 移除特殊字符（保留基本標點）
        cleaned = re.sub(r'[^\w\s\-\(\)\[\]\.\/\&]', '', cleaned)
        
        return cleaned

class RateLimiter:
    """速率限制器"""
    
    def __init__(self, requests_per_minute: int = 30):
        self.requests_per_minute = requests_per_minute
        self.request_times = []
    
    def wait_if_needed(self):
        """如果需要的話進行等待"""
        current_time = time.time()
        
        # 清理超過一分鐘的記錄
        self.request_times = [t for t in self.request_times if current_time - t < 60]
        
        # 如果超過限制，等待
        if len(self.request_times) >= self.requests_per_minute:
            oldest_request = min(self.request_times)
            wait_time = 60 - (current_time - oldest_request) + random.uniform(1, 3)
            
            if wait_time > 0:
                logger.info(f"達到速率限制，等待 {wait_time:.2f} 秒")
                time.sleep(wait_time)
        
        self.request_times.append(current_time) 