# app/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from . import db
from .models import SearchRequest, HotelPrice
from .forms import SearchForm # 稍後會建立這個表單
from datetime import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/', methods=['GET', 'POST'])
def index():
    # form = SearchForm() # 稍後會取消註解並使用表單
    # if form.validate_on_submit():
    #     try:
    #         new_search = SearchRequest(
    #             location=form.location.data,
    #             check_in_date=form.check_in_date.data,
    #             check_out_date=form.check_out_date.data
    #         )
    #         db.session.add(new_search)
    #         db.session.commit()
    #         flash('搜尋請求已新增，系統將開始為您追蹤價格！', 'success')
    #         # 觸發一次立即爬取 (可選)
    #         # from .services.scheduler_service import schedule_price_check
    #         # schedule_price_check(new_search.id, run_now=True)
    #         return redirect(url_for('main.index'))
    #     except Exception as e:
    #         db.session.rollback()
    #         flash(f'新增搜尋請求失敗: {e}', 'danger')
    
    active_searches = SearchRequest.query.filter_by(is_tracking=True).order_by(SearchRequest.created_at.desc()).all()
    # return render_template('index.html', form=form, searches=active_searches)
    return render_template('index.html', searches=active_searches) # 暫時不使用表單

@main_bp.route('/search/<int:search_id>')
def search_details(search_id):
    search_request = db.get_or_404(SearchRequest, search_id)
    prices = HotelPrice.query.filter_by(search_request_id=search_id).order_by(HotelPrice.crawl_timestamp.desc(), HotelPrice.price.asc()).all()
    
    # 準備圖表數據
    chart_data = {}
    # { 'Hotel A': { 'Agoda': [(timestamp1, price1), (timestamp2, price2)], 'Booking.com': [...] }, ... }
    for price_entry in prices:
        hotel_name = price_entry.hotel_name
        source = price_entry.source_site
        timestamp_ms = int(price_entry.crawl_timestamp.timestamp() * 1000) # JavaScript expects milliseconds
        
        if hotel_name not in chart_data:
            chart_data[hotel_name] = {}
        if source not in chart_data[hotel_name]:
            chart_data[hotel_name][source] = []
        chart_data[hotel_name][source].append([timestamp_ms, price_entry.price])

    # 為每個來源的數據排序，確保圖表線條正確
    for hotel in chart_data:
        for source in chart_data[hotel]:
            chart_data[hotel][source].sort(key=lambda x: x[0])
            
    return render_template('search_details.html', search_request=search_request, prices=prices, chart_data=chart_data)

@main_bp.route('/search/<int:search_id>/toggle_tracking', methods=['POST'])
def toggle_tracking(search_id):
    search_request = db.get_or_404(SearchRequest, search_id)
    search_request.is_tracking = not search_request.is_tracking
    db.session.commit()
    status = "開始追蹤" if search_request.is_tracking else "停止追蹤"
    flash(f'已更新 {search_request.location} 的追蹤狀態為: {status}', 'info')
    return redirect(request.referrer or url_for('main.index'))

@main_bp.route('/search/<int:search_id>/delete', methods=['POST'])
def delete_search(search_id):
    search_request = db.get_or_404(SearchRequest, search_id)
    try:
        db.session.delete(search_request)
        db.session.commit()
        flash(f'已刪除搜尋請求: {search_request.location}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除搜尋請求失敗: {e}', 'danger')
    return redirect(url_for('main.index'))

# 之後可以加入更多路由，例如顯示特定飯店的歷史價格等
