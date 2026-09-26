import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

from automation_system.database.db import init_database
from automation_system.web.app import app

if __name__ == "__main__":
    init_database()
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Admin Web Dashboard starting on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
