# daily_email.py
import os
import json
import arxiv
from datetime import datetime, timedelta, timezone
from transformers import pipeline
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time

# Configuration
MIN_FALLBACK = 5
DAILY_LIMIT = 10

# choosing method
EMAIL_MODE = os.environ.get("EMAIL_MODE", "gmail")

# Loading summarizer once (pipeline downloads the model)
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

def fetch_and_score(query, days_back=1, max_results=50):
    """Return list of arXiv result dicts filtered by `days_back`."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days_back)
    client = arxiv.Client()
    search = arxiv.Search(query=query, max_results=max_results, sort_by=arxiv.SortCriterion.SubmittedDate, sort_order=arxiv.SortOrder.Descending)
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
    # summarize
    for p in selected:
        try:
            p['summary'] = summarizer(p['abstract'], max_length=70, min_length=25, do_sample=False)[0]['summary_text']
            time.sleep(0.1)  # small sleep to be polite
        except Exception as e:
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

def send_via_sendgrid(sender, receiver, html_content):
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    sg_key = os.environ.get("SENDGRID_API_KEY")
    message = Mail(from_email=sender, to_emails=receiver, subject="📢 Your Daily Research Digest", html_content=html_content)
    sg = SendGridAPIClient(sg_key)
    resp = sg.send(message)
    if resp.status_code >= 400:
        raise Exception(f"SendGrid error: {resp.status_code} {resp.body}")

def main():
    # read subscribers.json that will be in repo root
    if not os.path.exists("subscribers.json"):
        print("No subscribers.json found — exiting.")
        return
    with open("subscribers.json", "r") as f:
        subscribers = json.load(f)

    for user_email, categories in subscribers.items():
        category_papers = {}
        for cat in categories:
            prints = get_top_for_category(cat, top_n=5)  # 5 each
            category_papers[cat] = prints
        html = build_email_html(user_email, category_papers)

        if EMAIL_MODE == "gmail":
            sender = os.environ.get("EMAIL_USER")
            send_via_gmail(sender, user_email, html)
        else:
            sender = os.environ.get("EMAIL_USER")
            send_via_sendgrid(sender, user_email, html)
        print(f"Sent to {user_email}")

if __name__ == "__main__":
    main()

