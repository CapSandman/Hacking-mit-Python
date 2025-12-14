# app/blueprints/uploads.py
import csv
from datetime import datetime
from io import TextIOWrapper
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import func
from app.extensions import db
from app.models.core import Meter, Reading15m

bp = Blueprint("uploads", __name__)


@bp.route("/")
@login_required
def index():
    meters = Meter.query.order_by(Meter.id.desc()).all()
    return render_template("uploads/upload.html", meters=meters)


def _parse_ts(ts_str: str) -> datetime:
    """Pokušaj parsiranja timestamp stringa u datetime."""
    ts_str = (ts_str or "").strip()
    if not ts_str:
        raise ValueError("empty timestamp")

    # ISO 8601 (npr. 2025-10-09T06:15:00 ili 2025-10-09 06:15:00)
    try:
        # fromisoformat prihvata i razmak između datuma i vremena
        return datetime.fromisoformat(ts_str)
    except Exception:
        pass

    # Klasični 'YYYY-MM-DD HH:MM'
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts_str, fmt)
        except Exception:
            continue

    # Accepting EU format
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(ts_str, fmt)
        except Exception:
            continue

    raise ValueError(f"unsupported timestamp format: {ts_str}")


@bp.route("/csv", methods=["POST"])
@login_required
def upload_csv():
    meter_id = request.form.get("meter_id", type=int)
    file = request.files.get("file")

    if not meter_id or not file:
        flash("Meter i CSV fajl su obavezni.", "error")
        return redirect(url_for("uploads.index"))

    meter = Meter.query.get(meter_id)
    if not meter:
        flash("Nepostojeći meter.", "error")
        return redirect(url_for("uploads.index"))

    # Čitanje CSV-a (podrži BOM preko utf-8-sig)
    inserted_or_updated = 0
    errors = 0
    affected_days = set()

    try:
        wrapper = TextIOWrapper(file.stream, encoding="utf-8-sig", newline="")
        reader = csv.DictReader(wrapper)

        # Validacija zaglavlja
        headers = {h.strip().lower() for h in (reader.fieldnames or [])}
        required = {"timestamp", "value_kwh"}
        # dozvoli i sinonime
        ok = ({"timestamp"} <= headers or {"ts"} <= headers) and (
            {"value_kwh"} <= headers or {"kwh"} <= headers
        )
        if not ok:
            flash(
                "Invalid CSV headers. Fields are required: "
                "`timestamp` i `value_kwh` (allowed synonyms: `ts`, `kwh`).",
                "error",
            )
            return redirect(url_for("uploads.index"))

        for lineno, row in enumerate(reader, start=2):  # +1 za header, pa start=2
            try:
                ts_str = (row.get("timestamp") or row.get("ts") or "").strip()
                val_str = (row.get("value_kwh") or row.get("kwh") or "").strip()

                ts = _parse_ts(ts_str)
                val = float(val_str)

                # Ako već postoji zapis za (meter_id, ts) — ažuriraj; inače kreiraj
                existing = Reading15m.query.filter_by(meter_id=meter_id, ts=ts).first()
                if existing:
                    # Ažuriraj samo ako se vrednost promijenila
                    if float(existing.value_kwh) != val:
                        existing.value_kwh = val
                else:
                    db.session.add(Reading15m(meter_id=meter_id, ts=ts, value_kwh=val))

                inserted_or_updated += 1
                affected_days.add(ts.date())

            except Exception as e:
                errors += 1
                # Loguj u konzolu, korisniku daj zbirno
                print(f"CSV line {lineno} error: {e}")

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print("CSV upload fatal error:", e)
        flash("Error reading CSV. Check format and encoding.", "error")
        return redirect(url_for("uploads.index"))

    # Inkrementalni obračun dnevnih suma za pogođene dane (site_energy_daily)
    # Pretpostavka: u bazi postoji tabela `site_energy_daily` i UNIQUE(site_id, day).
    try:
        site_id = meter.site_id
        updated_days = 0

        for day in affected_days:
            total = (
                db.session.query(func.sum(Reading15m.value_kwh))
                .filter(
                    Reading15m.meter_id.in_(
                        db.session.query(Meter.id).filter(Meter.site_id == site_id)
                    ),
                    func.date(Reading15m.ts) == day,
                )
                .scalar()
            ) or 0.0

            # UPSERT dnevnog zbira
            db.session.execute(
                db.text(
                    """
                    INSERT INTO site_energy_daily (site_id, day, energy_kwh)
                    VALUES (:site_id, :day, :energy)
                    ON DUPLICATE KEY UPDATE energy_kwh = VALUES(energy_kwh)
                    """
                ),
                {"site_id": site_id, "day": day, "energy": float(total)},
            )
            updated_days += 1

        db.session.commit()

        msg = f"Uvezeno/a ili ažurirano {inserted_or_updated} redova"
        if errors:
            msg += f", errors: {errors}"
        msg += f". Refreshed: {updated_days}."
        flash(msg, "success" if errors == 0 else "error")

    except Exception as e:
        db.session.rollback()
        print("Daily aggregate upsert error:", e)
        # I dalje obavesti korisnika o osnovnom importu, ali naznači da agregati nisu ažurirani
        msg = (
            f"Imported or updated {inserted_or_updated} rows, errors: {errors}. "
            f"Note: failed to update daily aggregates."
        )
        flash(msg, "error")

    return redirect(url_for("uploads.index"))