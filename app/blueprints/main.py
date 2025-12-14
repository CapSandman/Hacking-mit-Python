from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from app.extensions import db
from app.models.core import Site, Meter, Reading15m
from datetime import datetime, timedelta, date, time

bp = Blueprint('main', __name__)

@bp.route('/')
@login_required
def index():
    today = datetime.utcnow().date()
    yday = today - timedelta(days=1)
    sql = db.text("""
        SELECT s.id AS site_id, s.name AS site_name, s.capacity_kwp,
                SUM(CASE WHEN d.day = :today THEN d.energy_kwh ELSE 0 END) AS kwh_today,
                SUM(CASE WHEN d.day = :yday  THEN d.energy_kwh ELSE 0 END) AS kwh_yday
        FROM sites s
        LEFT JOIN site_energy_daily d ON d.site_id = s.id
        GROUP BY s.id, s.name, s.capacity_kwp
        ORDER BY s.name;
        """)
    rows = db.session.execute(sql, {"today": today, "yday": yday}).mappings().all()

    cutoff = datetime.utcnow() - timedelta(minutes=60)
    alarm_sql = db.text("""
      SELECT s.name AS site_name, m.name AS meter_name, MAX(r.ts) AS last_ts
      FROM meters m
      JOIN sites s ON s.id = m.site_id
      LEFT JOIN readings_15m r ON r.meter_id = m.id
      GROUP BY m.id
      HAVING COALESCE(MAX(r.ts), '1970-01-01') < :cutoff
      ORDER BY s.name, m.name;
    """)
    no_data = db.session.execute(alarm_sql, {"cutoff": cutoff}).mappings().all()
    return render_template('dashboard.html', rows=rows, no_data=no_data, today=today, yday=yday)

@bp.route("/api/site/<int:site_id>/day", methods=["GET"])   # ← umjesto @bp.get
@login_required
def site_day(site_id):
    qdate_str = request.args.get("date")
    if qdate_str:
        y,m,d = map(int, qdate_str.split("-"))
        qdate = date(y,m,d)
    else:
        qdate = datetime.utcnow().date()
    start = datetime.combine(qdate, time(0,0))
    end   = datetime.combine(qdate, time(0,0)) + timedelta(days=1)
    rows = (db.session.query(Reading15m.ts, Reading15m.value_kwh)
            .join(Meter, Reading15m.meter_id==Meter.id)
            .filter(Meter.site_id==site_id, Reading15m.ts>=start, Reading15m.ts<end)
            .order_by(Reading15m.ts)
            .all())
    agg = {}
    for ts, v in rows:
        key = ts.strftime("%H:%M")
        agg[key] = float(agg.get(key, 0.0) + float(v))
    labels = list(agg.keys()); data = [agg[k] for k in labels]
    return jsonify({"labels": labels, "data": data})
