"""
Central Configuration for LatestJobNotifications Automation Pipeline
"""
import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "database"
LOGS_DIR = BASE_DIR / "logs"
MEDIA_DIR = BASE_DIR / "media" / "thumbnails"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Database
DB_PATH = DATA_DIR / "automation.db"

# Master Prompt Path
MASTER_PROMPT_PATH = CONFIG_DIR / "master_prompt_v1.txt"
ACTIVE_PROMPT_VERSION = "MASTER_POST_V1"

# Website & SEO Details
WEBSITE_URL = "https://www.latestjobnotifications.online"
BLOG_ID = os.getenv("BLOGGER_BLOG_ID", "4127483416381856661") # Can be updated in Admin Dashboard or env

# Operational Modes
# "SAFE": Post created as DRAFT on Blogger. Admin preview & approval required before publishing.
# "AUTO": Automatically published if validation score >= 95%.
PUBLISH_MODE = os.getenv("PUBLISH_MODE", "SAFE")

# Admin Dashboard Password (matches Apps Script admin PIN or custom)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Timezone
TIMEZONE = "Asia/Kolkata"

import base64
import json
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or base64.b64decode(b"QVEuQWI4Uk42TG9HQm9LNjIzT0MxX2ZjOWlLVnJnSmtJSkV4a1k5YTllek5RbVVqUFJOeWc=").decode()

# Cloudflare Workers AI (10,000 free requests/day per account)
CLOUDFLARE_CONFIG_FILE = CONFIG_DIR / "cloudflare_config.json"
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID") or base64.b64decode(b"OTRhYjhiZWE0MjBjN2YwMTZiOTM2OWI3Y2Q1YjM4MTU=").decode()
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN") or base64.b64decode(b"Y2Z1dF9qa0pzZ3F2STBUSmxFekVDVU1hUzhUaUJTZkRHa1lmUUFTOHR1WDVsZTM3NjQ5MDU=").decode()

if CLOUDFLARE_CONFIG_FILE.exists():
    try:
        with open(CLOUDFLARE_CONFIG_FILE, "r", encoding="utf-8") as _cf_f:
            _cf_data = json.load(_cf_f)
            if _cf_data.get("account_id"):
                CLOUDFLARE_ACCOUNT_ID = _cf_data.get("account_id", "").strip()
            if _cf_data.get("api_token"):
                CLOUDFLARE_API_TOKEN = _cf_data.get("api_token", "").strip()
    except Exception:
        pass

# Google Blogger OAuth2 credentials file path
BLOGGER_CLIENT_SECRET_FILE = CONFIG_DIR / "client_secret.json"
BLOGGER_TOKEN_FILE = CONFIG_DIR / "blogger_token.json"

# Scanner URLs
FREEJOBALERT_LATEST_URL = "https://www.freejobalert.com/latest-notifications/"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
