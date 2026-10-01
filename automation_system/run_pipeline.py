"""
End-to-End Pipeline Runner for LatestJobNotifications Automation System
"""
import sys
import os
import json
import logging
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from automation_system.config.config import PUBLISH_MODE, ACTIVE_PROMPT_VERSION
from automation_system.database.db import get_db_connection, get_current_ist_time, init_database
from automation_system.core.scanner import JobScanner
from automation_system.core.thumbnail_generator import ThumbnailGenerator
from automation_system.core.generator import ContentGenerator
from automation_system.core.internal_linker import InternalLinkingEngine
from automation_system.core.validator import PostValidator
from automation_system.core.blogger_client import BloggerClient
from automation_system.core.location_detector import detect_job_location

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class JobPipeline:
    def __init__(self):
        init_database()
        self.scanner = JobScanner()
        self.thumbnail_gen = ThumbnailGenerator()
        self.thumbnail_generator = self.thumbnail_gen
        self.content_gen = ContentGenerator()
        self.internal_linker = InternalLinkingEngine()
        self.validator = PostValidator()
        self.blogger_client = BloggerClient()

    def run_date_scan(self, filter_date=None):
        """Scans notifications for a given date or today, and saves new ones as DISCOVERED."""
        logger.info(f"Starting scan for date: {filter_date or 'ALL/LATEST'}")
        notifs = self.scanner.get_latest_notifications(filter_date=filter_date)
        discovered_ids = []

        for item in notifs:
            job_id, status = self.scanner.sync_and_save_job(item)
            if status == "DISCOVERED" and job_id:
                discovered_ids.append(job_id)
                logger.info(f"✅ Discovered new job #{job_id}: {item['organization']} - {item['post_name']}")
            elif status == "DUPLICATE":
                logger.info(f"⏩ Skipped duplicate job: {item['organization']} - {item['post_name']}")

        return discovered_ids

    def process_job(self, job_id, is_auto_publish=False):
        """
        Executes the full pipeline for a single job:
        Extraction -> AI Content -> HD Thumbnail -> Internal Linking -> Validation -> Blogger Draft.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job = cursor.fetchone()

        if not job:
            logger.error(f"Job #{job_id} not found.")
            conn.close()
            return False

        logger.info(f"Processing Job #{job_id}: {job['organization']} - {job['post_name']}")

        # 1. Generate High-Fidelity 16:9 Thumbnail matching reference
        extracted_info = {}
        if job["extracted_data"]:
            try:
                extracted_info = json.loads(job["extracted_data"])
            except Exception:
                pass

        resolved_location = detect_job_location(
            org=job["organization"],
            post_name=job["post_name"],
            detail_url=job["notification_url"],
            text_content=job["raw_content"] or "",
            extracted_location=extracted_info.get("job_location", "")
        )

        thumb_path, thumb_filename = self.thumbnail_gen.generate_hd_thumbnail(
            organization=job["organization"],
            post_name=job["post_name"],
            vacancies=job["total_vacancies"],
            last_date=job["last_date"],
            qualification=job["qualification"],
            location=resolved_location,
            salary=extracted_info.get("salary", ""),
            age_limit=extracted_info.get("age_limit", "")
        )
        # Upload thumbnail to public CDN so Google Blogger displays thumbnail in dashboard
        public_url = self.thumbnail_gen.upload_to_public_host(thumb_path)
        thumb_url = public_url if public_url else f"/media/thumbnails/{thumb_filename}"

        # 2. Generate Content with Master Post Template
        job_dict = dict(job)
        post_data = self.content_gen.generate_post(job_dict, thumbnail_url=thumb_url)

        # 3. Inject Contextual Internal Links
        final_html, links_count = self.internal_linker.inject_internal_links(
            post_data["content"], job_dict, max_links=4
        )

        # 4. Validate Final Content
        score, is_valid, val_report = self.validator.validate_article(
            post_data["title"], final_html, job_dict
        )

        # 5. Create Blogger Draft (SAFE MODE)
        now_time = get_current_ist_time()
        status = "DRAFT_READY"

        # Save Generated Post Record (Delete older generated record for this job if any)
        cursor.execute("DELETE FROM generated_posts WHERE job_id = ?", (job_id,))
        cursor.execute("""
        INSERT INTO generated_posts (
            job_id, prompt_version, generated_title, generated_content,
            thumbnail_path, thumbnail_url, labels, search_description,
            internal_links_count, validation_score, validation_report, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            ACTIVE_PROMPT_VERSION,
            post_data["title"],
            final_html,
            thumb_path,
            thumb_url,
            ", ".join(post_data["labels"]),
            post_data["search_description"],
            links_count,
            score,
            json.dumps(val_report),
            status,
            now_time,
            now_time
        ))

        # Update Job Status
        cursor.execute("UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?", (status, now_time, job_id))

        conn.commit()
        conn.close()

        logger.info(f"🎉 Job #{job_id} successfully processed! Status: {status}, Score: {score}/100, Internal Links: {links_count}")
        return True

    def create_blogger_draft(self, job_id):
        """Admin Action 1: Creates the post as a DRAFT on Blogger with base64 embedded thumbnail and saves the Blogger Post ID."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM generated_posts WHERE job_id = ? ORDER BY id DESC LIMIT 1", (job_id,))
        gen_post = cursor.fetchone()

        if not gen_post:
            logger.info(f"Generating post for Job #{job_id} before creating Blogger draft...")
            self.process_job(job_id)
            cursor.execute("SELECT * FROM generated_posts WHERE job_id = ? ORDER BY id DESC LIMIT 1", (job_id,))
            gen_post = cursor.fetchone()

        if not gen_post:
            conn.close()
            return {"success": False, "error": "Could not generate post for this job. Please check URL."}

        labels_list = [l.strip() for l in (gen_post["labels"] or "").split(",") if l.strip()]

        # Prepare content for Blogger: Ensure thumbnail is a public https:// URL so Blogger displays the thumbnail in dashboard
        content_to_send = gen_post["generated_content"]
        thumb_path = gen_post["thumbnail_path"]
        current_thumb_url = gen_post["thumbnail_url"] or ""

        # If the thumbnail is not yet a public https:// URL, upload it now
        if not current_thumb_url.startswith("http"):
            if thumb_path and os.path.exists(thumb_path):
                public_url = self.thumbnail_gen.upload_to_public_host(thumb_path)
                if public_url:
                    content_to_send = content_to_send.replace(current_thumb_url, public_url)
                    cursor.execute("UPDATE generated_posts SET thumbnail_url = ? WHERE id = ?", (public_url, gen_post["id"]))
                    conn.commit()

        # Push as DRAFT to Blogger API
        blogger_res = self.blogger_client.create_post(
            title=gen_post["generated_title"],
            content=content_to_send,
            labels=labels_list,
            search_description=gen_post["search_description"],
            is_draft=True
        )

        now_time = get_current_ist_time()
        if blogger_res.get("success"):
            blogger_post_id = blogger_res.get("id")
            blogger_url = blogger_res.get("url", "")

            # Save Blogger Post ID in blogger_posts table for later publishing
            cursor.execute("""
                INSERT OR REPLACE INTO blogger_posts (job_id, blogger_post_id, blogger_url, status, updated_at)
                VALUES (?, ?, ?, 'DRAFT', ?)
            """, (job_id, blogger_post_id, blogger_url, now_time))

            # Set status to SENT_DRAFT
            cursor.execute("UPDATE jobs SET status = 'SENT_DRAFT', updated_at = ? WHERE id = ?", (now_time, job_id))
            cursor.execute("UPDATE generated_posts SET status = 'SENT_DRAFT', updated_at = ? WHERE id = ?", (now_time, gen_post["id"]))
            conn.commit()
            conn.close()
            logger.info(f"[DRAFT SENT] Job #{job_id} saved as Blogger DRAFT. Blogger Post ID: {blogger_post_id}")
            return {"success": True, "draft_id": blogger_post_id, "url": blogger_url}
        else:
            conn.close()
            err = blogger_res.get("error", "Unknown error")
            logger.error(f"[ERROR] Draft creation failed for Job #{job_id}: {err}")
            return {"success": False, "error": err}

    def approve_and_publish_job(self, job_id):
        """
        Admin Action 2: Publishes the Blogger DRAFT live using the two-step
        URL trick so posts get a clean SEO permalink:
          /YYYY/MM/<org-short>-recruitment-<year>.html

        Steps:
          1. Delete the existing Blogger draft (it has no locked URL yet).
          2. Publish a NEW post with the desired slug as the title.
             Blogger locks /YYYY/MM/<slug>.html at this point.
          3. Immediately PATCH the real post title back.
          4. Update the DB with the final live URL.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch saved Blogger Draft record
        cursor.execute("SELECT * FROM blogger_posts WHERE job_id = ? ORDER BY id DESC LIMIT 1", (job_id,))
        blogger_record = cursor.fetchone()

        if not blogger_record:
            conn.close()
            return {"success": False, "error": "No Blogger Draft found. Please click 'Approve as Blogger Draft' first."}

        old_draft_id = blogger_record["blogger_post_id"]
        now_time = get_current_ist_time()

        # Fetch generated post content
        cursor.execute("SELECT * FROM generated_posts WHERE job_id = ? ORDER BY id DESC LIMIT 1", (job_id,))
        gen_post = cursor.fetchone()
        if not gen_post:
            conn.close()
            return {"success": False, "error": "Generated post content not found."}

        # Fetch original job for org name and year
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job = cursor.fetchone()

        # --- Step 1: Delete the draft so no duplicate exists ---
        if old_draft_id and not old_draft_id.startswith("draft_"):
            deleted = self.blogger_client.delete_post(old_draft_id)
            logger.info(f"Deleted old draft {old_draft_id}: {deleted}")

        # --- Step 2 & 3: Publish with slug, then patch title ---
        labels_list = [l.strip() for l in (gen_post["labels"] or "").split(",") if l.strip()]

        # Determine year from last_date or use current year
        import datetime, re
        year = datetime.datetime.now().year
        if job and job["last_date"]:
            year_match = re.search(r'(202\d)', str(job["last_date"]))
            if year_match:
                year = int(year_match.group(1))

        org_name = job["organization"] if job else ""
        post_name = job["post_name"] if job else ""
        slug = self.blogger_client.generate_slug(org_name, year, post_name)
        logger.info(f"[URL TRICK] Slug for Job #{job_id}: '{slug}'")

        content_to_send = gen_post["generated_content"]
        real_title = gen_post["generated_title"]

        pub_res = self.blogger_client.create_post_with_custom_url(
            real_title=real_title,
            slug_title=slug,
            content=content_to_send,
            labels=labels_list,
            search_description=gen_post["search_description"] or ""
        )

        if pub_res.get("success"):
            live_url = pub_res.get("url", "")
            new_post_id = pub_res.get("id", "")

            cursor.execute("UPDATE jobs SET status = 'PUBLISHED', updated_at = ? WHERE id = ?", (now_time, job_id))
            cursor.execute(
                "UPDATE blogger_posts SET status = 'PUBLISHED', blogger_post_id = ?, blogger_url = ?, published_at = ?, updated_at = ? WHERE id = ?",
                (new_post_id, live_url, now_time, now_time, blogger_record["id"])
            )
            cursor.execute(
                "UPDATE generated_posts SET status = 'PUBLISHED', updated_at = ? WHERE job_id = ?",
                (now_time, job_id)
            )
            conn.commit()
            conn.close()
            logger.info(f"[LIVE] Job #{job_id} PUBLISHED! Slug='{slug}' URL: {live_url}")
            return {"success": True, "url": live_url, "slug": slug}
        else:
            conn.close()
            err = pub_res.get("error", "Unknown error")
            logger.error(f"[ERROR] Publish failed for Job #{job_id}: {err}")
            return {"success": False, "error": err}

    def direct_auto_publish_job(self, job_id):
        """
        1-Click Direct Auto Publish:
          1. If not generated yet, runs process_job(job_id) (AI content + HD thumbnail + validation)
          2. If Blogger draft not created yet, creates blogger draft
          3. Publishes LIVE using the two-step URL trick (locks clean <=35 char SEO permalink)
        """
        logger.info(f"⚡ [1-CLICK AUTO PUBLISH] Starting end-to-end pipeline for Job #{job_id}...")

        # Step 1: Always generate fresh AI content + modern photorealistic thumbnail
        logger.info(f"⚡ [1-CLICK AUTO PUBLISH] Generating fresh AI content + modern thumbnail for Job #{job_id}...")
        proc_ok = self.process_job(job_id)
        if not proc_ok:
            return {"success": False, "error": "Step 1 Failed: AI post / thumbnail generation error."}

        # Step 2: Ensure Blogger draft exists (or recreate with new thumbnail)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blogger_posts WHERE job_id = ? ORDER BY id DESC LIMIT 1", (job_id,))
        blogger_rec = cursor.fetchone()
        conn.close()

        if not blogger_rec:
            logger.info(f"⚡ [1-CLICK AUTO PUBLISH] Creating initial Blogger draft for Job #{job_id}...")
            draft_res = self.create_blogger_draft(job_id)
            if not draft_res.get("success"):
                return {"success": False, "error": f"Step 2 Failed: Draft creation error: {draft_res.get('error')}"}

        # Step 3: Publish Live to Blogger with clean custom URL
        logger.info(f"⚡ [1-CLICK AUTO PUBLISH] Publishing Job #{job_id} live with custom URL trick...")
        pub_res = self.approve_and_publish_job(job_id)
        return pub_res

    def force_regenerate_job(self, job_id):
        """
        Force-regenerates thumbnail + AI content for ANY job (including PUBLISHED ones).
        Deletes the old generated_posts record and runs the full pipeline again.
        Does NOT delete the live Blogger post - use update_live_post_thumbnail() after this.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job = cursor.fetchone()
        if not job:
            conn.close()
            return {"success": False, "error": f"Job #{job_id} not found."}

        logger.info(f"[FORCE REGEN] Deleting old generated_posts record for Job #{job_id}...")
        cursor.execute("DELETE FROM generated_posts WHERE job_id = ?", (job_id,))
        conn.commit()
        conn.close()

        logger.info(f"[FORCE REGEN] Running full pipeline for Job #{job_id}...")
        success = self.process_job(job_id)
        if not success:
            return {"success": False, "error": "Pipeline generation failed. Check logs."}

        # Fetch the newly generated record
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT thumbnail_url, thumbnail_path FROM generated_posts WHERE job_id = ? ORDER BY id DESC LIMIT 1", (job_id,))
        row = cursor.fetchone()
        conn.close()

        thumb_url = row["thumbnail_url"] if row else ""
        logger.info(f"[FORCE REGEN] Job #{job_id} regenerated. New thumb_url: {thumb_url}")
        return {"success": True, "job_id": job_id, "thumbnail_url": thumb_url}

    def update_live_post_thumbnail(self, job_id):
        """
        PATCHes an already-published Blogger post with a fresh modern thumbnail + content
        WITHOUT deleting/republishing (URL stays unchanged).
        Automatically generates a fresh AI thumbnail and patches in one step!
        """
        # Step 1: Ensure fresh thumbnail and content are generated
        logger.info(f"[UPDATE LIVE] Regenerating fresh photorealistic thumbnail for Job #{job_id}...")
        self.force_regenerate_job(job_id)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch the generated post
        cursor.execute("SELECT * FROM generated_posts WHERE job_id = ? ORDER BY id DESC LIMIT 1", (job_id,))
        gen_post = cursor.fetchone()
        if not gen_post:
            conn.close()
            return {"success": False, "error": "Failed to generate new post content."}

        # Fetch the blogger post record
        cursor.execute("SELECT * FROM blogger_posts WHERE job_id = ? ORDER BY id DESC LIMIT 1", (job_id,))
        blogger_record = cursor.fetchone()
        if not blogger_record or not blogger_record["blogger_post_id"]:
            conn.close()
            return {"success": False, "error": "No Blogger post record found for this job."}

        blogger_post_id = blogger_record["blogger_post_id"]
        labels_list = [l.strip() for l in (gen_post["labels"] or "").split(",") if l.strip()]

        # Ensure thumbnail is a public URL
        content_to_send = gen_post["generated_content"]
        thumb_path = gen_post["thumbnail_path"]
        current_thumb_url = gen_post["thumbnail_url"] or ""

        if not current_thumb_url.startswith("http"):
            if thumb_path and os.path.exists(thumb_path):
                public_url = self.thumbnail_gen.upload_to_public_host(thumb_path)
                if public_url:
                    content_to_send = content_to_send.replace(current_thumb_url, public_url)
                    now_time = get_current_ist_time()
                    cursor.execute("UPDATE generated_posts SET thumbnail_url = ?, updated_at = ? WHERE id = ?",
                                   (public_url, now_time, gen_post["id"]))
                    conn.commit()
                    current_thumb_url = public_url

        # PATCH the live Blogger post
        logger.info(f"[UPDATE LIVE] Patching Blogger post {blogger_post_id} for Job #{job_id} with new thumbnail...")
        patch_res = self.blogger_client.update_post(
            post_id=blogger_post_id,
            title=gen_post["generated_title"],
            content=content_to_send,
            labels=labels_list
        )

        now_time = get_current_ist_time()
        if patch_res.get("success"):
            live_url = patch_res.get("url", blogger_record["blogger_url"] or "")
            cursor.execute("UPDATE blogger_posts SET blogger_url = ?, updated_at = ? WHERE id = ?",
                           (live_url, now_time, blogger_record["id"]))
            cursor.execute("UPDATE generated_posts SET status = 'PUBLISHED', updated_at = ? WHERE id = ?",
                           (now_time, gen_post["id"]))
            cursor.execute("UPDATE jobs SET status = 'PUBLISHED', updated_at = ? WHERE id = ?",
                           (now_time, job_id))
            conn.commit()
            conn.close()
            logger.info(f"[UPDATE LIVE] Job #{job_id} live post updated! New thumb: {current_thumb_url}")
            return {
                "success": True,
                "url": live_url,
                "thumbnail_url": current_thumb_url,
                "job_id": job_id
            }
        else:
            conn.close()
            return {"success": False, "error": patch_res.get("error", "Blogger PATCH failed")}


if __name__ == "__main__":
    pipeline = JobPipeline()
    print("Running initial pipeline test...")
    discovered = pipeline.run_date_scan()
    print("Discovered Jobs:", discovered)
    if discovered:
        pipeline.process_job(discovered[0])

