from app import create_app
from app.extensions import db
from app.models.core import User
from werkzeug.security import generate_password_hash
from flask.cli import with_appcontext
import click
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, date
from sqlalchemy import func
from app.models.core import Site, Meter, Reading15m, AlarmRule
from app.notify import send_email
from app.models import core
from app.models import ppa
from app.models import *

app = create_app()

@app.cli.command("create-user")
@with_appcontext
@click.argument("username")
@click.argument("password")
def create_user_cmd(username, password):
    u = User.query.filter_by(username=username).first()
    hashed = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)
    if u:
        u.password_hash = hashed
    else:
        u = User(username=username, password_hash=hashed)
        db.session.add(u)
    db.session.commit()
    click.echo("Done.")

@app.cli.command("rebuild-daily")
@with_appcontext
def rebuild_daily_cmd():
    # očisti tabelu i izgradi ponovo iz readings_15m
    sql_delete = db.text("DELETE FROM site_energy_daily")
    db.session.execute(sql_delete)
    db.session.commit()

    sql_insert = db.text("""
      INSERT INTO site_energy_daily (site_id, day, energy_kwh)
      SELECT s.id AS site_id, DATE(r.ts) AS day, SUM(r.value_kwh) AS energy_kwh
      FROM sites s
      JOIN meters m ON m.site_id = s.id
      JOIN readings_15m r ON r.meter_id = m.id
      GROUP BY s.id, DATE(r.ts)
      ORDER BY s.id, DATE(r.ts)
    """)
    db.session.execute(sql_insert)
    db.session.commit()
    click.echo("Rebuilt site_energy_daily.")

def check_alarms():
    with app.app_context():
        now = datetime.utcnow()

        # NO DATA
        rules_nd = AlarmRule.query.filter_by(rule_type='no_data', is_active=True).all()
        for r in rules_nd:
            cutoff = now - timedelta(minutes=int(r.minutes_no_data or 60))
            last_ts = (db.session.query(func.max(Reading15m.ts))
                       .join(Meter, Reading15m.meter_id==Meter.id)
                       .filter(Meter.site_id==r.site_id)
                       .scalar())
            if not last_ts or last_ts < cutoff:
                site = Site.query.get(r.site_id)
                subj = f"[SFM] NO DATA: {site.name}"
                body = (f"Site: {site.name}\n"
                        f"Rule: no_data >= {r.minutes_no_data} min\n"
                        f"Last reading: {last_ts}\n"
                        f"Time (UTC): {now}")
                send_email(subj, body, r.email_to)

        # LOW PRODUCTION (today vs expected)
        rules_lp = AlarmRule.query.filter_by(rule_type='low_prod', is_active=True).all()
        for r in rules_lp:
            site = Site.query.get(r.site_id)
            expect = float(r.expect_kwh_per_kwp or 0) * float(site.capacity_kwp or 0)
            start = datetime.combine(date.today(), datetime.min.time())
            end = start + timedelta(days=1)
            total = (db.session.query(func.sum(Reading15m.value_kwh))
                     .join(Meter, Reading15m.meter_id==Meter.id)
                     .filter(Meter.site_id==site.id,
                             Reading15m.ts>=start, Reading15m.ts<end)
                     .scalar()) or 0.0
            if expect > 0 and total < expect:
                subj = f"[SFM] LOW PRODUCTION: {site.name}"
                body = (f"Site: {site.name}\n"
                        f"Expected today >= {expect:.2f} kWh "
                        f"(target {float(r.expect_kwh_per_kwp):.2f} kWh/kWp), "
                        f"actual {total:.2f} kWh")
                send_email(subj, body, r.email_to)

# pokreni pozadinski scheduler (15 min)
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(check_alarms, 'interval', minutes=15, id='check_alarms')
scheduler.start()



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=False, host="0.0.0.0", port=5001)
