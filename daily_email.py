# daily_email.py
import os
import arxiv
from datetime import datetime, timedelta, timezone
from transformers import pipeline
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time
from supabase import create_client

# Config
MIN_FALLBACK = 5
DAILY_LIMIT = 10
EMAIL_MODE = os.environ.get("EMAIL_MODE", "gmail")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

def fetch_and_score(query, days_back=1, max_results=50):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days_back)
    client = arxiv.Client()
    search = arxiv.Search(query=query, max_results=max_results,
                          sort_by=arxiv.SortCriterion.SubmittedDate,
                          sort_order=arxiv.SortOrder.Descending)
    papers = []
    for result in client.results(search):
        if result.published >= cutoff:
            papers.append({
                "title": result.title.strip(),
                "abstract": result.summary.strip().replace("\n", " "),
                "link": result.entry_id
            })
    return papers

def get_top_for_category(category, top_n=10):
    papers = fetch_and_score(category, days_back=1, max_results=50)
    if len(papers) < MIN_FALLBACK:
        papers = fetch_and_score(category, days_back=7, max_results=200)
    selected = papers[:top_n]
    for p in selected:
        try:
            p['summary'] = summarizer(p['abstract'], max_length=70, min_length=25, do_sample=False)[0]['summary_text']
            time.sleep(0.1)
        except Exception:
            p['summary'] = p['abstract'][:200] + "..."
    return selected

def build_email_html(user_email, category_papers):
    html = """<html><body style="font-family: Arial, sans-serif;">"""
    html += f"<h2>📢 Daily Research Digest</h2><p>Hi {user_email}, here are your selected topics:</p>"
    for cat, papers in category_papers.items():
        html += f"<h3>📂 {cat.title()}</h3><ol>"
        for p in papers:
            html += f"<li><b>{p['title']}</b><br><p>{p['summary']}</p><a href='{p['link']}'>Read full paper</a></li><br>"
        html += "</ol>"
    html += "<p style='font-size:small;color:gray;'>Generated automatically.</p></body></html>"
    return html

def send_via_gmail(sender, receiver, html_content):
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    username = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_PASS")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "📢 Your Daily Research Digest"
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
    subscribers = fetch_subscribers()
    for sub in subscribers:
        email = sub["email"]
        categories = sub["categories"]
        category_papers = {}
        for cat in categories:
            category_papers[cat] = get_top_for_category(cat, top_n=5)
        html = build_email_html(email, category_papers)

        if EMAIL_MODE == "gmail":
            sender = os.environ.get("EMAIL_USER")
            send_via_gmail(sender, email, html)
        print(f"Sent to {email}")

if __name__ == "__main__":
    main()
