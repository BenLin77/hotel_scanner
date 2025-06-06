# app/services/scheduler_service.py
from .. import scheduler, db # 從 app/__init__.py 導入 scheduler 和 db
from ..models import SearchRequest
from .scraper_service import scrape_prices_for_request
from flask import current_app
import logging

logger = logging.getLogger(__name__)

def job_wrapper(search_request_id):
    """執行爬取任務的包裝函數，確保在應用程式上下文中執行"""
    app = current_app._get_current_object() # 獲取當前的 Flask app 實例
    with app.app_context():
        search_request = db.session.get(SearchRequest, search_request_id)
        if search_request and search_request.is_tracking:
            try:
                logger.info(f"排程任務開始: 爬取請求 ID {search_request_id}")
                scrape_prices_for_request(search_request, app.config['APP_SETTINGS'])
                logger.info(f"排程任務完成: 爬取請求 ID {search_request_id}")
            except Exception as e:
                logger.error(f"爬取請求 ID {search_request_id} 時發生錯誤: {e}", exc_info=True)
        elif not search_request:
            logger.warning(f"排程任務: 找不到請求 ID {search_request_id}，可能已被刪除。")
            # 可以考慮移除此任務
            remove_scheduled_job(search_request_id)
        elif not search_request.is_tracking:
            logger.info(f"排程任務: 請求 ID {search_request_id} 已取消追蹤，跳過爬取。")
            # 也可以考慮移除此任務，或者讓它在下次檢查時自然跳過
            # remove_scheduled_job(search_request_id) # 如果希望取消追蹤就立即移除任務

def schedule_price_check(search_request_id, run_now=False):
    """為指定的 SearchRequest ID安排或更新爬取任務"""
    app = current_app._get_current_object()
    interval_hours = app.config.get('APP_SETTINGS', {}).get('crawl_interval_hours', 2)
    job_id = f'crawl_request_{search_request_id}'

    # 檢查任務是否已存在
    existing_job = scheduler.get_job(job_id)
    if existing_job:
        # 更新現有任務的觸發器 (如果需要調整間隔)
        existing_job.reschedule(trigger='interval', hours=interval_hours)
        logger.info(f"已更新排程任務 {job_id}，間隔為 {interval_hours} 小時")
    else:
        # 新增任務
        scheduler.add_job(
            func=job_wrapper,
            args=[search_request_id],
            trigger='interval',
            hours=interval_hours,
            id=job_id,
            name=f'Price Crawl for SR-{search_request_id}',
            replace_existing=True # 如果因某些原因任務已存在但 get_job 未取到，則替換
        )
        logger.info(f"已新增排程任務 {job_id}，間隔為 {interval_hours} 小時")

    if run_now:
        # 如果需要立即執行一次 (例如，剛新增請求時)
        # scheduler.modify_job(job_id, next_run_time=datetime.now(timezone.utc) + timedelta(seconds=5))
        # 或者直接調用一次 (更簡單，但不會通過排程器)
        logger.info(f"觸發立即執行任務 {job_id}")
        job_wrapper(search_request_id) 

def remove_scheduled_job(search_request_id):
    """移除指定 SearchRequest ID 的排程任務"""
    job_id = f'crawl_request_{search_request_id}'
    try:
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f"已成功移除排程任務: {job_id}")
        else:
            logger.info(f"排程任務 {job_id} 不存在，無需移除。")
    except Exception as e:
        logger.error(f"移除排程任務 {job_id} 時發生錯誤: {e}")

def reschedule_all_active_jobs():
    """重新排程所有活躍的追蹤請求 (例如，應用啟動時)"""
    app = current_app._get_current_object()
    with app.app_context():
        active_searches = SearchRequest.query.filter_by(is_tracking=True).all()
        if not active_searches:
            logger.info("沒有活躍的追蹤請求需要排程。")
            return
            
        logger.info(f"正在為 {len(active_searches)} 個活躍的追蹤請求設定排程...")
        for sr in active_searches:
            schedule_price_check(sr.id)
        logger.info("所有活躍追蹤請求的排程設定完成。");

# 可以在 app/__init__.py 中應用啟動時調用 reschedule_all_active_jobs
# 以確保重啟後任務仍然存在。
