# app/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SubmitField
from wtforms.validators import DataRequired, ValidationError
from datetime import date

class SearchForm(FlaskForm):
    location = StringField('地點 (例如：日本岡山)', validators=[DataRequired(message="請輸入地點")])
    check_in_date = DateField('入住日期', validators=[DataRequired(message="請輸入入住日期")], format='%Y-%m-%d')
    check_out_date = DateField('退房日期', validators=[DataRequired(message="請輸入退房日期")], format='%Y-%m-%d')
    submit = SubmitField('開始搜尋與追蹤')

    def validate_check_in_date(self, field):
        if field.data < date.today():
            raise ValidationError("入住日期不能早於今天")

    def validate_check_out_date(self, field):
        if self.check_in_date.data and field.data <= self.check_in_date.data:
            raise ValidationError("退房日期必須晚於入住日期")
