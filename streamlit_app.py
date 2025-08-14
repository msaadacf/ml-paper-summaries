# streamlit_app.py
import streamlit as st
from supabase import create_client
import os
from datetime import datetime
import threading
import time

# Import helpers from daily_email
from daily_email import get_top_for_category, build_email_html, send_via_gmail

# Config
CATEGORIES = [
    "machine learning",
    "robotics",
    "computer vision",
    "natural language processing",
    "statistics",
    "reinforcement learning",
    "bayesian",
    "graph neural network"
]

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
EMAIL_MODE = st.secrets["EMAIL_MODE"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("📚 ML Paper Digest — Subscribe")
st.markdown("Choose up to 3 categories and subscribe. You'll receive daily research updates in your email.")

email = st.text_input("Email address", "")
selected = st.multiselect("Choose up to 3 categories", CATEGORIES, max_selections=3)


def add_to_all_subscribers(email):
    exists = supabase.table("all_subscribers").select("*").eq("email", email).execute()
    if not exists.data:
        supabase.table("all_subscribers").insert({"email": email}).execute()


def add_to_subscribers(email, categories):
    supabase.table("subscribers").upsert({
        "email": email,
        "categories": categories
    }).execute()


def remove_from_subscribers(email):
    supabase.table("subscribers").delete().eq("email", email).execute()


def fetch_subscribers():
    resp = supabase.table("subscribers").select("*").execute()
    return {row["email"]: row["categories"] for row in resp.data}


def _send_confirmation_email_now(email, categories):
    # Build fresh summaries (5 per category) + confirmation note
    category_papers = {}
    for cat in categories:
        category_papers[cat] = get_top_for_category(cat, top_n=5)

    html = build_email_html(email, category_papers)
    # Add a one-line confirmation at the top
    confirmation_note = (
        "<p style='font-style:italic;'>"
        "You’re subscribed to the ML Paper Digest. You’ll receive daily updates at 8:00 AM (America/Chicago)."
        "</p>"
    )
    html = html.replace("</h2>", "</h2>" + confirmation_note, 1)

    if EMAIL_MODE == "gmail":
        sender = st.secrets["EMAIL_USER"]
        send_via_gmail(sender, email, html, subject="✅ Subscription Confirmed — ML Paper Digest")


def send_confirmation_email_delayed(email, categories, delay_seconds=60):
    """Fire-and-forget 1-minute delayed confirmation to avoid blocking the UI."""
    def _task():
        try:
            time.sleep(delay_seconds)
            _send_confirmation_email_now(email, categories)
        except Exception as e:
            # Log in Streamlit server logs
            print(f"[ERROR] Confirmation send failed for {email}: {e}")

    th = threading.Thread(target=_task, daemon=True)
    th.start()


# Subscribe
if st.button("Subscribe"):
    if not email:
        st.error("Please enter an email.")
    elif not selected:
        st.error("Select at least one category.")
    elif len(selected) > 3:
        st.error("Max 3 categories allowed.")
    else:
        add_to_subscribers(email, selected)
        add_to_all_subscribers(email)
        # ---- NEW: non-blocking delayed confirmation ----
        send_confirmation_email_delayed(email, selected, delay_seconds=60)
        st.success(f"Subscribed {email} to {', '.join(selected)}. You'll receive a confirmation email with fresh summaries in ~1 minute.")

# Unsubscribe
if st.button("Unsubscribe"):
    if not email:
        st.error("Please enter an email.")
    else:
        subs = fetch_subscribers()
        if email not in subs:
            st.warning("Email not found in active subscribers.")
        else:
            remove_from_subscribers(email)
            st.success(f"{email} unsubscribed successfully.")

st.markdown("---")
st.caption("Thank you for subscribing. If you want to ever unsubscribe, just add your email above and click 'Unsubscribe'. Thank you!")
