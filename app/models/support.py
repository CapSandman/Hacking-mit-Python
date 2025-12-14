from app.extensions import db

class TestItem(db.Model):
    __tablename__ = "testitems"
    id = db.Column(db.Integer, primary_key=True)
    priority = db.Column(db.String(32), nullable=True)
    username = db.Column(db.String(80), nullable=True)
    title = db.Column(db.String(255), nullable=True)
    info = db.Column(db.Text, nullable=True) # dugi opis (može sadržati bilo šta)