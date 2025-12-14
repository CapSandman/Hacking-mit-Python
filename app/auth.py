from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, limiter
from app.models.core import User
import re
from sqlalchemy import text, inspect

login_manager = LoginManager()
login_manager.login_view = "auth.login"

bp = Blueprint("auth", __name__)

class UserWrapper(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username





USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")

def validate_registration(username, password, confirm):
    if not USERNAME_RE.match(username or ""):
        return "Korisničko ime mora imati 3–32 znaka (slova, brojevi, . _ -)."
    if not password or len(password) < 8:
        return "Lozinka mora imati najmanje 8 znakova."
    if len(password) > 128:
        return "Lozinka je preduga (max 128 znakova)."
    if password != confirm:
        return "Lozinke se ne poklapaju."
    return None

@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm  = request.form.get("confirm") or ""

        # validacija
        err = validate_registration(username, password, confirm)
        if err:
            flash(err, "warning")
            return render_template("auth/register.html", values=request.form)

        # jedinstvenost
        table_name = getattr(User, "__tablename__", None) or getattr(User, "__table__", None).name
        sql_check = text(f"SELECT 1 FROM {table_name} WHERE username = :username LIMIT 1")
        if db.session.execute(sql_check, {"username": username}).fetchone():
            flash("Korisnicko ime je zauzeto.", "warning")
            return render_template("auth/register.html", values=request.form)

        sql_insert = text(f"INSERT INTO {table_name} (username, password) VALUES (:username, :password)")
        db.session.execute(sql_insert, {"username": username, "password": password})
        db.session.commit()
        # auto login nakon registracije (po želji)
        flash("Registration succesful. Welcome!", "success")
        return redirect(url_for("main.index"))

    return render_template("auth/register.html")

@login_manager.user_loader
def load_user(user_id):
    # First try to load from the primary users table (numeric ids)
    try:
        numeric_id = int(user_id)
    except (TypeError, ValueError):
        numeric_id = None

    table_name = getattr(User, "__tablename__", None) or getattr(User, "__table__", None).name
    row = None
    if numeric_id is not None:
        sql_by_id = text(f"SELECT id, username FROM {table_name} WHERE id = :id")
        row = db.session.execute(sql_by_id, {"id": numeric_id}).fetchone()

    if row is None:
        sql_by_username = text(f"SELECT id, username FROM {table_name} WHERE username = :username")
        row = db.session.execute(sql_by_username, {"username": user_id}).fetchone()
        if row is None:
            return None

    mapping = getattr(row, "_mapping", None) or row
    return UserWrapper(mapping["id"], mapping["username"])

# ----------------------------------------------------------------------------------
@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(
    "5 per minute",
    methods=["POST"],
    error_message="Too many login attempts from this IP address. Try again in a few minutes."
)
def login():
    if request.method == "POST":
        username = request.form.get("Username") or request.form.get("username")
        password = request.form.get("Password") or request.form.get("password")

        if not username or not isinstance(username, str):
            flash("Invalid username", "warning")
            return render_template("auth/login.html", cookie=None)
        if not password or not isinstance(password, str) or len(password) < 3:
            flash("Invalid password", "warning")
            return render_template("auth/login.html", cookie=None)

        # dobije ime tabele iz modela
        table_name = getattr(User, "__tablename__", None) or getattr(User, "__table__", None).name

        # inspect engine -> dobijemo stvarne kolone u tabeli
        inspector = inspect(db.engine)
        cols = [c['name'] for c in inspector.get_columns(table_name)]

        # odredimo koju kolonu koristiti kao "pwd_col"
        # prioritetno koristimo password_hash, ako ne postoji fallback na password (legacy)
        if 'password_hash' in cols:
            pwd_col = 'password_hash'
            using_hash = True
        elif 'password' in cols:
            pwd_col = 'password'
            using_hash = False
        else:
            flash("User table contains no password column.", "danger")
            return render_template("auth/login.html", cookie=None)

        # sigurni parametrizirani upit (aliasiramo kolonu u password_hash da je ostatak koda isti)
        sql = text(
            f"SELECT id, username, {pwd_col} AS password_hash "
            f"FROM {table_name} WHERE username = :username LIMIT 1"
        )

        row = db.session.execute(sql, {"username": username}).mappings().fetchone()

        if not row:
            flash("Incorrect username or password", "danger")
            return render_template("auth/login.html", cookie=None)

        stored = row.get("password_hash")

        # Ako u bazi stoji heš (koristimo check_password_hash)
        password_ok = False
        if using_hash:
            try:
                password_ok = check_password_hash(stored, password)
            except Exception as e:
                # neočekivana greška pri provjeri heša -> odbij
                password_ok = False
        else:
            # legacy: direktna provjera plaintext (nepoželjno, ali kompatibilno)
            password_ok = (password == stored)

        if not password_ok:
            flash("Incorrect username or password", "danger")
            return render_template("auth/login.html", cookie=None)

        # uspješan login
        login_user(UserWrapper(row["id"], row["username"]))
        resp = redirect("/tickets")
        resp.set_cookie("name", username, httponly=True, samesite="Lax")
        #resp.set_cookie("test_xss", "hello123", httponly=False, samesite="Lax")
        return resp

    return render_template("auth/login.html", cookie=None)




@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
