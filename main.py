import os
import smtplib
import feedparser
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google import genai

# Розширений список джерел: офіційні сайти + динамічний пошук новин Google News за ключовими словами
RSS_FEEDS = [
    # Офіційні інститути та медіа
    "https://www.luke.fi/en/rss",
    "https://phys.org/rss-feed/earth-sciences/environment/",
    
    # Динамічний пошук по всьому інтернету за останні 7 днів:
    # 1. ШІ та дистанційне зондування в лісовому секторі
    "https://news.google.com/rss/search?q=forestry+remote+sensing+AI+when:7d&hl=en-US&gl=US&ceid=US:en",
    # 2. Супутниковий моніторинг лісів та LiDAR
    "https://news.google.com/rss/search?q=LiDAR+satellite+forest+monitoring+when:7d&hl=en-US&gl=US&ceid=US:en",
    # 3. Регулювання вирубки лісів у ЄС (EUDR)
    "https://news.google.com/rss/search?q=EUDR+forest+regulation+compliance+when:7d&hl=en-US&gl=US&ceid=US:en",
    # 4. Фінські лісові технології
    "https://news.google.com/rss/search?q=Finland+forestry+technology+when:7d&hl=en-US&gl=US&ceid=US:en"
]

def fetch_recent_articles(days=7):
    articles = []
    seen_links = set()  # Щоб уникнути дублікатів новин з різних запитів
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    print(f"Збір новин з розширених джерел...")

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                # Перевіряємо дублікати
                if entry.link in seen_links:
                    continue
                seen_links.add(entry.link)

                # Перевірка дати
                pub_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                # Якщо в стрічці Google News дата свіжа або парсер не вказав точну мітку часу
                if pub_date is None or pub_date >= cutoff_date:
                    articles.append({
                        "title": entry.title,
                        "link": entry.link,
                        "date": pub_date.strftime("%Y-%m-%d") if pub_date else "Recent",
                        "summary": getattr(entry, "summary", "")[:500]
                    })
        except Exception as e:
            print(f"Помилка зчитування стрічки {url}: {e}")

    print(f"Всього знайдено релевантних статей: {len(articles)}")
    # Беремо до 20 найцікавіших матеріалів і передаємо їх на фільтрацію моделі
    return articles[:20]

def generate_digest(articles):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY не знайдено!")

    if not articles:
        return "<p>За останній тиждень нових релевантних публікацій не знайдено.</p>"

    client = genai.Client(api_key=api_key)
    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"{i}. [{a['date']}] {a['title']}\nURL: {a['link']}\nSummary: {a['summary']}\n\n"

    prompt = f"""
Ти — технічний радник та AI-аналітик компанії Metsäavain (Forest Key), Фінляндія.
Компанія займається: лісовим сектором, AI, remote sensing, супутниками, LiDAR, GIS та регулюванням ЄС (EUDR).

Ось статті за тиждень:
{articles_text}

Завдання:
1. Обери 3-4 найважливіші статті.
2. Сформуй чистий HTML (використовуй теги <h3>, <p>, <a>, <b>, <ul>, <li>).
3. Для кожної статті розкрий:
   - 📌 Заголовок як клікабельне посилання
   - 💡 Коротку суть
   - 🎯 So What? — чому це важливо для Metsäavain саме зараз.
Мова: ділова англійська (Professional English). Поверни тільки HTML-код без лапок чи блоків коду ```.
"""
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
    )
    return response.text

def send_email(html_content, recipient_email="ileynkova.kate@gmail.com"):
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_APP_PASSWORD")

    if not sender_email or not sender_password:
        print("Помилка: SENDER_EMAIL або SENDER_APP_PASSWORD відсутні.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌲 Weekly Forestry & Geospatial AI Briefing — {datetime.now().strftime('%d.%m.%Y')}"
    msg["From"] = f"Metsäavain Radar <{sender_email}>"
    msg["To"] = recipient_email

    styled_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #222; max-width: 650px; margin: auto; padding: 20px;">
        <h2 style="color: #2e7d32; border-bottom: 2px solid #2e7d32; padding-bottom: 8px;">
          🌲 Weekly Geospatial & Forestry Intelligence
        </h2>
        <p style="color: #666; font-size: 13px;">Curated for Metsäavain leadership | Past 7 days update</p>
        <div>{html_content}</div>
        <hr style="border: none; border-top: 1px solid #ddd; margin-top: 30px;" />
        <p style="font-size: 11px; color: #888;">Generated automatically by Forestry AI Digest Agent.</p>
      </body>
    </html>
    """
    msg.attach(MIMEText(styled_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        print(f"✅ Лист успішно надіслано на {recipient_email}!")
    except Exception as e:
        print(f"❌ Помилка під час відправки пошти: {e}")

def main():
    print("1. Збір свіжих новин...")
    articles = fetch_recent_articles(days=7)
    print("2. Генерація дайджесту...")
    digest_html = generate_digest(articles)
    print("3. Відправка на пошту...")
    send_email(digest_html, recipient_email="ileynkova.kate@gmail.com")

if __name__ == "__main__":
    main()