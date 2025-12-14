from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_required, current_user
from datetime import datetime
from app.models.support import TestItem
from app.extensions import db
from flask import abort
from sqlalchemy import text

bp = Blueprint("tickets", __name__, template_folder="../templates/tickets")

@bp.route("/tickets")
@login_required
def list_tickets():
    items = TestItem.query.order_by(TestItem.id.desc()).all()
    last_seen = request.cookies.get("tickets_last_seen")
    resp = make_response(render_template("tickets/list.html", items=items, last_seen=last_seen, q=""))
    resp.set_cookie(
        "tickets_last_seen",
        datetime.utcnow().isoformat(timespec="seconds"),
        max_age=30*24*3600,
        httponly=False,
        samesite="Lax",
        # secure=True
    )
    return resp

@bp.route("/tickets/new", methods=["GET", "POST"])
@login_required
def new_ticket():
    if request.method == "POST":
        priority = (request.form.get("priority") or "").strip()
        username = (request.form.get("username") or current_user.username or "").strip()
        title = (request.form.get("title") or "").strip()
        info = (request.form.get("info") or "").strip()

        if not title:
            flash("Title is required", "warning")
            return render_template("tickets/new.html", values=request.form)

        ti = TestItem(priority=priority, username=username, title=title, info=info)
        db.session.add(ti)
        db.session.commit()
        flash(f"Ticket #{ti.id} created", "success")

        resp = make_response(redirect(url_for("tickets.list_tickets")))
        resp.set_cookie("last_ticket_user", username, max_age=30*24*3600, httponly=False, samesite="Lax")
        return resp

    last_user = request.cookies.get("last_ticket_user", current_user.username if current_user.is_authenticated else "")
    return render_template("tickets/new.html", last_user=last_user)



@bp.route("/tickets/search", methods=["GET"])
@login_required
def search_bar():
    q = request.args.get("q", "")
    
    if len(q) > 200:
        q = q[:200]
    
    pat = "%" + q + "%"
    
    tbl = TestItem.__tablename__  # npr. "testitems"
    
    sql = (
        "SELECT id, title, username, priority AS body FROM " + tbl + " "
        + "WHERE LOWER(title) LIKE LOWER('" + pat + "') "
        + "OR LOWER(priority) LIKE LOWER('" + pat + "') "
        + "OR LOWER(username) LIKE LOWER('" + pat + "') "
        + "ORDER BY id DESC"
    )
    
    try:
        rows = db.session.execute(text(sql)).all()
    except Exception as e:
        rows = []
        # Opciono: možeš logirati grešku ili prikazati korisniku
        # error = str(e)
    
    return render_template("tickets/list.html", items=rows, q=q)
 


@bp.route("/tickets/<int:tid>", methods=["GET"])
@login_required
def view_ticket(tid):
    tbl = TestItem.__tablename__
    sql = text(f"SELECT id, title, username, created_at, info FROM {tbl} WHERE id = :tid")
    row = db.session.execute(sql, {"tid": tid}).first()
    if not row:
        abort(404)
    # Row podržava pristup atributima: row.id, row.title, row.info ...
    return render_template("tickets/view.html", item=row)

@bp.route("/tickets/<int:tid>/edit", methods=["GET", "POST"])
@login_required
def edit_ticket(tid):
    ti = TestItem.query.get_or_404(tid)
    if request.method == "POST":
        ti.title = (request.form.get("title") or "").strip()
        ti.info  = (request.form.get("info")  or "").strip()
        db.session.commit()
        flash(f"Ticket #{ti.id} updated", "success")
        return redirect(url_for("tickets.view_ticket", tid=ti.id))
    return render_template("tickets/new.html", item=ti)


@bp.route("/tickets/<int:tid>/delete", methods=["POST"])
@login_required
def delete_ticket(tid):
    ti = TestItem.query.get_or_404(tid)
    db.session.delete(ti)
    db.session.commit()
    flash(f"Ticket #{tid} deleted.", "success")
    return redirect(url_for("tickets.list_tickets"))
