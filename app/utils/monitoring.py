"""
監控和效能追蹤模組

提供爬蟲效能監控、錯誤追蹤和統計功能
"""

import time
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, asdict
import threading

logger = logging.getLogger(__name__)

@dataclass
class ScrapingMetrics:
    """爬取指標"""
    site_name: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error_message: Optional[str]
    results_count: int
    request_id: Optional[int]

class PerformanceMonitor:
    """效能監控器"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics_history = deque(maxlen=max_history)
        self.site_stats = defaultdict(lambda: {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_duration': 0,
            'total_results': 0,
            'last_success': None,
            'last_error': None
        })
        self._lock = threading.Lock()
    
    @contextmanager
    def track_scraping(self, site_name: str, request_id: Optional[int] = None):
        """追蹤爬取效能的上下文管理器"""
        start_time = time.time()
        error_message = None
        results_count = 0
        
        try:
            yield self
            success = True
        except Exception as e:
            success = False
            error_message = str(e)
            logger.error(f"爬取 {site_name} 時發生錯誤: {e}")
            raise
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            # 記錄指標
            metrics = ScrapingMetrics(
                site_name=site_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                success=success,
                error_message=error_message,
                results_count=results_count,
                request_id=request_id
            )
            
            self.record_metrics(metrics)
    
    def record_metrics(self, metrics: ScrapingMetrics):
        """記錄指標"""
        with self._lock:
            self.metrics_history.append(metrics)
            
            # 更新站點統計
            stats = self.site_stats[metrics.site_name]
            stats['total_requests'] += 1
            stats['total_duration'] += metrics.duration
            stats['total_results'] += metrics.results_count
            
            if metrics.success:
                stats['successful_requests'] += 1
                stats['last_success'] = metrics.end_time
            else:
                stats['failed_requests'] += 1
                stats['last_error'] = {
                    'time': metrics.end_time,
                    'message': metrics.error_message
                }
    
    def get_site_statistics(self, site_name: str) -> Dict:
        """獲取指定站點的統計資訊"""
        with self._lock:
            stats = self.site_stats[site_name].copy()
            
            if stats['total_requests'] > 0:
                stats['success_rate'] = stats['successful_requests'] / stats['total_requests']
                stats['average_duration'] = stats['total_duration'] / stats['total_requests']
                stats['average_results'] = stats['total_results'] / stats['total_requests']
            else:
                stats.update({
                    'success_rate': 0,
                    'average_duration': 0,
                    'average_results': 0
                })
            
            return stats
    
    def get_overall_statistics(self) -> Dict:
        """獲取整體統計資訊"""
        with self._lock:
            if not self.metrics_history:
                return {
                    'total_requests': 0,
                    'success_rate': 0,
                    'average_duration': 0,
                    'sites': {}
                }
            
            total_requests = len(self.metrics_history)
            successful_requests = sum(1 for m in self.metrics_history if m.success)
            total_duration = sum(m.duration for m in self.metrics_history)
            
            stats = {
                'total_requests': total_requests,
                'successful_requests': successful_requests,
                'failed_requests': total_requests - successful_requests,
                'success_rate': successful_requests / total_requests,
                'average_duration': total_duration / total_requests,
                'sites': {}
            }
            
            # 各站點統計
            for site_name in self.site_stats:
                stats['sites'][site_name] = self.get_site_statistics(site_name)
            
            return stats
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict]:
        """獲取最近的錯誤"""
        with self._lock:
            errors = []
            for metrics in reversed(self.metrics_history):
                if not metrics.success and len(errors) < limit:
                    errors.append({
                        'site_name': metrics.site_name,
                        'error_message': metrics.error_message,
                        'time': datetime.fromtimestamp(metrics.end_time, timezone.utc).isoformat(),
                        'request_id': metrics.request_id
                    })
            
            return errors
    
    def is_site_healthy(self, site_name: str, min_success_rate: float = 0.8) -> bool:
        """檢查站點是否健康"""
        stats = self.get_site_statistics(site_name)
        return stats.get('success_rate', 0) >= min_success_rate

class AlertManager:
    """警報管理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.alert_history = deque(maxlen=100)
        self.last_alert_times = {}
        self.min_alert_interval = 300  # 5分鐘
    
    def check_and_send_alerts(self, monitor: PerformanceMonitor):
        """檢查並發送警報"""
        current_time = time.time()
        
        # 檢查各站點的健康狀況
        for site_name in monitor.site_stats:
            stats = monitor.get_site_statistics(site_name)
            
            # 檢查成功率
            if stats['total_requests'] >= 5:  # 至少要有5次請求才檢查
                success_rate = stats['success_rate']
                threshold = self.config.get('monitoring', {}).get('alert_thresholds', {}).get('error_rate', 0.1)
                
                if success_rate < (1 - threshold):
                    self._send_alert(
                        'low_success_rate',
                        f"站點 {site_name} 成功率過低: {success_rate:.2%}",
                        site_name,
                        current_time
                    )
            
            # 檢查響應時間
            avg_duration = stats['average_duration']
            response_time_threshold = self.config.get('monitoring', {}).get('alert_thresholds', {}).get('response_time', 30)
            
            if avg_duration > response_time_threshold:
                self._send_alert(
                    'slow_response',
                    f"站點 {site_name} 響應時間過慢: {avg_duration:.2f}秒",
                    site_name,
                    current_time
                )
    
    def _send_alert(self, alert_type: str, message: str, site_name: str, current_time: float):
        """發送警報"""
        alert_key = f"{alert_type}_{site_name}"
        
        # 檢查是否太頻繁
        last_alert_time = self.last_alert_times.get(alert_key, 0)
        if current_time - last_alert_time < self.min_alert_interval:
            return
        
        self.last_alert_times[alert_key] = current_time
        
        alert_data = {
            'type': alert_type,
            'message': message,
            'site_name': site_name,
            'time': datetime.fromtimestamp(current_time, timezone.utc).isoformat()
        }
        
        self.alert_history.append(alert_data)
        
        # 記錄到日誌
        logger.warning(f"警報: {message}")
        
        # 發送通知（如果配置了的話）
        self._send_notification(alert_data)
    
    def _send_notification(self, alert_data: Dict):
        """發送通知"""
        try:
            # Email 通知
            email_config = self.config.get('notifications', {}).get('email', {})
            if email_config.get('enabled'):
                self._send_email_notification(alert_data, email_config)
            
            # Discord 通知
            discord_config = self.config.get('notifications', {}).get('discord', {})
            if discord_config.get('enabled'):
                self._send_discord_notification(alert_data, discord_config)
                
        except Exception as e:
            logger.error(f"發送通知失敗: {e}")
    
    def _send_email_notification(self, alert_data: Dict, email_config: Dict):
        """發送 Email 通知"""
        # 這裡可以實作 Email 發送邏輯
        logger.info(f"應該發送 Email 通知: {alert_data['message']}")
    
    def _send_discord_notification(self, alert_data: Dict, discord_config: Dict):
        """發送 Discord 通知"""
        # 這裡可以實作 Discord Webhook 通知
        logger.info(f"應該發送 Discord 通知: {alert_data['message']}")

class MetricsExporter:
    """指標導出器"""
    
    def __init__(self, monitor: PerformanceMonitor):
        self.monitor = monitor
    
    def export_to_json(self, filepath: str):
        """導出指標到 JSON 文件"""
        try:
            stats = self.monitor.get_overall_statistics()
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
                
            logger.info(f"指標已導出到: {filepath}")
            
        except Exception as e:
            logger.error(f"導出指標失敗: {e}")
    
    def get_prometheus_metrics(self) -> str:
        """生成 Prometheus 格式的指標"""
        lines = []
        stats = self.monitor.get_overall_statistics()
        
        # 整體指標
        lines.append(f"# HELP hotel_scraper_total_requests Total number of scraping requests")
        lines.append(f"# TYPE hotel_scraper_total_requests counter")
        lines.append(f"hotel_scraper_total_requests {stats['total_requests']}")
        
        lines.append(f"# HELP hotel_scraper_success_rate Success rate of scraping requests")
        lines.append(f"# TYPE hotel_scraper_success_rate gauge")
        lines.append(f"hotel_scraper_success_rate {stats['success_rate']}")
        
        # 各站點指標
        for site_name, site_stats in stats['sites'].items():
            site_label = site_name.lower().replace('.', '_')
            
            lines.append(f"hotel_scraper_site_requests{{site=\"{site_name}\"}} {site_stats['total_requests']}")
            lines.append(f"hotel_scraper_site_success_rate{{site=\"{site_name}\"}} {site_stats['success_rate']}")
            lines.append(f"hotel_scraper_site_avg_duration{{site=\"{site_name}\"}} {site_stats['average_duration']}")
        
        return '\n'.join(lines)

# 全域監控實例
performance_monitor = PerformanceMonitor()
alert_manager = None

def initialize_monitoring(config: Dict):
    """初始化監控系統"""
    global alert_manager
    alert_manager = AlertManager(config)
    
    # 設定定期檢查
    import threading
    import time
    
    def periodic_check():
        while True:
            try:
                if alert_manager:
                    alert_manager.check_and_send_alerts(performance_monitor)
                time.sleep(300)  # 每5分鐘檢查一次
            except Exception as e:
                logger.error(f"定期檢查時發生錯誤: {e}")
    
    # 在背景執行定期檢查
    check_thread = threading.Thread(target=periodic_check, daemon=True)
    check_thread.start()
    
    logger.info("監控系統已初始化")

def get_monitoring_dashboard_data() -> Dict:
    """獲取監控儀表板資料"""
    stats = performance_monitor.get_overall_statistics()
    recent_errors = performance_monitor.get_recent_errors(5)
    
    return {
        'overall_stats': stats,
        'recent_errors': recent_errors,
        'alert_history': list(alert_manager.alert_history) if alert_manager else []
    } 