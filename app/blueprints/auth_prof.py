from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from sqlalchemy import text
from app.extensions import db

bp = Blueprint("auth", __name__, template_folder="../templates")    # zadražavamo ime "auth" da ostali linkovi rade

@bp.route("/login", methods=["GET", "POST"])
def login():
    """
    NAMJERNO LOŠE:
    - raw SQL bez ORM modela
    - plain text password poređenje
    - bez CSRF
    - ručno setovanje session-a (bez Flask-Login)
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # profesorov stil: direktno u tabelu users
        row = db.session.execute(
            text("SELECT id, username, password FROM users_prof WHERE username = :u"), {"u": username}
        ).mappings().first()

        if not row:
            flash("Non existing user.", "error")
            return render_template("auth/login_prof.html")
        
        # LOŠE: plain text uporedba (bez hash-a)
        if password != (row["password"] or ""):
            flash("Wrong password.", "error")
            return render_template("auth/login_prof.html")
        
        # LOŠE: ručni session umjesto Flask-Login
        session["user_id"] = int(row["id"])
        session["username"] = row["username"]
        flash("Login successful.", "success")
        return redirect(url_for("main.index"))
    
    return render_template("auth/login_prof.html")

@bp.route("/logout")
def logout():
    # LOŠE: ručno čistimo session (bez login_manager.logout_user)
    session.clear()
    flash("Logging out.", "success")
    return redirect(url_for("auth.login"))