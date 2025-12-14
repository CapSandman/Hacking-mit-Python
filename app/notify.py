import os, smtplib
from email.message import EmailMessage

def send_email(subject: str, body: str, to: str | None = None):
    host = os.getenv("SMTP_HOST"); port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER"); pwd = os.getenv("SMTP_PASS")
    from_addr = os.getenv("ALERT_FROM", user)
    to_addr = to or os.getenv("ALERT_TO_DEFAULT", user)

    if not (host and user and pwd and to_addr):
        print("Email not configured; skipping:", subject); 
        return

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, pwd)
        s.send_message(msg)
