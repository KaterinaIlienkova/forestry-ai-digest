import os
import time
import json
import smtplib
import urllib.request
import urllib.error
import feedparser
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google import genai

# Global & regional intelligence feeds: Direct portals and language-agnostic entity searches
RSS_FEEDS = [
    # 1. Direct Specialized Portals
    "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET&concepts=18-35354",  # Yle: Forestry (Nordic)
    "https://www.metsalehti.fi/feed/",                                                       # Metsälehti (Leading Finnish Forest Media)
    "https://www.luke.fi/en/rss",                                                            # Luke (Natural Resources Institute Finland)
    "https://www.timber-online.net/rss",                                                     # Timber Online (Central Europe)
    "https://forestsnews.cifor.org/feed",                                                    # CIFOR (International Forest Policy)
    "https://news.mongabay.com/feed/?post_type=post&s=forest+tech",                          # Mongabay (Global Forest Tech)

    # 2. Competitors
    "https://news.google.com/rss/search?q=(Arbonaut+OR+%22CollectiveCrunch%22+OR+%22Trimble+Forestry%22+OR+Indufor+OR+Remsoft)",
    "https://news.google.com/rss/search?q=(%22AFRY+smart+forestry%22+OR+Sitowise+OR+%22Field+Finland%22+OR+%22Koko+Forest%22+OR+Triona+OR+Interpine)",
    "https://news.google.com/rss/search?q=(%22Unique+land+use%22+OR+Microforest)+forestry",

    # 3. Key Clients, Target Prospects & Stakeholders
    "https://news.google.com/rss/search?q=(Ponsse+OR+%22John+Deere+Forestry%22+OR+Kesla)+(forest+OR+harvester+OR+forestry)",
    "https://news.google.com/rss/search?q=(%22Metsä+Group%22+OR+UPM+OR+%22Stora+Enso%22+OR+Mondi)+(investointi+OR+investment+OR+mill+OR+pulp)",
    "https://news.google.com/rss/search?q=(%22Asian+Pulp+and+Paper%22+OR+%22APRIL+group%22+OR+SAFCOL+OR+%22York+Timbers%22+OR+%22New+Forests%22)",
    "https://news.google.com/rss/search?q=(Tornator+OR+Versowood+OR+Finsilva+OR+Koskisen+OR+%22United+Bankers%22+OR+Metsähallitus)",

    # 4. Macro Capital Investments & Industrial Capacity
    "https://news.google.com/rss/search?q=(forestry+OR+biomass+OR+pulp+OR+sawmill)+(investment+OR+acquisition+OR+%22funding+program%22)",
    "https://news.google.com/rss/search?q=(metsäteollisuus+OR+sahateollisuus+OR+sellutehdas)+(investointi+OR+hanke+OR+rahoitus)",
    "https://news.google.com/rss/search?q=(forestal+OR+celulosa+OR+aserradero)+(inversión+OR+planta+OR+adquisición)",

    # 5. Regulation, Policy Shifts & EUDR
    "https://news.google.com/rss/search?q=EUDR+(deforestation+OR+timber+OR+compliance+OR+traceability)",
    "https://news.google.com/rss/search?q=(forestry+OR+metsätalous+OR+forestal)+(legislation+OR+policy+OR+sääntely+OR+reglamento)"
]

def fetch_recent_articles(days=7):
    """Fetches, deduplicates, and filters multilingual articles within the target sliding window."""
    articles = []
    seen_links = set()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    print(f"Collecting articles across multilingual feeds (sliding window: past {days} days)...")

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            print(f"Checking {url[:75]}...: found {len(feed.entries)} entries")

            for entry in feed.entries[:8]:
                link = getattr(entry, "link", "")
                if not link or link in seen_links:
                    continue
                seen_links.add(link)

                pub_date = None
                parsed_time = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
                if parsed_time:
                    try:
                        pub_date = datetime(*parsed_time[:6], tzinfo=timezone.utc)
                    except Exception:
                        pub_date = None

                if pub_date is None or pub_date >= cutoff_date:
                    articles.append({
                        "title": getattr(entry, "title", "No Title"),
                        "link": link,
                        "date": pub_date.strftime("%Y-%m-%d") if pub_date else "Recent",
                        "summary": getattr(entry, "summary", "")[:500]
                    })
        except Exception as e:
            print(f"Warning: Failed to fetch feed {url}: {e}")

    print(f"Total deduplicated articles collected for executive review: {len(articles)}")
    return articles[:45]

def generate_digest_data(articles):
    """
    Synthesizes executive briefing into structured JSON objects.
    Enables dual-destination publishing: ClickUp tasks and formatted HTML email.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Environment variable GEMINI_API_KEY is not set.")

    if not articles:
        return []

    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"{i}. [{a['date']}] {a['title']}\nURL: {a['link']}\nSummary: {a['summary']}\n\n"

    prompt = f"""
You are the Executive Market & Strategic Intelligence Agent for the leadership team at Metsäavain (Forest Key), Joensuu, Finland.

Core Objective:
Identify 4 to 6 SIGNIFICANT strategic events from the past 7 days across:
- Competitors: Arbonaut, AFRY smart forestry, Sitowise, Field Finland, Koko Forest, CollectiveCrunch, Unique land use, Trimble, Microforest, Remsoft, Indufor, Triona, Interpine.
- Strategic Clients & Stakeholders: Ponsse, John Deere, Kesla, UPM, Stora Enso, Asian Pulp and Paper, Metsä Group, Mondi, APRIL, SAFCOL, York Timbers, New Forests, Tornator, Versowood, Finsilva, Koskisen, United Bankers Forest Fund, Metsähallitus.
- Macro Sectors: Major pulp mills/sawmills capital investments, EUDR compliance & forest legislation, and Geospatial AI/LiDAR technology.

Constraint: This is NOT an active sales tool. Provide high-level strategic intelligence for leadership evaluation.

Language Directive:
Input articles are in multiple languages (Finnish, English, Spanish, etc.). Process natively and output strictly in professional Executive English.

Collected news items:
{articles_text}

OUTPUT INSTRUCTION:
Return ONLY a valid JSON array of objects. Do NOT include markdown blocks like ```json or ```.
Each object must have these exact keys:
[
  {{
    "category": "Competitors" | "Clients & Partners" | "Capital & Investments" | "Policy & EUDR" | "Geospatial Tech",
    "entity": "Name of main company or sector involved",
    "title": "Clear, informative headline",
    "summary": "2-3 concise, fact-driven sentences explaining the core development",
    "strategic_signal": "1 sharp sentence highlighting the direct strategic significance or risk/opportunity for Metsäavain leadership",
    "url": "Original link from the article",
    "date": "Publication date"
  }}
]
"""

    client = genai.Client(api_key=api_key)

    models_to_try = [
        "gemini-2.5-pro",
        "gemini-3.5-pro",
        "gemini-3.8-flash",
        "gemini-3.6-flash"
    ]

    for model_name in models_to_try:
        try:
            print(f"Attempting structured generation with model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            print(f"✅ Successfully synthesized briefing with {model_name}!")

            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            parsed_items = json.loads(raw_text.strip())
            if isinstance(parsed_items, list):
                return parsed_items
        except Exception as e:
            print(f"⚠️ Model {model_name} failed: {e}. Trying next available model...")
            time.sleep(3)

    # Fallback to direct raw format if AI generation fails
    print("⚠️ AI synthesis unavailable. Building fallback items from raw articles...")
    fallback_items = []
    for a in articles[:6]:
        fallback_items.append({
            "category": "Direct Feed",
            "entity": "Industry General",
            "title": a['title'],
            "summary": a['summary'][:250] + "...",
            "strategic_signal": "Direct uncurated article collected during temporary AI API unavailability.",
            "url": a['link'],
            "date": a['date']
        })
    return fallback_items

def build_html_digest(items):
    """Constructs clean executive HTML email from structured intelligence items."""
    if not items:
        return "<p>No significant market shifts, competitor updates, or regulatory signals identified for the past 7 days.</p>"

    # Group items by category
    categories = {}
    category_icons = {
        "Competitors": "⚔️ Competitors & Market Dynamics",
        "Clients & Partners": "🌲 Strategic Clients & Organizations",
        "Capital & Investments": "🏭 Major Capital Investments & Facilities",
        "Policy & EUDR": "⚖️ Policy, Legislation & EUDR Compliance",
        "Geospatial Tech": "🔬 Geospatial AI & Operational Technology",
        "Direct Feed": "⚡ Weekly Direct Industry Feed"
    }

    for item in items:
        cat = item.get("category", "General")
        categories.setdefault(cat, []).append(item)

    html = ""
    for cat_key, cat_items in categories.items():
        cat_title = category_icons.get(cat_key, f"📌 {cat_key}")
        html += f"<h3 style='color: #2e7d32; border-bottom: 1px solid #c8e6c9; padding-bottom: 4px; margin-top: 24px;'>{cat_title}</h3>"
        html += "<ul style='padding-left: 20px; list-style-type: none; margin: 0;'>"

        for item in cat_items:
            html += f"""
            <li style="margin-bottom: 20px; background: #fafafa; padding: 14px; border-left: 4px solid #2e7d32; border-radius: 4px;">
                <div style="margin-bottom: 6px;">
                    <a href="{item.get('url', '#')}" target="_blank" style="color: #1b5e20; font-weight: bold; font-size: 16px; text-decoration: none;">
                        {item.get('title')}
                    </a>
                    <span style="color: #7f8c8d; font-size: 12px; margin-left: 8px;">({item.get('date', 'Recent')})</span>
                </div>
                <p style="margin: 4px 0 8px 0; font-size: 14px; line-height: 1.5; color: #2c3e50;">
                    {item.get('summary')}
                </p>
                <div style="background: #e8f5e9; padding: 8px 12px; border-radius: 4px; font-size: 13px; color: #1b5e20;">
                    <b>🎯 Strategic Signal:</b> {item.get('strategic_signal')}
                </div>
            </li>
            """
        html += "</ul>"

    return html

def push_to_clickup(items):
    """
    Pushes structured intelligence items into ClickUp list tasks.
    Configured for private staging and human-in-the-loop validation.
    """
    api_token = os.environ.get("CLICKUP_API_TOKEN")
    list_id = os.environ.get("CLICKUP_LIST_ID")

    if not api_token or not list_id:
        print("ℹ️ ClickUp synchronization skipped: CLICKUP_API_TOKEN or CLICKUP_LIST_ID not configured.")
        return

    print(f"Step 3: Exporting {len(items)} items to ClickUp list {list_id}...")
    url = f"https://api.clickup.com/api/v2/list/{list_id}/task"
    headers = {
        "Authorization": api_token,
        "Content-Type": "application/json"
    }

    for item in items:
        category = item.get("category", "Market")
        entity = item.get("entity", "Forestry")
        title = item.get("title", "Signal")

        task_payload = {
            "name": f"[{category}] {title}",
            "description": (
                f"### 💡 Executive Summary\n{item.get('summary', '')}\n\n"
                f"### 🎯 Strategic Signal for Metsäavain\n{item.get('strategic_signal', '')}\n\n"
                f"---\n"
                f"**Entity:** {entity}\n"
                f"**Date:** {item.get('date', '')}\n"
                f"**Source URL:** [Read Original Article]({item.get('url', '')})\n"
            ),
            "tags": [
                category.lower().replace(" ", "-"),
                entity.lower().replace(" ", "-")
            ],
            "status": "to do"  # or 'inbox' / 'review' if custom status configured in ClickUp
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(task_payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req) as resp:
                if resp.status in (200, 201):
                    print(f"  ✓ ClickUp Task created: {title[:45]}...")
        except urllib.error.HTTPError as e:
            print(f"  ⚠️ ClickUp API warning ({e.code}): {e.read().decode('utf-8')[:150]}")
        except Exception as e:
            print(f"  ⚠️ Failed to push task to ClickUp: {e}")

def send_email(html_content, recipient_email="ileynkova.kate@gmail.com"):
    """Dispatches formatted HTML briefing via Gmail SMTP."""
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_APP_PASSWORD")

    if not sender_email or not sender_password:
        print("Error: Missing SENDER_EMAIL or SENDER_APP_PASSWORD environment variables.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌲 Metsäavain Executive Radar — {datetime.now().strftime('%d.%m.%Y')}"
    msg["From"] = f"Metsäavain Radar <{sender_email}>"
    msg["To"] = recipient_email

    styled_html = f"""
    <html>
      <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #2c3e50; max-width: 680px; margin: 0 auto; padding: 24px;">
        <div style="border-bottom: 2px solid #2e7d32; padding-bottom: 12px; margin-bottom: 20px;">
          <h2 style="color: #2e7d32; margin: 0; font-size: 22px;">
            🌲 Metsäavain Executive Intelligence Radar
          </h2>
          <p style="color: #7f8c8d; font-size: 13px; margin: 4px 0 0 0;">
            Weekly management overview: Competitors, Strategic Organizations, Capital & Policy
          </p>
        </div>
        <div>
          {html_content}
        </div>
        <hr style="border: none; border-top: 1px solid #e0e0e0; margin-top: 36px; margin-bottom: 16px;" />
        <p style="font-size: 11px; color: #95a5a6; margin: 0;">
          Generated automatically by Metsäavain Executive Radar Agent via GitHub Actions.
        </p>
      </body>
    </html>
    """
    msg.attach(MIMEText(styled_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        print(f"✅ Executive radar briefing delivered to {recipient_email}!")
    except Exception as e:
        print(f"❌ Failed to dispatch email: {e}")

def main():
    print("Step 1: Gathering fresh multilingual market, competitor, and client intelligence...")
    articles = fetch_recent_articles(days=7)

    print("Step 2: Synthesizing executive briefing via AI (JSON Structured Data)...")
    intel_items = generate_digest_data(articles)

    print("Step 3: Formatting and dispatching email report...")
    digest_html = build_html_digest(intel_items)
    send_email(digest_html, recipient_email="ileynkova.kate@gmail.com")

    print("Step 4: Synchronizing items into ClickUp workspace...")
    push_to_clickup(intel_items)

    print("✅ Pipeline run completed successfully.")

if __name__ == "__main__":
    main()