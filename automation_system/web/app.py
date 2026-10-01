"""
Admin Web Dashboard for LatestJobNotifications Automation Pipeline
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_from_directory
import pytz

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR.parent))

from automation_system.config.config import (
    ADMIN_PASSWORD, PUBLISH_MODE, ACTIVE_PROMPT_VERSION, MASTER_PROMPT_PATH, MEDIA_DIR
)
from automation_system.database.db import get_db_connection, get_current_ist_time, init_database
from automation_system.run_pipeline import JobPipeline

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "latestjobnotifications-secret-key"

pipeline = JobPipeline()

@app.route("/")
def dashboard():
    """Renders the main admin dashboard with stats and job list."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Order by Post Date (YYYY-MM-DD) descending so recent date appears first
    cursor.execute("""
    SELECT j.*, g.validation_score, g.internal_links_count, g.generated_title, g.thumbnail_url, g.id as gen_id,
           b.blogger_url, b.blogger_post_id
    FROM jobs j
    LEFT JOIN generated_posts g ON j.id = g.job_id
    LEFT JOIN blogger_posts b ON j.id = b.job_id
    ORDER BY 
        substr(j.post_date, 7, 4) || '-' || substr(j.post_date, 4, 2) || '-' || substr(j.post_date, 1, 2) DESC,
        j.id DESC
    LIMIT 150
    """)
    jobs = cursor.fetchall()

    # Get summary counts
    cursor.execute("SELECT status, count(*) as count FROM jobs GROUP BY status")
    status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

    conn.close()

    # Compute IST date labels for Today / Yesterday / Day Before Yesterday
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist)
    today_str = now_ist.strftime("%d/%m/%Y")
    today_iso = now_ist.strftime("%Y-%m-%d")
    yesterday_str = (now_ist - timedelta(days=1)).strftime("%d/%m/%Y")
    day_before_str = (now_ist - timedelta(days=2)).strftime("%d/%m/%Y")

    return render_template(
        "index.html",
        jobs=jobs,
        status_counts=status_counts,
        publish_mode=PUBLISH_MODE,
        prompt_version=ACTIVE_PROMPT_VERSION,
        now_date=today_str,
        today_iso=today_iso,
        yesterday_str=yesterday_str,
        day_before_str=day_before_str
    )

@app.route("/media/thumbnails/<filename>")
def serve_thumbnail(filename):
    """Serves generated job thumbnail banners."""
    return send_from_directory(MEDIA_DIR, filename)

@app.route("/api/scan", methods=["POST"])
def api_scan():
    """Scans FreeJobAlert for a selected date."""
    data = request.json or {}
    filter_date = data.get("date", "").strip()
    try:
        discovered = pipeline.run_date_scan(filter_date=filter_date if filter_date else None)
        return jsonify({"success": True, "count": len(discovered), "discovered_ids": discovered})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/process/<int:job_id>", methods=["POST"])
def api_process_job(job_id):
    """Runs generation, thumbnail creation, internal linking, and validation for a job."""
    try:
        success = pipeline.process_job(job_id)
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/save-token", methods=["POST"])
def api_save_token():
    """Saves Blogger OAuth2 access token from dashboard."""
    data = request.json or {}
    token = data.get("token", "").strip()
    if not token:
        return jsonify({"success": False, "error": "Token cannot be empty"}), 400

    token_data = {"access_token": token}
    res = pipeline.blogger_client.save_token(token_data)
    if res:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Failed to save token"}), 500

@app.route("/api/save-cloudflare", methods=["POST"])
def api_save_cloudflare():
    """Saves Cloudflare Account ID and API Token."""
    data = request.json or {}
    account_id = data.get("account_id", "").strip()
    api_token = data.get("api_token", "").strip()
    if not account_id or not api_token:
        return jsonify({"success": False, "error": "Account ID and API Token cannot be empty"}), 400

    try:
        from automation_system.config.config import CLOUDFLARE_CONFIG_FILE
        with open(CLOUDFLARE_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"account_id": account_id, "api_token": api_token}, f, indent=2)

        # Update in-memory pipeline generator
        pipeline.thumbnail_generator.cf_account_id = account_id
        pipeline.thumbnail_generator.cf_api_token = api_token

        return jsonify({"success": True, "message": "Cloudflare Workers AI configured successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/get-cloudflare-status", methods=["GET"])
def api_get_cloudflare_status():
    """Checks if Cloudflare is configured."""
    has_cf = bool(pipeline.thumbnail_generator.cf_account_id and pipeline.thumbnail_generator.cf_api_token)
    return jsonify({
        "configured": has_cf,
        "account_id": pipeline.thumbnail_generator.cf_account_id[:6] + "..." if pipeline.thumbnail_generator.cf_account_id else ""
    })

@app.route("/api/create-draft/<int:job_id>", methods=["POST"])
def api_create_draft(job_id):
    """Admin Approves post and creates it as a DRAFT on Blogger."""
    try:
        res = pipeline.create_blogger_draft(job_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/publish/<int:job_id>", methods=["POST"])
def api_publish_job(job_id):
    """Admin Publishes the Approved Draft to Blogger LIVE (triggers notification)."""
    try:
        res = pipeline.approve_and_publish_job(job_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/direct-publish/<int:job_id>", methods=["POST"])
def api_direct_publish_job(job_id):
    """1-Click End-to-End: Generates content, creates draft, and publishes LIVE to Blogger."""
    try:
        res = pipeline.direct_auto_publish_job(job_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/preview/<int:job_id>", methods=["GET"])
def api_preview_job(job_id):
    """Returns generated HTML and details for live preview modal."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM generated_posts WHERE job_id = ? ORDER BY id DESC LIMIT 1", (job_id,))
    post = cursor.fetchone()
    conn.close()

    if post:
        return jsonify({
            "success": True,
            "title": post["generated_title"],
            "content": post["generated_content"],
            "thumbnail_url": post["thumbnail_url"],
            "labels": post["labels"],
            "validation_score": post["validation_score"],
            "validation_report": json.loads(post["validation_report"] or "{}")
        })
    return jsonify({"success": False, "error": "Post not generated yet."}), 404

@app.route("/api/add-custom-job", methods=["POST"])
def api_add_custom_job():
    """Allows admin to paste any direct Get Details URL to instantly create a job."""
    data = request.json or {}
    detail_url = data.get("url", "").strip()
    if not detail_url:
        return jsonify({"success": False, "error": "URL is required"}), 400

    try:
        job_summary = {
            "post_date": get_current_ist_time()[:10],
            "organization": data.get("organization", "Govt Recruitment"),
            "post_name": data.get("post_name", "Various Posts"),
            "qualification": data.get("qualification", ""),
            "total_vacancies": data.get("total_vacancies", ""),
            "last_date": data.get("last_date", ""),
            "detail_url": detail_url
        }
        job_id, status = pipeline.scanner.sync_and_save_job(job_summary)
        if job_id:
            # Process immediately
            pipeline.process_job(job_id)
            return jsonify({"success": True, "job_id": job_id, "status": status})
        return jsonify({"success": False, "error": "Failed to add job"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/download-apk")
def download_apk():
    """Serves the generated Admin Hub Android APK directly to mobile devices."""
    apk_name = "LatestJobNotifications-AdminHub.apk"
    apk_path = BASE_DIR.parent / apk_name
    if apk_path.exists():
        return send_from_directory(BASE_DIR.parent, apk_name, as_attachment=True)
    # Fallback to AdminHubApp debug folder
    debug_apk = BASE_DIR.parent / "AdminHubApp" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    if debug_apk.exists():
        return send_from_directory(debug_apk.parent, debug_apk.name, as_attachment=True, download_name=apk_name)
    return "<h3>APK is compiling... Please refresh this page in a few seconds!</h3>", 404

if __name__ == "__main__":
    init_database()
    print("Starting Admin Web Dashboard on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
