from datetime import datetime
from app.extensions import db

class Site(db.Model):
    __tablename__ = 'sites'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(225))
    capacity_kwp = db.Column(db.Numeric(10, 2), nullable=False)
    timezone = db.Column(db.String(64), nullable=False, default='Europe/Berlin')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    meters = db.relationship('Meter', back_populates='site', cascade='all, delete-orphan')

class Meter(db.Model):
    __tablename__ = "meters"
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    interval_minutes = db.Column(db.Integer, nullable=False, default=15)
    unit = db.Column(db.String(16), nullable=False, default='kWh')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    site = db.relationship('Site', back_populates='meters')
    readings = db.relationship('Reading15m', back_populates='meter', cascade='all, delete-orphan')

class Reading15m(db.Model):
    __tablename__ = "readings_15m"
    id = db.Column(db.BigInteger, primary_key=True)
    meter_id = db.Column(db.Integer, db.ForeignKey('meters.id'), nullable=False)
    ts = db.Column(db.DateTime, nullable=False)
    value_kwh = db.Column(db.Numeric(12,4), nullable=False)

    meter = db.relationship('Meter', back_populates='readings')

class User(db.Model):
    __tablename__ = "users2"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # AKO želiš moći deaktivirati nalog, nemoj zvati kolonu is_active (zasjenjuje property)!
    #active = db.Column('is_active', db.Boolean, nullable=False, default=True)

    #@property
    #def is_active(self):
        # Flask-Login će ovo zvati; vraćamo vrijednost iz kolone
        #return bool(self.active)

class AlarmRule(db.Model):
    __tablename__ = 'alarm_rules'
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)

    # 'no_data' | 'low_prod'
    rule_type = db.Column(db.String(32), nullable=False)

    # za 'no_data': koristi se minutes_no_data, za 'low_prod': expect_kwh_per_kwp
    minutes_no_data = db.Column(db.Integer)              # npr. 60
    expect_kwh_per_kwp = db.Column(db.Numeric(10,3))     # npr. 3.5

    email_to = db.Column(db.String(255))                 # opcioni override
    #is_active = db.Column(db.Boolean, default=True, nullable=False)

    site = db.relationship('Site')

