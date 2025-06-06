# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import yaml
import os
import logging

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = SQLAlchemy()
migrate = Migrate()

# 排程器設定
# jobstores = {
#     'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite') # 可以考慮將任務持久化到資料庫
# }
# executors = {
#     'default': {'type': 'threadpool', 'max_workers': 10} # 根據需要調整
# }
# job_defaults = {
#     'coalesce': False,
#     'max_instances': 3
# }
scheduler = BackgroundScheduler(
    # jobstores=jobstores, 
    # executors=executors, 
    # job_defaults=job_defaults, 
    daemon=True
)

def load_config():
    """載入設定檔 config/settings.yaml"""
    # 確保路徑相對於 __init__.py 檔案的父目錄 (即專案根目錄)
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml'))
    logger.info(f"嘗試從 {config_path} 載入設定檔")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
            logger.info("設定檔載入成功。")
            return config_data
    except FileNotFoundError:
        logger.warning(f"警告: 設定檔 {config_path} 未找到。將使用預設值。")
        return {
            'target_sites': [
                {'name': 'Agoda', 'base_url': 'https://www.agoda.com', 'enabled': True},
                {'name': 'Hotels.com', 'base_url': 'https://www.hotels.com', 'enabled': True},
                {'name': 'Booking.com', 'base_url': 'https://www.booking.com', 'enabled': True},
            ],
            'crawl_interval_hours': 2,
            'webdriver': {'browser': 'chrome', 'headless': True}
        }
    except yaml.YAMLError as e:
        logger.error(f"警告: 解析設定檔 {config_path} 錯誤: {e}。將使用預設值。")
        return { # 在 YAML 解析錯誤時也返回預設值
            'target_sites': [],
            'crawl_interval_hours': 2,
            'webdriver': {'browser': 'chrome', 'headless': True}
        }

def create_app():
    """應用程式工廠函數"""
    app = Flask(__name__)

    # 從環境變數讀取 SECRET_KEY，若無則使用預設值 (僅供開發)
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_very_secret_key_for_dev_only')
    if app.config['SECRET_KEY'] == 'a_very_secret_key_for_dev_only':
        logger.warning("警告: SECRET_KEY 使用的是預設值，請在生產環境中設定一個安全的隨機值！")

    # 資料庫設定 (使用 SQLite)
    # 確保 db 檔案路徑相對於專案根目錄
    db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if not os.path.exists(db_dir):
        os.makedirs(db_dir) # 如果 migrations 等目錄的父目錄不存在，則建立它
    db_path = os.path.join(db_dir, 'site.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    logger.info(f"資料庫將使用: {app.config['SQLALCHEMY_DATABASE_URI']}")

    # 載入自訂設定
    app_settings = load_config()
    app.config['APP_SETTINGS'] = app_settings

    # 初始化擴展
    db.init_app(app)
    migrate.init_app(app, db)

    # 註冊藍圖、匯入模型等需要在應用程式上下文中進行
    with app.app_context():
        from . import models # 確保模型被 SQLAlchemy 識別
        from .routes import main_bp
        app.register_blueprint(main_bp)

        # 初始化/重新排程所有活躍的任務
        from .services.scheduler_service import reschedule_all_active_jobs
        # reschedule_all_active_jobs() # 稍後在確認排程器正常運作後啟用

    # 啟動排程器
    if not scheduler.running:
        try:
            scheduler.start()
            logger.info("排程器已啟動。")
        except Exception as e:
            logger.error(f"啟動排程器失敗: {e}", exc_info=True)

    # 確保應用程式關閉時，排程器也一併關閉
    import atexit
    def shutdown_scheduler():
        if scheduler.running:
            logger.info("正在關閉排程器...")
            try:
                scheduler.shutdown()
                logger.info("排程器已成功關閉。")
            except Exception as e:
                logger.error(f"關閉排程器時發生錯誤: {e}", exc_info=True)
    atexit.register(shutdown_scheduler)

    return app
