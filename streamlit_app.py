# streamlit_app.py
import streamlit as st
from supabase import create_client
import os
from datetime import datetime, timedelta, timezone
from daily_email import get_top_for_category, build_email_html, send_via_gmail, send_via_sendgrid

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

def send_confirmation_email(email, categories):
    # Fetch last 24h papers for these categories
    category_papers = {}
    for cat in categories:
        category_papers[cat] = get_top_for_category(cat, top_n=5)
    html = build_email_html(email, category_papers)

    if EMAIL_MODE == "gmail":
        sender = st.secrets["EMAIL_USER"]
        send_via_gmail(sender, email, html)
    else:
        sender = st.secrets["EMAIL_USER"]
        send_via_sendgrid(sender, email, html)

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
        send_confirmation_email(email, selected)
        st.success(f"Subscribed {email} to {', '.join(selected)}. Confirmation email sent!")

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
st.caption("Thank you for subscribing. If you want to ever unsubscibe, just add your email above and click 'Unsubscribe'. Thank you!")
