# daily_email.py
import os
import arxiv
from arxiv import Client, Search, UnexpectedEmptyPageError
from datetime import datetime, timedelta, timezone
from transformers import pipeline
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time
from supabase import create_client

# ---- NEW: timezone-safe guard ----
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

# Config
MIN_FALLBACK = 5
DAILY_LIMIT = 10
EMAIL_MODE = os.environ.get("EMAIL_MODE", "gmail")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")


def is_now_8am_chicago_window(window_minutes: int = 15) -> bool:
    """
    Returns True only if current time in America/Chicago is between 08:00 and 08:window_minutes.
    Acts as a safety check in case cron is misconfigured.
    """
    if ZoneInfo is None:
        # Fallback: assume cron is correct
        return True
    now_chi = datetime.now(ZoneInfo("America/Chicago"))
    start = now_chi.replace(hour=8, minute=0, second=0, microsecond=0)
    end = start + timedelta(minutes=window_minutes)
    return start <= now_chi < end


def fetch_and_score(query, days_back=1, max_results=50):
    """
    Fetch papers from arXiv safely, with proper query formatting and
    graceful handling of empty pages.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days_back)
    client = Client()

    # Wrap query to handle spaces and special characters
    safe_query = f'all:"{query.strip()}"'

    search = Search(
        query=safe_query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    papers = []
    try:
        for result in client.results(search):
            if result.published >= cutoff:
                papers.append({
                    "title": result.title.strip(),
                    "abstract": result.summary.strip().replace("\n", " "),
                    "link": result.entry_id
                })
    except UnexpectedEmptyPageError:
        # No results found — return empty list instead of crashing
        print(f"[WARN] No results found for query: {query}")

    return papers


def get_top_for_category(category, top_n=10):
    papers = fetch_and_score(category, days_back=1, max_results=50)
    if len(papers) < MIN_FALLBACK:
        papers = fetch_and_score(category, days_back=7, max_results=200)
    selected = papers[:top_n]
    for p in selected:
        try:
            p['summary'] = summarizer(
                p['abstract'],
                max_length=70,
                min_length=25,
                do_sample=False
            )[0]['summary_text']
            time.sleep(0.1)
        except Exception:
            p['summary'] = p['abstract'][:200] + "..."
    return selected


def build_email_html(user_email, category_papers):
    html = """<html><body style="font-family: Arial, sans-serif;">"""
    html += "<h2>📢 Daily Research Digest</h2>"
    # ---- CHANGED: greeting ----
    html += "<p>Hello learner, here are your selected topics:</p>"
    for cat, papers in category_papers.items():
        html += f"<h3>📂 {cat.title()}</h3><ol>"
        for p in papers:
            html += (
                f"<li><b>{p['title']}</b><br>"
                f"<p>{p['summary']}</p>"
                f"<a href='{p['link']}'>Read full paper</a></li><br>"
            )
        html += "</ol>"
    html += "<p style='font-size:small;color:gray;'>Generated automatically.</p></body></html>"
    return html


def send_via_gmail(sender, receiver, html_content, subject="📢 Your Daily Research Digest"):
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    username = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_PASS")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver
    msg.attach(MIMEText(html_content, "html"))
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(username, password)
        server.sendmail(sender, receiver, msg.as_string())


def fetch_subscribers():
    resp = supabase.table("subscribers").select("*").execute()
    return resp.data


def main():
    # ---- NEW: safety check to ensure 8am America/Chicago ----
    override = os.environ.get("OVERRIDE_SEND", "").strip() == "1"
    if not override and not is_now_8am_chicago_window(window_minutes=15):
        print("[INFO] Not in the 8:00–8:15 AM America/Chicago window. Exiting.")
        return

    subscribers = fetch_subscribers()
    for sub in subscribers:
        email = sub["email"]
        categories = sub["categories"]
        category_papers = {}
        for cat in categories:
            # ---- ENSURE 5 per category ----
            category_papers[cat] = get_top_for_category(cat, top_n=5)

        html = build_email_html(email, category_papers)

        if EMAIL_MODE == "gmail":
            sender = os.environ.get("EMAIL_USER")
            send_via_gmail(sender, email, html)

        print(f"Sent to {email}")


if __name__ == "__main__":
    main()
