import os
import sys
import json
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

# ── Restore secrets from Render Environment Variables ──────────────
config_dir = APP_DIR / "automation_system" / "config"

# Blogger OAuth token (stored as Render env secret)
blogger_token_env = os.environ.get("BLOGGER_TOKEN_JSON", "")
if blogger_token_env:
    try:
        token_file = config_dir / "blogger_token.json"
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(blogger_token_env)
        print("[OK] blogger_token.json restored from environment variable.")
    except Exception as e:
        print(f"[WARN] Could not write blogger_token.json: {e}")

# Client secret (stored as Render env secret)
client_secret_env = os.environ.get("BLOGGER_CLIENT_SECRET_JSON", "")
if client_secret_env:
    try:
        cs_file = config_dir / "client_secret.json"
        with open(cs_file, "w", encoding="utf-8") as f:
            f.write(client_secret_env)
        print("[OK] client_secret.json restored from environment variable.")
    except Exception as e:
        print(f"[WARN] Could not write client_secret.json: {e}")
# ───────────────────────────────────────────────────────────────────

from automation_system.database.db import init_database
from automation_system.web.app import app

if __name__ == "__main__":
    init_database()
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting Admin Web Dashboard on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
