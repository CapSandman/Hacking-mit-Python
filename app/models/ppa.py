from datetime import datetime, date
from app.extensions import db
from sqlalchemy.orm import relationship

class PPATariff(db.Model):
    __tablename__ = "ppa_tariffs"
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)

    # tip modela: 'fixed' | 'cropex_multiplier' | 'cropex_markup'
    kind = db.Column(db.String(32), nullable=False, default="cropex_multiplier")

    # parametri:
    # fixed: fixed_price_eur_mwh
    fixed_price_eur_mwh = db.Column(db.Numeric(12, 4))
    # cropex_multiplier: unit_price = coeff * Pck + adder
    coeff = db.Column(db.Numeric(12, 6), default=1.0)
    adder_eur_mwh = db.Column(db.Numeric(12, 4), default=0.0)
    # cropex_markup: unit_price = Pck + markup_eur_mwh
    markup_eur_mwh = db.Column(db.Numeric(12, 4), default=0.0)

    currency = db.Column(db.String(8), default="EUR")
    valid_from = db.Column(db.Date, nullable=False, default=date.today)
    valid_to   = db.Column(db.Date)

    is_active = db.Column(db.Boolean, default=True)

class DayAheadPrice(db.Model):
    __tablename__ = "day_ahead_prices"
    id = db.Column(db.BigInteger, primary_key=True)
    # satni timestamp (početak sata) u UTC ili lokalno – koristi isto kao za readings agregaciju
    ts = db.Column(db.DateTime, nullable=False, index=True)
    market = db.Column(db.String(32), nullable=False, default="CROPEX")
    price_eur_mwh = db.Column(db.Numeric(12, 4), nullable=False)

    __table_args__ = (db.UniqueConstraint("market", "ts", name="uq_market_ts"),)

class Invoice(db.Model):
    __tablename__ = "invoices"
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id"), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end   = db.Column(db.Date, nullable=False)
    currency = db.Column(db.String(8), default="EUR")
    total_amount = db.Column(db.Numeric(14, 2), default=0)
    status = db.Column(db.String(32), default="draft")  # draft|issued|paid|void
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # NEW: veza na stavke – ORM kaskada
    items = relationship(
        "InvoiceItem",
        backref="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class InvoiceItem(db.Model):
    __tablename__ = "invoice_items"
    id = db.Column(db.BigInteger, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False, index=True)
    ts = db.Column(db.DateTime, nullable=False)  # hourly bucket
    energy_mwh = db.Column(db.Numeric(14, 6), nullable=False)
    unit_price_eur_mwh = db.Column(db.Numeric(12, 4), nullable=False)
    line_amount_eur = db.Column(db.Numeric(14, 4), nullable=False)

    __table_args__ = (db.UniqueConstraint("invoice_id", "ts", name="uq_invoice_ts"),)
