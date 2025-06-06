# app/models.py
from . import db # 從 app/__init__.py 導入 db 實例
from datetime import datetime, timezone

class SearchRequest(db.Model):
    """儲存使用者的搜尋請求"""
    __tablename__ = 'search_requests'

    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(255), nullable=False, index=True, comment="搜尋地點")
    check_in_date = db.Column(db.Date, nullable=False, index=True, comment="入住日期")
    check_out_date = db.Column(db.Date, nullable=False, index=True, comment="退房日期")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), comment="建立時間")
    is_tracking = db.Column(db.Boolean, default=True, nullable=False, index=True, comment="是否仍在追蹤")
    last_crawled_at = db.Column(db.DateTime, nullable=True, comment="上次爬取時間")
    # user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # 如果有使用者系統，可以加上

    # cascade="all, delete-orphan" 表示刪除 SearchRequest 時，其關聯的 HotelPrice 也會被刪除
    prices = db.relationship('HotelPrice', backref='search_request', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<SearchRequest {self.id}: {self.location} ({self.check_in_date.strftime("%Y-%m-%d")} - {self.check_out_date.strftime("%Y-%m-%d")})>'

class HotelPrice(db.Model):
    """儲存爬取到的飯店價格"""
    __tablename__ = 'hotel_prices'

    id = db.Column(db.Integer, primary_key=True)
    search_request_id = db.Column(db.Integer, db.ForeignKey('search_requests.id'), nullable=False, index=True, comment="關聯的搜尋請求ID")
    
    hotel_name = db.Column(db.String(512), nullable=False, index=True, comment="飯店名稱")
    price = db.Column(db.Float, nullable=False, comment="價格")
    currency = db.Column(db.String(10), nullable=False, default="TWD", comment="貨幣單位")
    source_site = db.Column(db.String(100), nullable=False, comment="價格來源網站")
    crawl_timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True, comment="爬取時間戳")
    details_url = db.Column(db.Text, nullable=True, comment="飯店詳情頁面URL")
    # room_type = db.Column(db.String(255), nullable=True) # 可以考慮增加房型等資訊

    def __repr__(self):
        return f'<HotelPrice {self.id}: {self.hotel_name} - {self.price} {self.currency} on {self.source_site}>'

# 如果未來有使用者系統，可以取消註解以下模型
# class User(db.Model):
#     __tablename__ = 'users'
#     id = db.Column(db.Integer, primary_key=True)
#     username = db.Column(db.String(80), unique=True, nullable=False)
#     email = db.Column(db.String(120), unique=True, nullable=False)
#     password_hash = db.Column(db.String(128))
#     search_requests = db.relationship('SearchRequest', backref='user', lazy='dynamic')

#     def set_password(self, password):
#         self.password_hash = generate_password_hash(password)

#     def check_password(self, password):
#         return check_password_hash(self.password_hash, password)
