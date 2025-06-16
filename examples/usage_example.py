#!/usr/bin/env python3
# examples/usage_example.py
"""
Hotel Scanner 使用範例

這個腳本展示如何使用改進後的爬蟲功能
"""

import sys
import os
from datetime import datetime, timedelta

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app, db
from app.models import SearchRequest
from app.services.scraper_service import ScraperService
from app.utils.monitoring import performance_monitor, initialize_monitoring

def example_basic_usage():
    """基本使用範例"""
    print("=== 基本使用範例 ===")
    
    # 創建 Flask 應用程式上下文
    app = create_app()
    
    with app.app_context():
        # 創建一個搜尋請求
        search_request = SearchRequest(
            location="台北",
            check_in_date=(datetime.now() + timedelta(days=7)).date(),
            check_out_date=(datetime.now() + timedelta(days=9)).date(),
            is_tracking=True
        )
        
        db.session.add(search_request)
        db.session.commit()
        
        print(f"創建了搜尋請求: {search_request}")
        
        # 使用改進的爬蟲進行爬取
        config = app.config['APP_SETTINGS']
        scraper = ScraperService(config)
        
        try:
            results = scraper.scrape_prices_for_request(search_request, config)
            print(f"爬取完成，獲得 {len(results) if results else 0} 筆結果")
            
        except Exception as e:
            print(f"爬取過程中發生錯誤: {e}")

def example_monitoring_usage():
    """監控功能使用範例"""
    print("\n=== 監控功能使用範例 ===")
    
    app = create_app()
    
    with app.app_context():
        # 初始化監控系統
        config = app.config['APP_SETTINGS']
        initialize_monitoring(config)
        
        # 模擬一些爬取活動
        with performance_monitor.track_scraping("Booking.com", request_id=1):
            print("模擬爬取 Booking.com...")
            import time
            time.sleep(2)  # 模擬爬取時間
        
        with performance_monitor.track_scraping("Agoda", request_id=2):
            print("模擬爬取 Agoda...")
            time.sleep(1.5)
        
        # 查看統計資訊
        stats = performance_monitor.get_overall_statistics()
        print(f"整體統計: {stats}")
        
        # 查看特定站點統計
        booking_stats = performance_monitor.get_site_statistics("Booking.com")
        print(f"Booking.com 統計: {booking_stats}")

def example_concurrent_scraping():
    """並發爬取範例"""
    print("\n=== 並發爬取範例 ===")
    
    app = create_app()
    
    with app.app_context():
        # 創建多個搜尋請求
        search_requests = []
        cities = ["台北", "高雄", "台中"]
        
        for i, city in enumerate(cities):
            request = SearchRequest(
                location=city,
                check_in_date=(datetime.now() + timedelta(days=7 + i)).date(),
                check_out_date=(datetime.now() + timedelta(days=9 + i)).date(),
                is_tracking=True
            )
            db.session.add(request)
            search_requests.append(request)
        
        db.session.commit()
        
        # 使用增強版爬蟲進行並發爬取
        from app.services.enhanced_scraper import EnhancedScraperService
        
        config = app.config['APP_SETTINGS']
        enhanced_scraper = EnhancedScraperService(config)
        
        try:
            results = enhanced_scraper.scrape_with_concurrency(search_requests, config)
            print(f"並發爬取完成，結果: {results}")
            
        except Exception as e:
            print(f"並發爬取失敗: {e}")

def example_price_analysis():
    """價格分析範例"""
    print("\n=== 價格分析範例 ===")
    
    app = create_app()
    
    with app.app_context():
        from app.models import HotelPrice
        from app.utils.scraper_helpers import PriceParser
        
        # 獲取最近的價格資料
        recent_prices = HotelPrice.query.order_by(HotelPrice.crawl_timestamp.desc()).limit(10).all()
        
        if recent_prices:
            print("最近的價格資料:")
            for price in recent_prices:
                print(f"  {price.hotel_name}: {price.price} {price.currency} ({price.source_site})")
            
            # 價格統計
            prices_by_site = {}
            for price in recent_prices:
                if price.source_site not in prices_by_site:
                    prices_by_site[price.source_site] = []
                prices_by_site[price.source_site].append(price.price)
            
            print("\n各站點平均價格:")
            for site, prices in prices_by_site.items():
                avg_price = sum(prices) / len(prices)
                print(f"  {site}: {avg_price:.2f} 元")
        
        else:
            print("尚無價格資料")

def example_configuration():
    """配置範例"""
    print("\n=== 配置範例 ===")
    
    # 展示如何動態修改配置
    example_config = {
        'target_sites': [
            {
                'name': 'Booking.com',
                'base_url': 'https://www.booking.com',
                'enabled': True,
                'search_delay': [3, 8]
            }
        ],
        'crawl_interval_hours': 2,
        'max_concurrent_requests': 3,
        'webdriver': {
            'browser': 'chrome',
            'headless': True,
            'use_undetected': True
        },
        'anti_detection': {
            'random_user_agent': True,
            'simulate_human_behavior': True,
            'random_delays': True
        },
        'proxy_settings': {
            'enabled': False,
            'proxies': []
        }
    }
    
    print("範例配置:")
    import json
    print(json.dumps(example_config, indent=2, ensure_ascii=False))

def main():
    """主函數"""
    print("Hotel Scanner 使用範例")
    print("=" * 50)
    
    try:
        # 基本使用
        example_basic_usage()
        
        # 監控功能
        example_monitoring_usage()
        
        # 並發爬取
        example_concurrent_scraping()
        
        # 價格分析
        example_price_analysis()
        
        # 配置範例
        example_configuration()
        
        print("\n所有範例執行完成！")
        
    except Exception as e:
        print(f"執行範例時發生錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 