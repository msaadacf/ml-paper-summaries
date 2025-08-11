# streamlit_app.py
import streamlit as st
import requests
import json
import base64
import os
from typing import List

# Configuration...
REPO_OWNER = "msaadacf"      
REPO_NAME = "ml-paper-summaries"            
BRANCH = "main"
FILE_PATH = "subscribers.json"

# Allowing only following categories for now:
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

st.title("📚 ML Paper Digest — Subscribe")

st.markdown("Please choose up to 3 categories and subscribe. Your subscription will be saved. You can unsubcribe later if you want :)")

# Input fields
email = st.text_input("Email address", "")
selected = st.multiselect("Choose up to 3 categories", CATEGORIES, max_selections=3)

# Load GitHub token from Streamlit secrets
try:
    GH_TOKEN = st.secrets["GH_PAT"]
except Exception:
    GH_TOKEN = None

if GH_TOKEN is None:
    st.error("GitHub token not found. Add `GH_PAT` to Streamlit Secrets (see README).")
    st.stop()

def get_subscribers_from_repo() -> dict:
    """Reads subscribers.json from repo (or return empty)."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    r = requests.get(url, headers={"Authorization": f"token {GH_TOKEN}"})
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode()
        return json.loads(content), data["sha"]
    elif r.status_code == 404:
        return {}, None
    else:
        st.error(f"Error reading subscribers file: {r.status_code} {r.text}")
        return {}, None

def commit_subscribers_to_repo(subs: dict, sha=None, message="Update subscribers"):
    """Creates or update subscribers.json in the repo."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    content_b64 = base64.b64encode(json.dumps(subs, indent=2).encode()).decode()
    payload = {
        "message": message,
        "content": content_b64,
        "branch": BRANCH
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers={"Authorization": f"token {GH_TOKEN}"}, json=payload)
    return r

# Load current subscribers
subscribers, sha = get_subscribers_from_repo()

# Subscribe button
if st.button("Subscribe"):
    if not email:
        st.error("Please enter an email.")
    elif not selected:
        st.error("Please select at least one category.")
    elif len(selected) > 3:
        st.error("Please choose up to 3 categories.")
    else:
        subscribers[email] = selected
        resp = commit_subscribers_to_repo(subscribers, sha=sha, message=f"Add/Update subscription for {email}")
        if resp.status_code in (200, 201):
            st.success(f"Subscribed {email} to {', '.join(selected)}")
            # update sha for future updates
            sha = resp.json().get("content", {}).get("sha")
        else:
            st.error(f"Ah, failed to save subscription: {resp.status_code} {resp.text}")

# Unsubscribe button
if st.button("Unsubscribe"):
    if not email:
        st.error("Enter an email.")
    elif email not in subscribers:
        st.warning("Email not subscribed.")
    else:
        del subscribers[email]
        resp = commit_subscribers_to_repo(subscribers, sha=sha, message=f"Remove subscription for {email}")
        if resp.status_code in (200, 201):
            st.success(f"Unsubscribed {email}")
            sha = resp.json().get("content", {}).get("sha")
        else:
            st.error(f"Failed to save subscription: {resp.status_code} {resp.text}")

st.markdown("---")
st.write("Current subscribers (preview):")
st.write(subscribers)


