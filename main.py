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

# Comprehensive feeds: Direct specialized portals and multilingual entity search clusters
RSS_FEEDS = [
    # 1. Direct Specialized Portals
    "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET&concepts=18-35354",  # Yle: Forestry (Nordic regional)
    "https://www.metsalehti.fi/feed/",                                                       # Metsälehti (Leading Finnish forest media)
    "https://www.luke.fi/en/rss",                                                            # Luke (Natural Resources Institute Finland)
    "https://www.timber-online.net/rss",                                                     # Timber Online (Central Europe markets)
    "https://forestsnews.cifor.org/feed",                                                    # CIFOR (International forestry policy & governance)
    "https://news.mongabay.com/feed/?post_type=post&s=forest+tech",                          # Mongabay (Global forest tech & monitoring)

    # 2. Competitors
    "https://news.google.com/rss/search?q=(Arbonaut+OR+%22CollectiveCrunch%22+OR+%22Trimble+Forestry%22+OR+Indufor+OR+Remsoft)",
    "https://news.google.com/rss/search?q=(%22AFRY+smart+forestry%22+OR+Sitowise+OR+%22Field+Finland%22+OR+%22Koko+Forest%22+OR+Triona+OR+Interpine)",
    "https://news.google.com/rss/search?q=(%22Unique+land+use%22+OR+Microforest)+forestry",

    # 3. Strategic Clients, Asset Owners & Equipment Giants
    "https://news.google.com/rss/search?q=(Ponsse+OR+%22John+Deere+Forestry%22+OR+Kesla)+(forest+OR+harvester+OR+forestry)",
    "https://news.google.com/rss/search?q=(%22Metsä+Group%22+OR+UPM+OR+%22Stora+Enso%22+OR+Mondi)+(investointi+OR+investment+OR+mill+OR+pulp)",
    "https://news.google.com/rss/search?q=(%22Asian+Pulp+and+Paper%22+OR+%22APRIL+group%22+OR+SAFCOL+OR+%22York+Timbers%22+OR+%22New+Forests%22)",
    "https://news.google.com/rss/search?q=(Tornator+OR+Versowood+OR+Finsilva+OR+Koskisen+OR+%22United+Bankers%22+OR+Metsähallitus)",
    "https://news.google.com/rss/search?q=(%22UPM%22+OR+%22Stora+Enso%22+OR+Arauco+OR+CMPC+OR+Suzano)+(celulosa+OR+forestal+OR+madera)&hl=es-419&gl=CL&ceid=CL:es-419",

    # 4. Macro Investments, Capital & Industrial Scale (Pulp, Sawmills, Biomass)
    "https://news.google.com/rss/search?q=(forestry+OR+biomass+OR+pulp+OR+sawmill)+(investment+OR+acquisition+OR+%22funding+program%22)",
    "https://news.google.com/rss/search?q=(metsäteollisuus+OR+sahateollisuus+OR+sellutehdas)+(investointi+OR+hanke+OR+rahoitus)&hl=fi&gl=FI&ceid=FI:fi",
    "https://news.google.com/rss/search?q=(forestal+OR+celulosa+OR+aserradero)+(inversión+OR+planta+OR+adquisición)&hl=es-419&gl=CL&ceid=CL:es-419",

    # 5. Regulation, National Legislation & EUDR Traceability
    "https://news.google.com/rss/search?q=EUDR+(deforestation+OR+timber+OR+compliance+OR+traceability)",
    "https://news.google.com/rss/search?q=(forestry+OR+metsätalous+OR+forestal)+(legislation+OR+policy+OR+sääntely+OR+reglamento)"
]

def fetch_recent_articles(days=7):
    """
    Fetches, deduplicates, and filters multilingual articles within the sliding window.
    Passes all qualifying articles directly without artificial list slicing.
    """
    articles = []
    seen_links = set()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    print(f"Collecting articles across feeds (sliding window: past {days} days)...")

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            print(f"Checking {url[:75]}...: found {len(feed.entries)} entries")

            for entry in feed.entries:
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
    return articles

def generate_digest_data(articles):
    """
    Synthesizes executive briefing into structured JSON objects using Gemini.
    Returns None if all AI models are unavailable (prevents uncurated noise).
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

Core Mission:
Identify and synthesize critical, strategic industry signals across global and Nordic markets that could otherwise go unnoticed.
Crucial constraint: This is NOT a sales tool. Do not generate sales pitches. Generate objective, executive-level signals for leadership evaluation.

Key Entities of Interest:
- Competitors: Arbonaut, AFRY smart forestry, Sitowise, Field Finland, Koko Forest, CollectiveCrunch, Unique land use, Trimble, Microforest, Remsoft, Indufor, Triona, Interpine.
- Strategic Clients & Stakeholders: Ponsse, John Deere, Kesla, UPM, Stora Enso, Asian Pulp and Paper, Metsä Group, Mondi, APRIL, SAFCOL, York Timbers, New Forests, Tornator, Versowood, Finsilva, Koskisen, United Bankers Forest Fund, Metsähallitus.
- Macro Pillars: Precision forestry, biomass energy, wood transformation, sawmills, and pulp.

Language & Processing Directive:
- Raw articles arrive in multiple languages (Finnish, English, Spanish, Swedish, German, Portuguese, etc.).
- Analyze each article natively in its original language.
- Synthesize all strategic findings uniformly into clear, professional, executive-level English.

Geographic & Market Scope:
- Ensure a balanced global and regional perspective. Do NOT restrict the briefing exclusively to Finland.
- Ingest and highlight significant international developments (Central Europe, North America, Latin America, EU-wide policy) alongside Nordic signals.

Selection Logic (Dynamic Significance Threshold):
- Do NOT force a rigid count of articles.
- Include EVERY article that clears the executive threshold of significance (typically between 4 to 10 high-value stories).
- Filter out trivial operational noise, routine local events, or generic PR fluff. Focus strictly on:
  * Major industrial capital projects (new pulp mills, sawmills, bioenergy plants, significant funding programs).
  * Notable competitor maneuvers (M&A, new platforms/software, strategic partnerships, major contracts, profit warnings, executive appointments).
  * Strategic organizational shifts in named clients & asset owners.
  * Significant national forest policies, EU directives, and EUDR compliance/traceability milestones.

Raw candidate articles collected from the past 7 days:
{articles_text}

OUTPUT FORMAT:
Return ONLY a valid, parseable JSON array of objects. Do NOT wrap output in markdown code fences like ```json or ```.
Schema for each JSON object:
[
  {{
    "category": "Competitors" | "Clients & Partners" | "Capital & Investments" | "Policy & EUDR" | "Geospatial Tech",
    "entity": "Name of primary organization or market sector involved",
    "title": "Clear, informative executive headline",
    "summary": "2-3 concise, fact-driven sentences explaining the core event and context",
    "strategic_signal": "1 sharp sentence highlighting the direct strategic significance, risk, or opportunity for Metsäavain leadership",
    "url": "Original URL link from the article",
    "date": "Publication date"
  }}
]
"""

    client = genai.Client(api_key=api_key)

    # Active, supported Gemini model IDs (tested for v1beta)
    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-3.1-pro-preview",
        "gemini-3.5-flash",
        "gemini-3.8-flash"
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
            print(f"⚠️️ Model {model_name} request failed: {e}. Trying next available model...")
            time.sleep(3)

    # If all models fail, return None to trigger an alert instead of sending random uncurated news
    print("❌ All AI models unavailable (503/404). Aborting uncurated noise output.")
    return None

def build_html_digest(items):
    """Constructs responsive executive HTML email from structured intelligence items."""
    if not items:
        return "<p>No significant market shifts, competitor updates, or regulatory signals identified for the past 7 days.</p>"

    categories = {}
    category_icons = {
        "Competitors": "⚔️ Competitors & Market Dynamics",
        "Clients & Partners": "🌲 Strategic Clients & Organizations",
        "Capital & Investments": "🏭 Major Capital Investments & Facilities",
        "Policy & EUDR": "⚖️ Policy, Legislation & EUDR Compliance",
        "Geospatial Tech": "🔬 Geospatial AI & Operational Technology"
    }

    for item in items:
        cat = item.get("category", "General")
        categories.setdefault(cat, []).append(item)

    html = ""
    for cat_key, cat_items in categories.items():
        cat_title = category_icons.get(cat_key, f"📌 {cat_key}")
        html += f"<h3 style='color: #2e7d32; border-bottom: 1px solid #c8e6c9; padding-bottom: 6px; margin-top: 26px;'>{cat_title}</h3>"
        html += "<ul style='padding-left: 0; list-style-type: none; margin: 0;'>"

        for item in cat_items:
            html += f"""
            <li style="margin-bottom: 20px; background: #fafafa; padding: 14px 16px; border-left: 4px solid #2e7d32; border-radius: 4px;">
                <div style="margin-bottom: 6px;">
                    <a href="{item.get('url', '#')}" target="_blank" style="color: #1b5e20; font-weight: bold; font-size: 15px; text-decoration: none;">
                        {item.get('title')}
                    </a>
                    <span style="color: #7f8c8d; font-size: 12px; margin-left: 8px;">({item.get('date', 'Recent')})</span>
                </div>
                <p style="margin: 4px 0 8px 0; font-size: 13.5px; line-height: 1.5; color: #2c3e50;">
                    {item.get('summary')}
                </p>
                <div style="background: #e8f5e9; padding: 8px 12px; border-radius: 4px; font-size: 12.5px; color: #1b5e20; line-height: 1.4;">
                    <b>🎯 Strategic Signal:</b> {item.get('strategic_signal')}
                </div>
            </li>
            """
        html += "</ul>"

    return html

def push_to_clickup(items):
    """
    Pushes structured intelligence items into ClickUp list tasks with clean Custom Fields.
    """
    api_token = os.environ.get("CLICKUP_API_TOKEN")
    list_id = os.environ.get("CLICKUP_LIST_ID")

    if not api_token or not list_id:
        print("ℹ️ ClickUp synchronization skipped: CLICKUP_API_TOKEN or CLICKUP_LIST_ID not configured.")
        return

    print(f"Step 4: Synchronizing {len(items)} items to ClickUp list {list_id}...")
    
    # 1. Отримуємо ID кастомних полів зі списку ClickUp
    fields_url = f"https://api.clickup.com/api/v2/list/{list_id}/field"
    headers = {
        "Authorization": api_token,
        "Content-Type": "application/json"
    }

    custom_field_map = {}
    try:
        req = urllib.request.Request(fields_url, headers=headers, method="GET")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for f in data.get("fields", []):
                custom_field_map[f.get("name", "").strip().lower()] = f
    except Exception as e:
        print(f"  ⚠️ Could not fetch list custom fields: {e}")

    task_url = f"https://api.clickup.com/api/v2/list/{list_id}/task"

    for item in items:
        category = item.get("category", "General")
        entity = item.get("entity", "Forestry")
        title = item.get("title", "Signal")
        strategic_signal = item.get("strategic_signal", "")
        article_url = item.get("url", "")
        date_str = item.get("date", "")

        # Заповнюємо кастомні поля, якщо вони створені в інтерфейсі
        task_custom_fields = []

        # Поле Strategic Signal
        if "strategic signal" in custom_field_map:
            field_id = custom_field_map["strategic signal"]["id"]
            task_custom_fields.append({"id": field_id, "value": strategic_signal})

        # Поле Entity
        if "entity" in custom_field_map:
            field_id = custom_field_map["entity"]["id"]
            task_custom_fields.append({"id": field_id, "value": entity})

        # Поле Category (Dropdown)
        if "category" in custom_field_map:
            cat_field = custom_field_map["category"]
            options = cat_field.get("type_config", {}).get("options", [])
            matched_option = next((opt for opt in options if category.lower() in opt.get("name", "").lower()), None)
            if matched_option:
                task_custom_fields.append({"id": cat_field["id"], "value": matched_option.get("orderindex")})

        task_payload = {
            "name": title,
            "description": (
                f"### 💡 Executive Summary\n{item.get('summary', '')}\n\n"
                f"### 🎯 Strategic Signal for Metsäavain\n{strategic_signal}\n\n"
                f"---\n"
                f"**Category:** {category}\n"
                f"**Entity / Sector:** {entity}\n"
                f"**Date:** {date_str}\n"
                f"**Source URL:** [Read Full Story]({article_url})\n"
            ),
            "tags": [entity.lower().replace(" ", "-")],
            "custom_fields": task_custom_fields
        }

        try:
            req = urllib.request.Request(
                task_url,
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

def send_email(subject, html_content, recipient_email="ileynkova.kate@gmail.com"):
    """Dispatches formatted HTML briefing via Gmail SMTP."""
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_APP_PASSWORD")

    if not sender_email or not sender_password:
        print("Error: Missing SENDER_EMAIL or SENDER_APP_PASSWORD environment variables.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
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
        print(f"✅ Notification delivered to {recipient_email}!")
    except Exception as e:
        print(f"❌ Failed to dispatch email: {e}")

def main():
    print("Step 1: Gathering fresh multilingual market, competitor, and client intelligence...")
    articles = fetch_recent_articles(days=7)

    print("Step 2: Synthesizing executive briefing via AI (JSON Structured Data)...")
    intel_items = generate_digest_data(articles)

    # Clean handling if AI service is temporarily down
    if intel_items is None:
        print("⚠️ Gemini AI unavailable. Dispatching technical downtime notification...")
        alert_subject = f"⚠️ Metsäavain Radar Alert: AI API Temporarily Unavailable — {datetime.now().strftime('%d.%m.%Y')}"
        alert_html = """
        <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 16px; border-radius: 4px;">
            <h3 style="color: #856404; margin-top: 0;">Service Alert: Weekly Digest Paused</h3>
            <p style="color: #856404; font-size: 14px; margin-bottom: 0;">
                The automated intelligence radar gathered raw news feeds as scheduled, but Google Gemini API endpoints 
                are currently experiencing temporary high-demand rate limits (HTTP 503 / 404).
            </p>
            <p style="color: #856404; font-size: 14px; margin-top: 8px;">
                <b>Action taken:</b> Uncurated raw news was <b>not</b> published or archived to keep your briefing clean. 
                The pipeline will retry automatically on the next scheduled run, or you can trigger a manual run later.
            </p>
        </div>
        """
        send_email(alert_subject, alert_html, recipient_email="ileynkova.kate@gmail.com")
        print("🛑 Workflow stopped cleanly (no noisy data pushed to ClickUp or email).")
        return

    print("Step 3: Formatting and dispatching email report...")
    digest_subject = f"🌲 Metsäavain Executive Radar — {datetime.now().strftime('%d.%m.%Y')}"
    digest_html = build_html_digest(intel_items)
    send_email(digest_subject, digest_html, recipient_email="ileynkova.kate@gmail.com")

    print("Step 4: Synchronizing items into ClickUp workspace...")
    push_to_clickup(intel_items)

    print("✅ Pipeline run completed successfully.")

if __name__ == "__main__":
    main()