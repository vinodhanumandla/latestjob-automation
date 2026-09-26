"""
SQLite Database Manager & Schema Initialization
"""
import sqlite3
import json
from datetime import datetime
import pytz
from automation_system.config.config import DB_PATH, TIMEZONE

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_current_ist_time():
    ist = pytz.timezone(TIMEZONE)
    return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

def init_database():
    """Initializes all required tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Jobs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_name TEXT DEFAULT 'FreeJobAlert',
        source_url TEXT,
        notification_url TEXT UNIQUE,
        pdf_url TEXT,
        apply_url TEXT,
        official_website_url TEXT,
        post_date TEXT,
        notification_number TEXT,
        organization TEXT,
        post_name TEXT,
        total_vacancies TEXT,
        qualification TEXT,
        last_date TEXT,
        raw_content TEXT,
        extracted_data TEXT, -- JSON string
        status TEXT DEFAULT 'DISCOVERED', -- DISCOVERED, PROCESSING, EXTRACTED, GENERATED, DRAFT_READY, PUBLISHED, FAILED, DUPLICATE, REJECTED
        error_message TEXT,
        created_at TEXT,
        updated_at TEXT
    );
    """)

    # Generated Posts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS generated_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        prompt_version TEXT,
        generated_title TEXT,
        generated_content TEXT,
        thumbnail_path TEXT,
        thumbnail_url TEXT,
        labels TEXT, -- comma-separated
        search_description TEXT,
        internal_links_count INTEGER DEFAULT 0,
        validation_score INTEGER DEFAULT 0,
        validation_report TEXT, -- JSON string
        status TEXT DEFAULT 'DRAFT_READY',
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs (id)
    );
    """)

    # Blogger Posts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS blogger_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        blogger_post_id TEXT UNIQUE,
        blogger_url TEXT,
        status TEXT DEFAULT 'DRAFT', -- DRAFT, PUBLISHED
        published_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs (id)
    );
    """)

    # Internal Post Index for fast semantic link matching
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS internal_post_index (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        blogger_post_id TEXT UNIQUE,
        title TEXT,
        url TEXT UNIQUE,
        labels TEXT,
        keywords TEXT,
        organization TEXT,
        category TEXT,
        qualification TEXT,
        state TEXT,
        published_at TEXT,
        updated_at TEXT
    );
    """)

    # System Configuration Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT
    );
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_database()
    print("Database initialized successfully at:", DB_PATH)
