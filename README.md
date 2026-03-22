# Render Deployment Guide

## Step 1: Prepare Your Credentials

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Create a new Web Service
3. Connect your GitHub repo (or upload directly)

## Step 2: Add Environment Variables

In Render's Environment Variables section, add:

| Key | Value |
|-----|-------|
| `TELEGRAM_TOKEN` | Your bot token from @BotFather |
| `ADMIN_ID` | Your Telegram user ID from @userinfobot |
| `GOOGLE_CREDS` | Paste entire contents of `conmaret-key.json` |

## Step 3: Update bot.py (one change)

Change line 11 to:
```python
import json
import io
from google.auth import service_account

creds_info = json.loads(os.getenv("GOOGLE_CREDS"))
creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
```

## Step 4: Deploy

Click "Create Web Service" and you're done!

---

## Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file (copy from .env.example and fill in values)
cp .env.example .env

# Run locally
python bot.py
```