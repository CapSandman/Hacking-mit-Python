from flask import Flask, request, jsonify
from datetime import datetime
import os

app = Flask(__name__)

LOG_FILE = "inputs.log"


def write_log_line(text, extra=""):
    """Upiše jednu liniju u log fajl."""
    timestamp = datetime.utcnow().isoformat()
    ip = request.remote_addr or "-"
    ua = request.headers.get("User-Agent", "-")
    
    line = f"{timestamp}\t{ip}\t{ua}\t{text}\t{extra}\n"

    # Kreiraj fajl ako ne postoji i append-aj
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)


@app.route("/log", methods=["POST"])
def log_input():
    """
    Endpoint za primanje podataka koje korisnik šalje (npr. sadržaj forme).
    Očekuje JSON: { "input": "neki tekst" }
    """
    data = request.get_json(silent=True) or {}
    text = data.get("input", "")

    # Ako nema teksta, možeš po želji vratiti grešku:
    if not text:
        return jsonify({"status": "error", "message": "no input provided"}), 400

    write_log_line(text)
    return jsonify({"status": "ok"}), 200


@app.route("/")
def index():
    return "Logging server is running."


if __name__ == "__main__":
    # Pokreni server na 0.0.0.0:5000 da bude dostupan u mreži
    app.run(host="0.0.0.0", port=5000, debug=True)
