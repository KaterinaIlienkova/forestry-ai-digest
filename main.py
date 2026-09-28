import os
import time
import smtplib
import feedparser
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google import genai

# Source list: verified industry feeds + dynamic 7-day keyword search via Google News RSS
RSS_FEEDS = [
    # Official Finnish and scientific portals
    "[https://www.luke.fi/en/rss](https://www.luke.fi/en/rss)",
    "[https://phys.org/rss-feed/earth-sciences/environment/](https://phys.org/rss-feed/earth-sciences/environment/)",
    
    # Dynamic Google News queries targeting company domains (filtered to the past 7 days)
    "[https://news.google.com/rss/search?q=forestry+remote+sensing+AI+when:7d&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=forestry+remote+sensing+AI+when:7d&hl=en-US&gl=US&ceid=US:en)",
    "[https://news.google.com/rss/search?q=LiDAR+satellite+forest+monitoring+when:7d&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=LiDAR+satellite+forest+monitoring+when:7d&hl=en-US&gl=US&ceid=US:en)",
    "[https://news.google.com/rss/search?q=EUDR+forest+regulation+compliance+when:7d&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=EUDR+forest+regulation+compliance+when:7d&hl=en-US&gl=US&ceid=US:en)",
    "[https://news.google.com/rss/search?q=Finland+forestry+technology+when:7d&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=Finland+forestry+technology+when:7d&hl=en-US&gl=US&ceid=US:en)"
]

def fetch_recent_articles(days=7):
    """Fetches and deduplicates recent articles from configured RSS feeds."""
    articles = []
    seen_links = set()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    print(f"Collecting articles from feeds for the past {days} days...")

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                # Avoid duplicate articles fetched across different keyword feeds
                if entry.link in seen_links:
                    continue
                seen_links.add(entry.link)

                # Parse publication or update timestamps
                pub_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                if pub_date is None or pub_date >= cutoff_date:
                    articles.append({
                        "title": entry.title,
                        "link": entry.link,
                        "date": pub_date.strftime("%Y-%m-%d") if pub_date else "Recent",
                        "summary": getattr(entry, "summary", "")[:500]
                    })
        except Exception as e:
            print(f"Warning: Failed to parse feed {url}: {e}")

    print(f"Total relevant articles collected: {len(articles)}")
    return articles[:20]

def generate_digest(articles):
    """Synthesizes collected articles into an executive briefing using Gemini."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Environment variable GEMINI_API_KEY is not set.")

    if not articles:
        return "<p>No relevant forestry or geospatial AI updates were found for the past 7 days.</p>"

    client = genai.Client(api_key=api_key)
    
    # Format collected articles into a structured prompt
    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"{i}. [{a['date']}] {a['title']}\nURL: {a['link']}\nSummary: {a['summary']}\n\n"

    prompt = f"""
You are the Technical Advisor and Geospatial AI Intelligence Analyst for Metsäavain (Forest Key), a Finnish company based in Joensuu.
Metsäavain specializes in: precision forestry, LiDAR point-cloud processing, remote sensing (satellite and drone), GIS pipelines, and EU Deforestation Regulation (EUDR) compliance solutions.

Here are the news items collected over the past 7 days:
{articles_text}

Task:
1. Curate and select the 3 to 4 most strategically significant articles for the company's executive leadership.
2. Structure the output as clean HTML snippet (use standard HTML tags: <h3>, <p>, <a>, <b>, <ul>, <li>).
3. For each selected article, provide:
   - 📌 Clickable Title: An <a> tag linking to the original article with target="_blank"
   - 💡 Executive Summary: 1-2 concise sentences outlining the breakthrough or news
   - 🎯 "So What?" Strategic Relevance: Clearly explain why this matters to Metsäavain's technology, product roadmap, or regulatory positioning right now.

Tone and Language: High-level, objective, professional business English.
IMPORTANT: Return ONLY raw HTML snippet. Do not wrap the response in markdown blocks like ```html or ```.
"""

    # Fallback model tier list to handle temporary server capacity constraints (e.g. 503 errors)
    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-3.6-flash"
    ]

    last_error = None
    for model_name in models_to_try:
        for attempt in range(1, 3):
            try:
                print(f"Attempting generation with model: {model_name} (attempt {attempt}/2)...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                print(f"✅ Successfully generated briefing with {model_name}!")
                
                # Clean up any potential markdown fences returned by the model
                cleaned_html = response.text.strip()
                if cleaned_html.startswith("```html"):
                    cleaned_html = cleaned_html[7:]
                if cleaned_html.startswith("```"):
                    cleaned_html = cleaned_html[3:]
                if cleaned_html.endswith("```"):
                    cleaned_html = cleaned_html[:-3]
                    
                return cleaned_html.strip()
            except Exception as e:
                print(f"⚠️ Model {model_name} temporarily unavailable: {e}. Retrying in 5 seconds...")
                last_error = e
                time.sleep(5)

    raise RuntimeError(f"All fallback models failed to generate content: {last_error}")

def send_email(html_content, recipient_email="ileynkova.kate@gmail.com"):
    """Sends the formatted HTML briefing via Gmail SMTP."""
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_APP_PASSWORD")

    if not sender_email or not sender_password:
        print("Error: Missing SENDER_EMAIL or SENDER_APP_PASSWORD environment variables.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌲 Weekly Forestry & Geospatial AI Briefing — {datetime.now().strftime('%d.%m.%Y')}"
    msg["From"] = f"Metsäavain Radar <{sender_email}>"
    msg["To"] = recipient_email

    styled_html = f"""
    <html>
      <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #2c3e50; max-width: 650px; margin: 0 auto; padding: 24px;">
        <div style="border-bottom: 2px solid #2e7d32; padding-bottom: 12px; margin-bottom: 20px;">
          <h2 style="color: #2e7d32; margin: 0; font-size: 22px;">
            🌲 Weekly Geospatial & Forestry Intelligence
          </h2>
          <p style="color: #7f8c8d; font-size: 13px; margin: 4px 0 0 0;">
            Curated for Metsäavain leadership | Past 7 days briefing
          </p>
        </div>
        <div>
          {html_content}
        </div>
        <hr style="border: none; border-top: 1px solid #e0e0e0; margin-top: 36px; margin-bottom: 16px;" />
        <p style="font-size: 11px; color: #95a5a6; margin: 0;">
          Generated automatically by Metsäavain Forestry AI Digest Agent via GitHub Actions.
        </p>
      </body>
    </html>
    """
    msg.attach(MIMEText(styled_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        print(f"✅ Briefing email successfully delivered to {recipient_email}!")
    except Exception as e:
        print(f"❌ Failed to dispatch email: {e}")

def main():
    print("Step 1: Gathering fresh articles...")
    articles = fetch_recent_articles(days=7)
    
    print("Step 2: Generating executive AI digest...")
    digest_html = generate_digest(articles)
    
    print("Step 3: Dispatching email report...")
    send_email(digest_html, recipient_email="ileynkova.kate@gmail.com")

if __name__ == "__main__":
    main()