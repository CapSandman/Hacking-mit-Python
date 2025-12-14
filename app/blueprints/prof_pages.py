from flask import Blueprint, render_template

bp = Blueprint("prof", __name__, template_folder="../templates")

@bp.route("/")
def home():
    # jednostavna "home" stranica u prof modu
    return render_template("prof/home.html")

@bp.route("/tickets")
def tickets():
    # Namjerno dummy podaci (kao kod profesora)
    tickets = [
        {"id": 1, "subject": "Inverter A - warning", "status": "open"},
        {"id": 2, "subject": "Meter sync delay", "status": "open"},
        {"id": 3, "subject": "Curtailed due to grid", "status": "closed"}
    ]
    return render_template("prof/tickets.html", tickets=tickets)