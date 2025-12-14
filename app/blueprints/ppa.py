from datetime import date, datetime, timedelta
from decimal import Decimal
from io import StringIO, BytesIO
import csv
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required
from sqlalchemy import func
from app.extensions import db
from app.models.core import Site, Meter, Reading15m
from app.models.ppa import PPATariff, DayAheadPrice, Invoice, InvoiceItem
from flask import current_app
from app.currency import get_bam_rate, get_pdv_percent
from app.pdf import generate_invoice_pdf
import os

bp = Blueprint("ppa", __name__)

# ---------- helpers ----------
def get_active_tariff(site_id: int, day: date) -> PPATariff | None:
    q = (PPATariff.query.filter(
            PPATariff.site_id==site_id,
            PPATariff.is_active==True,
            PPATariff.valid_from <= day,
            (PPATariff.valid_to.is_(None) | (PPATariff.valid_to >= day))
        ).order_by(PPATariff.valid_from.desc()))
    return q.first()

def price_for_hour(ts_hour: datetime, tariff: PPATariff) -> Decimal:
    """Vrati cijenu €/MWh za dati sat prema tarifi. Ako treba Pck, uzmi iz DayAheadPrice."""
    if tariff.kind == "fixed":
        return Decimal(tariff.fixed_price_eur_mwh or 0)
    # Pck lookup
    dap = DayAheadPrice.query.filter_by(ts=ts_hour).first()
    pck = Decimal(dap.price_eur_mwh) if dap else Decimal(0)
    if tariff.kind == "cropex_multiplier":
        coeff = Decimal(tariff.coeff or 1)
        adder = Decimal(tariff.adder_eur_mwh or 0)
        return coeff * pck + adder
    if tariff.kind == "cropex_markup":
        markup = Decimal(tariff.markup_eur_mwh or 0)
        return pck + markup
    # default fallback
    return pck

def hourly_generation_mwh(site_id: int, start: datetime, end: datetime) -> list[dict]:
    """
    Vrati listu dictova {ts_hour, energy_mwh} agregirajući 15-min kWh u sate (÷1000).
    """
    sql = db.text("""
        SELECT
          DATE_FORMAT(r.ts, '%Y-%m-%d %H:00:00') AS ts_hour,
          SUM(r.value_kwh) / 1000.0 AS energy_mwh
        FROM readings_15m r
        JOIN meters m ON m.id = r.meter_id
        WHERE m.site_id = :site_id AND r.ts >= :start AND r.ts < :end
        GROUP BY DATE_FORMAT(r.ts, '%Y-%m-%d %H:00:00')
        ORDER BY ts_hour
    """)
    rows = db.session.execute(sql, {"site_id": site_id, "start": start, "end": end}).mappings().all()
    return [{"ts_hour": datetime.fromisoformat(r["ts_hour"]), "energy_mwh": float(r["energy_mwh"])} for r in rows]

# ---------- pages ----------
@bp.route("/contracts")
@login_required
def contracts():
    rows = (db.session.query(PPATariff, Site)
            .join(Site, PPATariff.site_id==Site.id)
            .order_by(Site.name, PPATariff.valid_from.desc())
            .all())
    return render_template("ppa/contracts.html", rows=rows)

@bp.route("/contracts/new", methods=["GET","POST"])
@login_required
def new_contract():
    sites = Site.query.order_by(Site.name).all()
    if request.method == "POST":
        t = PPATariff(
            site_id=request.form.get("site_id", type=int),
            name=request.form.get("name"),
            kind=request.form.get("kind"),
            fixed_price_eur_mwh=request.form.get("fixed_price_eur_mwh", type=float),
            coeff=request.form.get("coeff", type=float),
            adder_eur_mwh=request.form.get("adder_eur_mwh", type=float),
            markup_eur_mwh=request.form.get("markup_eur_mwh", type=float),
            currency="EUR",
            valid_from=request.form.get("valid_from"),
            valid_to=request.form.get("valid_to") or None,
            is_active=bool(request.form.get("is_active")),
        )
        db.session.add(t); db.session.commit()
        flash("PPA contract saved", "success")
        return redirect(url_for("ppa.contracts"))
    return render_template("ppa/contract_form.html", sites=sites, tariff=None)

@bp.route("/contracts/<int:tid>/edit", methods=["GET","POST"])
@login_required
def edit_contract(tid):
    tariff = PPATariff.query.get_or_404(tid)
    sites = Site.query.order_by(Site.name).all()
    if request.method == "POST":
        tariff.site_id = request.form.get("site_id", type=int)
        tariff.name = request.form.get("name")
        tariff.kind = request.form.get("kind")
        tariff.fixed_price_eur_mwh = request.form.get("fixed_price_eur_mwh", type=float)
        tariff.coeff = request.form.get("coeff", type=float)
        tariff.adder_eur_mwh = request.form.get("adder_eur_mwh", type=float)
        tariff.markup_eur_mwh = request.form.get("markup_eur_mwh", type=float)
        tariff.valid_from = request.form.get("valid_from")
        tariff.valid_to = request.form.get("valid_to") or None
        tariff.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("PPA contract updated", "success")
        return redirect(url_for("ppa.contracts"))
    return render_template("ppa/contract_form.html", sites=sites, tariff=tariff)

@bp.route("/contracts/<int:tid>/delete", methods=["POST"], endpoint="delete_contract")
@login_required
def delete_contract(tid):
    from app.models.ppa import PPATariff
    from app.extensions import db
    t = PPATariff.query.get_or_404(tid)

    # Napomena: postojeće fakture nisu vezane za konkretan tariff record,
    # pa brisanje ugovora NE mijenja ranije izračunate/pohranjene fakture.
    db.session.delete(t)
    db.session.commit()
    flash("PPA contract deleted.", "success")
    return redirect(url_for("ppa.contracts"))


@bp.route("/prices")
@login_required
def prices():
    # lista zadnjih 14 dana cijena
    latest = (db.session.query(DayAheadPrice.ts, DayAheadPrice.price_eur_mwh)
              .order_by(DayAheadPrice.ts.desc()).limit(24*14).all())
    return render_template("ppa/prices.html", rows=latest)

@bp.route("/prices/upload", methods=["POST"])
@login_required
def upload_prices():
    f = request.files.get("file")
    if not f:
        flash("Odaberi CSV sa cijenama.", "error")
        return redirect(url_for("ppa.prices"))
    # CSV: ts, price_eur_mwh  (ts = 'YYYY-MM-DD HH:00:00')
    reader = csv.DictReader(StringIO(f.stream.read().decode("utf-8-sig")))
    inserted, updated, errors = 0, 0, 0
    for i, row in enumerate(reader, start=2):
        try:
            ts = datetime.fromisoformat((row.get("ts") or row.get("timestamp")).strip())
            price = float((row.get("price_eur_mwh") or row.get("price")).strip())
            existing = DayAheadPrice.query.filter_by(ts=ts, market="CROPEX").first()
            if existing:
                existing.price_eur_mwh = price; updated += 1
            else:
                db.session.add(DayAheadPrice(ts=ts, market="CROPEX", price_eur_mwh=price)); inserted += 1
        except Exception as e:
            errors += 1
            print(f"Prices CSV line {i} error: {e}")
    db.session.commit()
    flash(f"Imported prices. Inserted {inserted}, updated {updated}, errors {errors}", "success" if errors==0 else "error")
    return redirect(url_for("ppa.prices"))

@bp.route("/preview", methods=["GET"])
@login_required
def preview():
    site_id = request.args.get("site_id", type=int)
    if not site_id:
        flash("Odaberi site za preview.", "error")
        return redirect(url_for("ppa.contracts"))
    # default period: prethodni kalendarski mjesec
    today = date.today().replace(day=1)
    period_end = today - timedelta(days=1)
    period_start = period_end.replace(day=1)

    # granice (pretpostavka: ts su UTC-naivni, kao u ostatku app)
    start_dt = datetime.combine(period_start, datetime.min.time())
    end_dt   = datetime.combine(period_end + timedelta(days=1), datetime.min.time())

    # aktivna tarifa
    t = get_active_tariff(site_id, period_start) or get_active_tariff(site_id, period_end)
    if not t:
        flash("Nema aktivne PPA tarife za odabrani site u tom periodu.", "error")
        return redirect(url_for("ppa.contracts"))

    hours = hourly_generation_mwh(site_id, start_dt, end_dt)
    lines = []
    total = Decimal("0")
    for h in hours:
        ts_hour = h["ts_hour"]
        e = Decimal(str(h["energy_mwh"]))
        unit = price_for_hour(ts_hour, t)
        amt = (e * unit).quantize(Decimal("0.0001"))
        total += amt
        lines.append({"ts": ts_hour, "energy_mwh": float(e), "unit_price": float(unit), "amount": float(amt)})

    return render_template("ppa/preview.html",
                           site=Site.query.get(site_id),
                           tariff=t,
                           period_start=period_start,
                           period_end=period_end,
                           lines=lines,
                           total=float(total))

@bp.route("/generate", methods=["POST"])
@login_required
def generate_invoice():
    site_id = request.form.get("site_id", type=int)
    period_start = date.fromisoformat(request.form.get("period_start"))
    period_end   = date.fromisoformat(request.form.get("period_end"))

    t = get_active_tariff(site_id, period_start) or get_active_tariff(site_id, period_end)
    if not t:
        flash("Nema aktivne PPA tarife za period.", "error")
        return redirect(url_for("ppa.preview") + f"?site_id={site_id}")

    start_dt = datetime.combine(period_start, datetime.min.time())
    end_dt   = datetime.combine(period_end + timedelta(days=1), datetime.min.time())
    hours = hourly_generation_mwh(site_id, start_dt, end_dt)

    inv = Invoice(site_id=site_id, period_start=period_start, period_end=period_end, currency="EUR", status="draft")
    db.session.add(inv); db.session.flush()

    total = Decimal("0")
    items = []
    for h in hours:
        ts_hour = h["ts_hour"]
        e = Decimal(str(h["energy_mwh"]))
        unit = price_for_hour(ts_hour, t)
        amt = (e * unit).quantize(Decimal("0.0001"))
        total += amt
        items.append(InvoiceItem(invoice_id=inv.id, ts=ts_hour,
                                 energy_mwh=e, unit_price_eur_mwh=unit, line_amount_eur=amt))
    db.session.bulk_save_objects(items)
    inv.total_amount = total.quantize(Decimal("0.01"))
    db.session.commit()

    flash(f"Invoice #{inv.id} created. Total = {inv.total_amount} EUR", "success")
    return redirect(url_for("ppa.view_invoice", iid=inv.id))

@bp.route("/invoice/<int:iid>")
@login_required
def view_invoice(iid):
    inv = Invoice.query.get_or_404(iid)
    items = InvoiceItem.query.filter_by(invoice_id=iid).order_by(InvoiceItem.ts).all()
    site = Site.query.get(inv.site_id)

    from app.currency import get_bam_rate, get_pdv_percent
    rate = get_bam_rate(inv.period_end)
    pdv = get_pdv_percent()

    total_eur = float(inv.total_amount)
    total_km_net = total_eur * rate
    pdv_amount = total_km_net * (pdv/100.0)
    grand_total = total_km_net + pdv_amount

    return render_template("ppa/invoice.html", invoice=inv, items=items, site=site,
                           rate=rate, pdv=pdv, total_km_net=total_km_net,
                           pdv_amount=pdv_amount, grand_total=grand_total)

@bp.route("/invoice/<int:iid>/export.csv")
@login_required
def export_invoice_csv(iid):
    inv = Invoice.query.get_or_404(iid)
    items = InvoiceItem.query.filter_by(invoice_id=iid).order_by(InvoiceItem.ts).all()
    sio = StringIO()
    w = csv.writer(sio)
    w.writerow(["ts","energy_mwh","unit_price_eur_mwh","amount_eur"])
    for it in items:
        w.writerow([it.ts.isoformat(), float(it.energy_mwh), float(it.unit_price_eur_mwh), float(it.line_amount_eur)])
    mem = BytesIO(sio.getvalue().encode("utf-8"))
    fname = f"invoice_{inv.id}_{inv.period_start}_{inv.period_end}.csv"
    return send_file(mem, as_attachment=True, download_name=fname, mimetype="text/csv")


@bp.route("/invoice/<int:iid>/export.pdf")
@login_required
def export_invoice_pdf(iid):
    inv = Invoice.query.get_or_404(iid)
    items = InvoiceItem.query.filter_by(invoice_id=iid).order_by(InvoiceItem.ts).all()
    site = Site.query.get_or_404(inv.site_id)

    from app.currency import get_bam_rate, get_pdv_percent
    rate = get_bam_rate(inv.period_end)
    pdv  = get_pdv_percent()

    # LOGO
    logo_path = os.path.join(current_app.root_path, "static", "MZ Solar(transparent).png")
    if not os.path.isfile(logo_path):
        logo_path = None

    # PRODAVAC (iz .env-a; stavi svoje podatke)
    seller = {
        "name":  os.getenv("COMPANY_NAME",  "MZ Solar d.o.o."),
        "addr":  os.getenv("COMPANY_ADDR",  "Vuka Karadžića 35"),
        "vat":   os.getenv("COMPANY_VAT",   "PDV: 123456789"),
        "iban":  os.getenv("COMPANY_IBAN",  "IBAN: BA39 1110 0000 0000 123"),
        "bank":  os.getenv("COMPANY_BANK",  "Banka: NLB Banka d.d."),
        "email": os.getenv("COMPANY_EMAIL", "info@mzsolar.com"),
        "phone": os.getenv("COMPANY_PHONE", "+387 33 000 000"),
    }

    # KUPAC – za sada placeholder (ili povuci iz Site ako imaš polja)
    buyer = {
        "name":  os.getenv("BUYER_NAME",  "Kupac d.o.o."),
        "addr":  os.getenv("BUYER_ADDR",  "Adresa kupca 10, 10000 Zagreb"),
        "vat":   os.getenv("BUYER_VAT",   "OIB: 987654321"),
        "email": os.getenv("BUYER_EMAIL", "kupac@example.com"),
    }

    pdf = generate_invoice_pdf(
        invoice=inv, items=items, site=site,
        rate_bam_per_eur=rate, pdv_percent=pdv,
        logo_path=logo_path, seller=seller, buyer=buyer
    )
    fname = f"invoice_{inv.id}_{inv.period_start}_{inv.period_end}.pdf"
    return send_file(pdf, as_attachment=True, download_name=fname, mimetype="application/pdf")

@bp.route("/invoices")
@login_required
def invoices_list():
    # filteri (opciono)
    site_id = request.args.get("site_id", type=int)
    q = db.session.query(Invoice, Site).join(Site, Invoice.site_id == Site.id)

    if site_id:
        q = q.filter(Invoice.site_id == site_id)

    q = q.order_by(Invoice.created_at.desc())
    rows = q.limit(200).all()  # jednostavno ograničenje; lako dodaćemo paginaciju kasnije

    sites = Site.query.order_by(Site.name).all()
    return render_template("ppa/invoices.html", rows=rows, sites=sites, site_id=site_id)

@bp.route("/invoice/<int:iid>/delete", methods=["POST"], endpoint="invoice_delete")
@login_required
def invoice_delete(iid):
    inv = Invoice.query.get_or_404(iid)
    # Ako želiš zaštitu: ne dozvoli brisanje 'paid'/'issued'
    # if inv.status in ("issued", "paid"):
    #     flash("Ne možeš obrisati issued/paid fakturu.", "error")
    #     return redirect(url_for("ppa.invoices_list"))

    db.session.delete(inv)  # zbog relationship(cascade), brišu se i stavke
    db.session.commit()
    flash(f"Invoice #{iid} obrisan.", "success")
    return redirect(url_for("ppa.invoices_list"))

@bp.route("/invoice/<int:iid>/status", methods=["POST"], endpoint="invoice_change_status")
@login_required
def invoice_change_status(iid):
    new_status = request.form.get("status")
    valid_statuses = ["draft", "issued", "paid", "void"]

    if new_status not in valid_statuses:
        flash("Invalid status.", "error")
        return redirect(url_for("ppa.invoices_list"))

    inv = Invoice.query.get_or_404(iid)
    inv.status = new_status
    db.session.commit()
    flash(f"Invoice #{inv.id} status changed to {new_status.upper()}.", "success")
    return redirect(url_for("ppa.invoices_list"))
