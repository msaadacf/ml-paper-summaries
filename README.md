# AI Newsboy
<img width="1842" height="949" alt="image" src="https://github.com/user-attachments/assets/ca37c498-fe43-4996-a844-eb0adf55ad76" />

The goal behind creation of this project is to receive automated daily summaries of recent research publications with high-impact potential in AI domains. 

Design summary: Automated daily arXiv research papers summaries delivered in an email, with a Streamlit subscription UI and a GitHub Actions scheduler.

## What it does
- Users subscribe via a Streamlit app by selecting up to **3** AI related categories.
- The backend pulls recent papers from **arXiv**, summarizes them using **facebook/bart-large-cnn** (Transformers + Torch), and sends an HTML email.
- A **GitHub Actions cron** runs every day and sends the digest to all active subscribers.
- Subscriptions are stored in **Supabase**.

## Repo structure
.github/workflows/daily_ml_digest.yml # daily scheduler (GitHub Actions)
daily_email.py # arXiv fetch + summarization + email sender
streamlit_app.py # subscription UI (Streamlit) + confirmation email
requirements.txt # python deps
subscribers.json # unused in current implementation (leftover)
README.md


## Architecture
1. **Streamlit UI (`streamlit_app.py`)**
   - Collects `email` + up to 3 `categories`
   - Writes to Supabase tables:
     - `subscribers` (email + categories array)
     - `all_subscribers` (email only)
   - Sends a **confirmation email** around 60 seconds after subscribing (non-blocking thread).

2. **Daily digest job (`daily_email.py`)**
   - Reads subscribers from Supabase (`subscribers` table)
   - For each subscriber and each category:
     - Fetches recent papers from arXiv
     - Summarizes abstracts (BART)
     - Builds HTML email
     - Sends via Gmail SMTP
   - Includes a safety window: only sends if current time is between **08:00–08:15 America/Chicago** unless overridden.

3. **Scheduler (`.github/workflows/daily_ml_digest.yml`)**
   - Runs daily at **13:00 UTC** (intended to map to 08:00 America/Chicago depending on DST)
   - Installs dependencies
   - Runs `python daily_email.py`

## Requirements
- Python 3.10+ (as Actions uses 3.10)
- Supabase project with the required tables (currently this project is offline due to a lack of Supabase subscription. But you can run it online if you still have free access)
- Gmail account credentials (App password is recommended)

## Supabase setup
Create these tables:

### `subscribers`
- `email` (text, primary key or unique)
- `categories` (text[] / array)

### `all_subscribers`
- `email` (text, primary key or unique)

Your code uses:
- `upsert` into `subscribers`
- `insert` into `all_subscribers` if not exists
- `delete` from `subscribers` to unsubscribe

## Configuration (Secrets)

### GitHub Actions secrets (Repo → Settings → Secrets and variables → Actions)
Required:
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `EMAIL_MODE` (use `gmail`)
- `EMAIL_USER` (your gmail address)
- `EMAIL_PASS` (gmail app password)

Optional:
- `OVERRIDE_SEND` (set to `1` if you want to bypass the 8:00–8:15am Chicago safety window)

### Streamlit secrets
If deploying on Streamlit Community Cloud, set these in the app’s Secrets:
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `EMAIL_MODE`
- `EMAIL_USER`
- `EMAIL_PASS`

## Running locally
```bash
python -m venv .venv
source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt

# Run Streamlit UI
streamlit run streamlit_app.py

