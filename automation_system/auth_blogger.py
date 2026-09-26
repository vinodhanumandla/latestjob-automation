"""
Google Blogger OAuth2 Setup & Token Generator
Run this script once to authenticate with your Google Account and enable Blogger Draft/Publishing.
"""
import sys
import json
import os
from pathlib import Path

# Fix Windows PowerShell encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root (New app test2-v17) to sys.path so 'automation_system' is found
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from automation_system.config.config import (
    BLOGGER_CLIENT_SECRET_FILE, BLOGGER_TOKEN_FILE, BLOG_ID
)

def authenticate_blogger():
    print("=" * 60)
    print("[AUTH] GOOGLE BLOGGER OAUTH2 AUTHENTICATION SETUP")
    print("=" * 60)

    if not BLOGGER_CLIENT_SECRET_FILE.exists():
        print("\n[!] 'client_secret.json' not found in automation_system/config/ folder.")
        print("\nTo connect your real Blogger website, follow these simple steps:")
        print("1. Go to Google Cloud Console: https://console.cloud.google.com/")
        print("2. Enable 'Blogger API v3'.")
        print("3. Go to 'Credentials' -> Create 'OAuth client ID' (Application type: Desktop app).")
        print("4. Download the JSON file and save it as:")
        print(f"   -> {BLOGGER_CLIENT_SECRET_FILE}")
        print("\nAlternatively, you can paste an Access Token directly.")
        
        token_input = input("\nEnter OAuth Access Token (or press Enter to exit): ").strip()
        if token_input:
            token_data = {"access_token": token_input}
            with open(BLOGGER_TOKEN_FILE, "w", encoding="utf-8") as f:
                json.dump(token_data, f, indent=2)
            print("[OK] Access token saved successfully to blogger_token.json!")
            return True
        return False

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        SCOPES = ["https://www.googleapis.com/auth/blogger"]
        print("\nStarting local authentication server...", flush=True)
        print("A browser window will open for you to sign in with your Google account.", flush=True)
        print("Please choose your account and click 'Continue' / 'Allow'...", flush=True)
        
        flow = InstalledAppFlow.from_client_secrets_file(str(BLOGGER_CLIENT_SECRET_FILE), SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")

        token_data = {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes
        }

        with open(BLOGGER_TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2)

        print("\n" + "=" * 60, flush=True)
        print("[SUCCESS] Blogger API authenticated successfully!", flush=True)
        print(f"Token saved to: {BLOGGER_TOKEN_FILE}", flush=True)
        print("=" * 60, flush=True)
        return True
    except ImportError:
        print("\n⚠️ 'google-auth-oauthlib' is required for automatic browser login.")
        print("Run: pip install google-auth-oauthlib google-api-python-client")
        return False
    except Exception as e:
        print("Authentication error:", e)
        return False

if __name__ == "__main__":
    authenticate_blogger()
