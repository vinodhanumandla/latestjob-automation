"""
Automatic Internal Linking Engine for LatestJobNotifications.online
Discovers semantically relevant existing Blogger posts and injects natural contextual backlinks.
"""
import re
import json
import logging
import requests
from bs4 import BeautifulSoup
from automation_system.config.config import WEBSITE_URL
from automation_system.database.db import get_db_connection, get_current_ist_time

logger = logging.getLogger(__name__)

class InternalLinkingEngine:
    def __init__(self):
        self.website_url = WEBSITE_URL.rstrip("/")

    def sync_existing_posts_from_feed(self):
        """
        Pulls published posts from Blogger's JSON feed and populates the local internal_post_index cache.
        """
        feed_url = f"{self.website_url}/feeds/posts/default?alt=json&max-results=50"
        try:
            resp = requests.get(feed_url, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"Could not fetch Blogger feed: Status {resp.status_code}")
                return 0

            data = resp.json()
            entries = data.get("feed", {}).get("entry", [])
            conn = get_db_connection()
            cursor = conn.cursor()
            synced_count = 0
            now_time = get_current_ist_time()

            for entry in entries:
                post_id = entry.get("id", {}).get("$t", "").split("post-")[-1]
                title = entry.get("title", {}).get("$t", "")
                
                # Extract post URL
                post_url = ""
                for link in entry.get("link", []):
                    if link.get("rel") == "alternate":
                        post_url = link.get("href", "")
                        break

                if not post_url:
                    continue

                # Extract labels/categories
                categories = [c.get("term", "") for c in entry.get("category", []) if c.get("term")]
                labels_str = ", ".join(categories)

                # Simple org/category extraction from title
                org = title.split()[0] if title else ""

                cursor.execute("""
                INSERT OR REPLACE INTO internal_post_index (
                    blogger_post_id, title, url, labels, organization, published_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (post_id, title, post_url, labels_str, org, now_time, now_time))
                synced_count += 1

            conn.commit()
            conn.close()
            logger.info(f"Synced {synced_count} posts into internal_post_index.")
            return synced_count
        except Exception as e:
            logger.error(f"Error syncing Blogger posts for internal linking: {e}")
            return 0

    def find_relevant_posts(self, job_data, max_links=5):
        """
        Scores existing posts in the cache for semantic relevance to the current job.
        Scoring:
        - Organization match: +40
        - Category/Label match: +25
        - Qualification match: +15
        - Keyword match: +10
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, url, labels, organization FROM internal_post_index")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            # Try to sync once if cache is empty
            self.sync_existing_posts_from_feed()
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, url, labels, organization FROM internal_post_index")
            rows = cursor.fetchall()
            conn.close()

        org = job_data.get("organization", "").lower()
        post_name = job_data.get("post_name", "").lower()
        qual = job_data.get("qualification", "").lower()

        scored_posts = []
        for row in rows:
            p_title = row["title"].lower()
            p_url = row["url"]
            p_labels = (row["labels"] or "").lower()
            p_org = (row["organization"] or "").lower()

            score = 0
            # Org Match
            if org and (org in p_title or org in p_org):
                score += 40
            # Post name match
            if post_name and any(word in p_title for word in post_name.split() if len(word) > 3):
                score += 25
            # Qualification match
            if any(q in p_title or q in p_labels for q in ["degree", "10th", "12th", "b.tech", "diploma"] if q in qual):
                score += 15
            # Bank / Railway / SSC category match
            for cat in ["bank", "railway", "ssc", "police", "apprentice", "court"]:
                if cat in org and cat in p_title:
                    score += 20

            if score > 0:
                scored_posts.append({
                    "title": row["title"],
                    "url": p_url,
                    "score": score
                })

        # Sort by highest score
        scored_posts.sort(key=lambda x: x["score"], reverse=True)
        return scored_posts[:max_links]

    def inject_internal_links(self, html_content, job_data, max_links=4):
        """
        Injects 3 to 6 contextual internal links into appropriate sections of the article
        without keyword stuffing.
        """
        relevant_posts = self.find_relevant_posts(job_data, max_links=max_links)
        if not relevant_posts:
            return html_content, 0

        # Build a sleek Related Job Opportunities box
        links_items_html = ""
        for p in relevant_posts:
            links_items_html += f"""
      <li style="margin-bottom: 8px;">
        👉 <a href="{p['url']}" style="color: #0284c7; font-weight: 600; text-decoration: underline;" target="_blank" rel="noopener">{p['title']}</a>
      </li>"""

        related_box_html = f"""
  <!-- AUTOMATIC INTERNAL LINKING: RELATED SARKARI NAUKRI OPPORTUNITIES -->
  <div class="jp-related-links-box" style="background: #f0f9ff; border-left: 4px solid #0284c7; border-radius: 8px; padding: 16px 20px; margin: 24px 0; font-family: sans-serif;">
    <h3 style="margin: 0 0 10px 0; font-size: 15px; font-weight: 700; color: #0369a1;">📌 Also Check Related Government Jobs & Notifications:</h3>
    <ul style="list-style: none; padding-left: 0; margin: 0; font-size: 13px;">
      {links_items_html}
    </ul>
  </div>
"""

        # Inject before FAQ or Important Links section
        if '<h2 class="jp-h2" id="faqs">' in html_content:
            modified_html = html_content.replace(
                '<h2 class="jp-h2" id="faqs">',
                f'{related_box_html}\n  <h2 class="jp-h2" id="faqs">'
            )
        elif '<h2 class="jp-h2" id="important-links">' in html_content:
            modified_html = html_content.replace(
                '<h2 class="jp-h2" id="important-links">',
                f'{related_box_html}\n  <h2 class="jp-h2" id="important-links">'
            )
        else:
            modified_html = html_content + f"\n{related_box_html}"

        return modified_html, len(relevant_posts)

if __name__ == "__main__":
    linker = InternalLinkingEngine()
    print("Syncing posts...")
    count = linker.sync_existing_posts_from_feed()
    print(f"Synced {count} posts.")
