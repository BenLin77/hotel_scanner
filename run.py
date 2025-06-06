# run.py
from app import create_app, db
# from app.models import SearchRequest, HotelPrice # 稍後會建立這些模型
from flask_migrate import Migrate

app = create_app()
migrate = Migrate(app, db)

if __name__ == '__main__':
    app.run(debug=True)
