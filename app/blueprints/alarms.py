from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.extensions import db
from app.models.core import AlarmRule, Site

bp = Blueprint("alarms", __name__)

@bp.route("/")
@login_required
def list_alarms():
    rules = (db.session.query(AlarmRule, Site)
             .join(Site, AlarmRule.site_id==Site.id).all())
    return render_template("alarms/list.html", rules=rules)

@bp.route("/new", methods=["GET","POST"])
@login_required
def new_alarm():
    sites = Site.query.order_by(Site.name).all()
    if request.method == "POST":
        rule = AlarmRule(
            site_id=request.form.get("site_id", type=int),
            rule_type=request.form.get("rule_type"),
            minutes_no_data=request.form.get("minutes_no_data", type=int),
            expect_kwh_per_kwp=request.form.get("expect_kwh_per_kwp", type=float),
            email_to=(request.form.get("email_to") or None),
            is_active=bool(request.form.get("is_active")),
        )
        db.session.add(rule); db.session.commit()
        flash("Alarm rule created", "success")
        return redirect(url_for("alarms.list_alarms"))
    return render_template("alarms/form.html", sites=sites, rule=None)

@bp.route("/<int:rid>/edit", methods=["GET","POST"])
@login_required
def edit_alarm(rid):
    rule = AlarmRule.query.get_or_404(rid)
    sites = Site.query.order_by(Site.name).all()
    if request.method == "POST":
        rule.site_id = request.form.get("site_id", type=int)
        rule.rule_type = request.form.get("rule_type")
        rule.minutes_no_data = request.form.get("minutes_no_data", type=int)
        rule.expect_kwh_per_kwp = request.form.get("expect_kwh_per_kwp", type=float)
        rule.email_to = request.form.get("email_to") or None
        rule.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Alarm rule updated", "success")
        return redirect(url_for("alarms.list_alarms"))
    return render_template("alarms/form.html", sites=sites, rule=rule)

@bp.route("/<int:rid>/delete", methods=["POST"])
@login_required
def delete_alarm(rid):
    rule = AlarmRule.query.get_or_404(rid)
    db.session.delete(rule); db.session.commit()
    flash("Alarm rule deleted", "success")
    return redirect(url_for("alarms.list_alarms"))
