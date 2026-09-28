import os
import time
import smtplib
import feedparser
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google import genai

# Comprehensive feeds targeting executive leadership, international business, and sales
RSS_FEEDS = [
    # 1. Institutional & Research Sources
    "https://www.luke.fi/en/rss",
    "https://phys.org/rss-feed/earth-sciences/environment/",
    "https://forestsnews.cifor.org/feed",
    "https://www.timber-online.net/rss",
    "https://news.mongabay.com/feed/?post_type=post&s=forest+tech",

    # 2. Regulatory & EUDR Compliance (Primary Sales & Commercial Drivers)
    "https://news.google.com/rss/search?q=EUDR+deforestation+regulation+compliance&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=EUDR+timber+supply+chain+traceability&hl=en-US&gl=US&ceid=US:en",

    # 3. Market Signals, Funding & Procurement (CEO & Business Development Focus)
    "https://news.google.com/rss/search?q=forestry+tech+investment+funding+round&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=forest+inventory+remote+sensing+contract+tender&hl=en-US&gl=US&ceid=US:en",

    # 4. Geospatial AI & Operational Technology Frontiers
    "https://news.google.com/rss/search?q=geospatial+AI+satellite+forest+monitoring&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=LiDAR+drone+forestry+commercial&hl=en-US&gl=US&ceid=US:en",

    # 5. Regional Context (Nordics & Emerging Partner Markets)
    "https://news.google.com/rss/search?q=Finnish+forest+industry+digitalization&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Ukraine+forestry+reform+digitalization&hl=en-US&gl=US&ceid=US:en"
]

def fetch_recent_articles(days=7):
    """Fetches, deduplicates, and filters articles within the target time window."""
    articles = []
    seen_links = set()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    print(f"Collecting articles across feeds (sliding window: past {days} days)...")

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            print(f"Checking {url}: found {len(feed.entries)} entries")

            for entry in feed.entries[:8]:
                link = getattr(entry, "link", "")
                if not link or link in seen_links:
                    continue
                seen_links.add(link)

                # Parse publication or update timestamps safely
                pub_date = None
                parsed_time = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
                if parsed_time:
                    try:
                        pub_date = datetime(*parsed_time[:6], tzinfo=timezone.utc)
                    except Exception:
                        pub_date = None

                # Keep article if it falls within the window or lacks a strict RSS timestamp
                if pub_date is None or pub_date >= cutoff_date:
                    articles.append({
                        "title": getattr(entry, "title", "No Title"),
                        "link": link,
                        "date": pub_date.strftime("%Y-%m-%d") if pub_date else "Recent",
                        "summary": getattr(entry, "summary", "")[:500]
                    })
        except Exception as e:
            print(f"Warning: Failed to fetch feed {url}: {e}")

    print(f"Total deduplicated articles collected for AI review: {len(articles)}")
    return articles[:30]

def generate_digest(articles):
    """Generates an executive-level briefing tailored for management and sales."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Environment variable GEMINI_API_KEY is not set.")

    if not articles:
        return "<p>No relevant forestry, regulatory, or geospatial updates were identified for the past 7 days.</p>"

    client = genai.Client(api_key=api_key)

    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"{i}. [{a['date']}] {a['title']}\nURL: {a['link']}\nSummary: {a['summary']}\n\n"

    prompt = f"""
You are the Strategic & Technical Intelligence Advisor for the leadership team at Metsäavain (Forest Key), Joensuu, Finland.
Target audience: CEO, Director of International Business, and International Sales Representatives.
Company core: Precision forestry, LiDAR point-cloud processing, remote sensing (satellite & drone), AI analytics pipelines, and EUDR compliance solutions.

Collected news items from the past 7 days:
{articles_text}

Task:
1. Select 4 to 5 high-impact stories categorized where relevant under:
   - 💼 Commercial & Market Signals (Investments, tenders, international market traction)
   - ⚖️ Regulatory & EUDR Impact (Compliance deadlines, supply chain traceability, penalties)
   - 🔬 Tech & Geospatial AI Frontiers (LiDAR, drone monitoring, inventory automation)
2. Structure output as a clean, professionally formatted HTML snippet (using <h3>, <p>, <a>, <b>, <ul>, <li>).
3. For each story, provide:
   - 📌 Clickable Title: An <a> tag with target="_blank"
   - 💡 Key Takeaway: 1-2 concise, fact-based sentences outlining the update
   - 🎯 "So What for Metsäavain?":
     * For CEO / International Business: What is the strategic risk or market opportunity?
     * For Sales: How can our sales reps leverage this when pitching to prospective clients?

Tone: Crisp, executive-level, commercially actionable business English.
IMPORTANT: Return ONLY raw HTML snippet. Do not wrap response in markdown code blocks like ```html or ```.
"""

    # Official active models as recommended by Google API
    models_to_try = [
        "gemini-3.8-flash",
        "gemini-3.8-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.5-flash"
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
                print(f"✅ Successfully synthesized briefing with {model_name}!")

                # Strip accidental markdown wrappers
                cleaned_html = response.text.strip()
                if cleaned_html.startswith("```html"):
                    cleaned_html = cleaned_html[7:]
                if cleaned_html.startswith("```"):
                    cleaned_html = cleaned_html[3:]
                if cleaned_html.endswith("```"):
                    cleaned_html = cleaned_html[:-3]

                return cleaned_html.strip()
            except Exception as e:
                print(f"⚠️ Model {model_name} unavailable: {e}. Retrying in 6 seconds...")
                last_error = e
                time.sleep(6)

    raise RuntimeError(f"All fallback models failed to generate content: {last_error}")

def send_email(html_content, recipient_email="ileynkova.kate@gmail.com"):
    """Dispatches formatted HTML briefing via Gmail SMTP."""
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_APP_PASSWORD")

    if not sender_email or not sender_password:
        print("Error: Missing SENDER_EMAIL or SENDER_APP_PASSWORD environment variables.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌲 Executive Forestry & Geospatial Briefing — {datetime.now().strftime('%d.%m.%Y')}"
    msg["From"] = f"Metsäavain Radar <{sender_email}>"
    msg["To"] = recipient_email

    styled_html = f"""
    <html>
      <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #2c3e50; max-width: 680px; margin: 0 auto; padding: 24px;">
        <div style="border-bottom: 2px solid #2e7d32; padding-bottom: 12px; margin-bottom: 20px;">
          <h2 style="color: #2e7d32; margin: 0; font-size: 22px;">
            🌲 Executive Forestry & Geospatial Intelligence
          </h2>
          <p style="color: #7f8c8d; font-size: 13px; margin: 4px 0 0 0;">
            Curated weekly intelligence for Metsäavain leadership & commercial team
          </p>
        </div>
        <div>
          {html_content}
        </div>
        <hr style="border: none; border-top: 1px solid #e0e0e0; margin-top: 36px; margin-bottom: 16px;" />
        <p style="font-size: 11px; color: #95a5a6; margin: 0;">
          Generated automatically by Metsäavain Geospatial AI Digest Agent via GitHub Actions.
        </p>
      </body>
    </html>
    """
    msg.attach(MIMEText(styled_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        print(f"✅ Intelligence briefing delivered to {recipient_email}!")
    except Exception as e:
        print(f"❌ Failed to dispatch email: {e}")

def main():
    print("Step 1: Gathering fresh industry and market intelligence...")
    articles = fetch_recent_articles(days=7)

    print("Step 2: Synthesizing executive briefing via AI...")
    digest_html = generate_digest(articles)

    print("Step 3: Dispatching email report...")
    send_email(digest_html, recipient_email="ileynkova.kate@gmail.com")

if __name__ == "__main__":
    main()