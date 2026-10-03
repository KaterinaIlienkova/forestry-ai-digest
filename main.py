import os
import time
import smtplib
import feedparser
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google import genai

# Global & regional intelligence feeds: Direct portals and language-agnostic entity searches
RSS_FEEDS = [
    # =========================================================================
    # 1. DIRECT INDUSTRY & INSTITUTIONAL PORTALS
    # =========================================================================
    "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET&concepts=18-35354",  # Yle: Forestry (Nordic regional)
    "https://www.metsalehti.fi/feed/",                                                       # Metsälehti (Finnish forestry hub)
    "https://www.luke.fi/en/rss",                                                            # Luke (Natural Resources Institute Finland)
    "https://www.timber-online.net/rss",                                                     # Timber Online (Central Europe markets)
    "https://forestsnews.cifor.org/feed",                                                    # CIFOR (International forestry policy)
    "https://news.mongabay.com/feed/?post_type=post&s=forest+tech",                          # Mongabay (Global forest technologies)

    # =========================================================================
    # 2. COMPETITOR TRACKING (Language-Agnostic Entity Clusters)
    # Target: Arbonaut, AFRY smart forestry, Sitowise, Field Finland, Koko Forest,
    # CollectiveCrunch, Unique land use, Trimble Forestry, Microforest, Remsoft, Indufor, Triona, Interpine
    # =========================================================================
    "https://news.google.com/rss/search?q=(Arbonaut+OR+%22CollectiveCrunch%22+OR+%22Trimble+Forestry%22+OR+Indufor+OR+Remsoft)",
    "https://news.google.com/rss/search?q=(%22AFRY+smart+forestry%22+OR+Sitowise+OR+%22Field+Finland%22+OR+%22Koko+Forest%22+OR+Triona+OR+Interpine)",
    "https://news.google.com/rss/search?q=(%22Unique+land+use%22+OR+Microforest)+forestry",

    # =========================================================================
    # 3. KEY CLIENTS, PROSPECTS & STAKEHOLDERS (Global Entity Clusters)
    # Target: Ponsse, John Deere Forestry, Kesla, UPM, Stora Enso, Asian Pulp and Paper,
    # Metsä Group, Mondi, APRIL, SAFCOL, York Timbers, New Forests, Tornator, Versowood,
    # Finsilva, Koskisen, United Bankers Forest Fund, Metsähallitus
    # =========================================================================
    "https://news.google.com/rss/search?q=(Ponsse+OR+%22John+Deere+Forestry%22+OR+Kesla)+(forest+OR+harvester+OR+forestry)",
    "https://news.google.com/rss/search?q=(%22Metsä+Group%22+OR+UPM+OR+%22Stora+Enso%22+OR+Mondi)+(investointi+OR+investment+OR+mill+OR+pulp)",
    "https://news.google.com/rss/search?q=(%22Asian+Pulp+and+Paper%22+OR+%22APRIL+group%22+OR+SAFCOL+OR+%22York+Timbers%22+OR+%22New+Forests%22)",
    "https://news.google.com/rss/search?q=(Tornator+OR+Versowood+OR+Finsilva+OR+Koskisen+OR+%22United+Bankers%22+OR+Metsähallitus)",

    # =========================================================================
    # 4. MACRO INVESTMENTS, CAPITAL & INDUSTRIAL SCALE (Pulp, Sawmills, Biomass)
    # =========================================================================
    "https://news.google.com/rss/search?q=(forestry+OR+biomass+OR+pulp+OR+sawmill)+(investment+OR+acquisition+OR+%22funding+program%22)",
    "https://news.google.com/rss/search?q=(metsäteollisuus+OR+sahateollisuus+OR+sellutehdas)+(investointi+OR+hanke+OR+rahoitus)",
    "https://news.google.com/rss/search?q=(forestal+OR+celulosa+OR+aserradero)+(inversión+OR+planta+OR+adquisición)",

    # =========================================================================
    # 5. REGULATION, NATIONAL LEGISLATION & EUDR TRACEABILITY
    # =========================================================================
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

    print(f"Total deduplicated articles collected for executive review: {len(articles)}")
    return articles[:45]

def generate_digest(articles):
    """Synthesizes executive briefing via Gemini strictly aligned with management radar specifications."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Environment variable GEMINI_API_KEY is not set.")

    if not articles:
        return "<p>No significant market shifts, competitor updates, or regulatory signals identified for the past 7 days.</p>"

    # Format collected articles into a structured text prompt
    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"{i}. [{a['date']}] {a['title']}\nURL: {a['link']}\nSummary: {a['summary']}\n\n"

    prompt = f"""
You are the Executive Market & Strategic Intelligence Agent for the management team at Metsäavain (Forest Key), Joensuu, Finland.

Core Objective:
Synthesize strategic intelligence across global markets to identify critical shifts that might otherwise go unnoticed.
Crucial constraint: This is NOT an active sales tool. Do not generate sales pitches. Generate clear, objective strategic signals so leadership can evaluate whether follow-up actions are warranted.

Key Entities of Interest:
- Competitors: Arbonaut, AFRY smart forestry, Sitowise, Field Finland, Koko Forest, CollectiveCrunch, Unique land use GmbH, Trimble Forestry, Microforest, Remsoft, Indufor, Triona, Interpine.
- Target Clients & Key Stakeholders: Ponsse, John Deere Forestry, Kesla, UPM, Stora Enso, Asian Pulp and Paper, Metsä Group, Mondi, APRIL, SAFCOL, York Timbers, New Forests, Tornator, Versowood, Finsilva, Koskisen, United Bankers Forest Fund, Metsähallitus Forestry.
- Core Sectors: Precision forestry, biomass energy, wood transformation, and pulp.

Language Directive:
- Raw articles may arrive in ANY world language (Finnish, English, Spanish, Portuguese, Swedish, German, etc.).
- Analyze each article natively in its original language.
- Translate and synthesize all findings uniformly into professional, executive-level English.

Collected news items from the past 7 days:
{articles_text}

Task:
1. Filter aggressively for SIGNIFICANCE. Skip trivial operational noise. Prioritize:
   - Major industrial projects (new pulp mills, sawmills, major expansions, large-scale capital programs).
   - Significant competitor moves (M&A, new software/platforms, strategic partnerships, major contracts, profit warnings, executive appointments).
   - Major corporate shifts in named clients & forestry asset owners.
   - Decisive policy, EUDR compliance, and national/international regulatory developments.
2. Structure output into 5 clear HTML sections:
   - ⚔️ Competitors & Market Movers (Arbonaut, Sitowise, Trimble, CollectiveCrunch, etc.)
   - 🌲 Strategic Clients & Industry Giants (Ponsse, UPM, Stora Enso, Metsä Group, Tornator, etc.)
   - 🏭 Major Capital Investments & Facilities (Pulp mills, sawmills, biomass plants, funding programs)
   - ⚖️ Policy, Legislation & EUDR Compliance (National forest laws, EU directives, geolocation traceability)
   - 🔬 Geospatial AI & Operational Technology (LiDAR point clouds, satellite algorithms, precision forestry tech)
3. For each selected high-impact story (aim for 4 to 6 stories in total across sections):
   - 📌 Clickable Title: (`<a href="..." target="_blank">Title</a>`)
   - 💡 Executive Summary: 2-3 concise, fact-driven sentences explaining the core event.
   - 🎯 Strategic Signal: 1 sharp sentence highlighting the direct impact, opportunity, or risk for Metsäavain leadership.

Tone: Crisp, objective, executive-level business English.
IMPORTANT: Return ONLY the raw HTML snippet. Do not wrap response in markdown code blocks like ```html or ```.
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
            print(f"Attempting generation with model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            print(f"✅ Successfully synthesized briefing with {model_name}!")

            # Strip accidental markdown code block wrappers
            cleaned_html = response.text.strip()
            if cleaned_html.startswith("```html"):
                cleaned_html = cleaned_html[7:]
            if cleaned_html.startswith("```"):
                cleaned_html = cleaned_html[3:]
            if cleaned_html.endswith("```"):
                cleaned_html = cleaned_html[:-3]

            return cleaned_html.strip()
        except Exception as e:
            print(f"⚠️ Model {model_name} request failed: {e}. Trying next available model...")
            time.sleep(3)

    # Graceful degradation fallback: direct curated list if all LLM endpoints fail
    print("⚠️ All AI model endpoints currently experiencing outages. Falling back to direct curated listing...")
    fallback_html = "<h3>⚡ Weekly Curated Industry Intelligence (Direct Feed)</h3>"
    fallback_html += "<p><i>Note: Automated AI synthesis temporarily bypassed due to API capacity constraints. Direct executive selection below:</i></p><ul>"
    for a in articles[:8]:
        fallback_html += f"""
        <li style="margin-bottom: 16px;">
            <b><a href="{a['link']}" target="_blank" style="color: #2e7d32; font-size: 15px;">{a['title']}</a></b> 
            <span style="color: #7f8c8d; font-size: 12px;">({a['date']})</span>
            <p style="margin: 4px 0 0 0; font-size: 13px; color: #34495e;">{a['summary']}</p>
        </li>
        """
    fallback_html += "</ul>"
    return fallback_html

def send_email(html_content, recipient_email="ileynkova.kate@gmail.com"):
    """Dispatches formatted HTML briefing via Gmail SMTP."""
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_APP_PASSWORD")

    if not sender_email or not sender_password:
        print("Error: Missing SENDER_EMAIL or SENDER_APP_PASSWORD environment variables.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌲 Metsäavain Executive Radar: Competitors, Clients & Policy — {datetime.now().strftime('%d.%m.%Y')}"
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

    print("Step 2: Synthesizing executive briefing via AI...")
    digest_html = generate_digest(articles)

    print("Step 3: Dispatching email report...")
    send_email(digest_html, recipient_email="ileynkova.kate@gmail.com")

if __name__ == "__main__":
    main()