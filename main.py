import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_email(html_content, recipient_email="ileynkova.kate@gmail.com"):
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_APP_PASSWORD")

    if not sender_email or not sender_password:
        print("Помилка: SENDER_EMAIL або SENDER_APP_PASSWORD не знайдено в секретах!")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "🌲 Weekly Forestry & Geospatial AI Briefing"
    msg["From"] = f"Metsäavain Radar <{sender_email}>"
    msg["To"] = recipient_email

    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        print(f"✅ Лист успішно надіслано на {recipient_email}!")
    except Exception as e:
        print(f"❌ Помилка під час відправки пошти: {e}")