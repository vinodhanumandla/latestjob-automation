"""
Google Blogger API v3 Client
Handles OAuth2 Authentication, Draft Creation, and Live Publishing.
"""
import os
import re
import time
import json
import logging
import requests
from automation_system.config.config import (
    BLOG_ID, BLOGGER_CLIENT_SECRET_FILE, BLOGGER_TOKEN_FILE
)

logger = logging.getLogger(__name__)

class BloggerClient:
    def __init__(self, blog_id=None):
        self.blog_id = blog_id or BLOG_ID
        self.access_token = self._load_token()

    def _load_token(self):
        """Loads saved OAuth2 access token, auto-refreshing if expired."""
        if BLOGGER_TOKEN_FILE.exists():
            try:
                with open(BLOGGER_TOKEN_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # If full OAuth credentials with refresh token exist, auto-refresh if needed
                if data.get("refresh_token") and data.get("client_id") and data.get("client_secret"):
                    try:
                        from google.oauth2.credentials import Credentials
                        from google.auth.transport.requests import Request
                        creds = Credentials(
                            token=data.get("access_token"),
                            refresh_token=data.get("refresh_token"),
                            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
                            client_id=data.get("client_id"),
                            client_secret=data.get("client_secret"),
                            scopes=data.get("scopes", ["https://www.googleapis.com/auth/blogger"])
                        )
                        if creds.expired and creds.refresh_token:
                            creds.refresh(Request())
                            data["access_token"] = creds.token
                            with open(BLOGGER_TOKEN_FILE, "w", encoding="utf-8") as wf:
                                json.dump(data, wf, indent=2)
                        return creds.token
                    except Exception as re:
                        logger.warning(f"Could not refresh token automatically: {re}")

                return data.get("access_token", "")
            except Exception as e:
                logger.error(f"Error loading blogger token: {e}")
        return ""

    def save_token(self, token_data):
        """Saves OAuth2 access token and refresh token."""
        try:
            with open(BLOGGER_TOKEN_FILE, "w", encoding="utf-8") as f:
                json.dump(token_data, f, indent=2)
            self.access_token = token_data.get("access_token", "")
            return True
        except Exception as e:
            logger.error(f"Error saving blogger token: {e}")
            return False

    def refresh_access_token(self):
        """Forces an OAuth2 token refresh using refresh_token."""
        if not BLOGGER_TOKEN_FILE.exists():
            return False
        try:
            with open(BLOGGER_TOKEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("refresh_token") and data.get("client_id") and data.get("client_secret"):
                from google.oauth2.credentials import Credentials
                from google.auth.transport.requests import Request
                creds = Credentials(
                    token=data.get("access_token"),
                    refresh_token=data.get("refresh_token"),
                    token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
                    client_id=data.get("client_id"),
                    client_secret=data.get("client_secret"),
                    scopes=data.get("scopes", ["https://www.googleapis.com/auth/blogger"])
                )
                creds.refresh(Request())
                data["access_token"] = creds.token
                with open(BLOGGER_TOKEN_FILE, "w", encoding="utf-8") as wf:
                    json.dump(data, wf, indent=2)
                self.access_token = creds.token
                logger.info("Successfully refreshed Blogger OAuth access token.")
                return True
        except Exception as e:
            logger.error(f"Failed to refresh Blogger token: {e}")
        return False

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """
        Removes/replaces unicode characters that cause Blogger API 400 errors.
        Handles: em-dash, en-dash, smart quotes, ellipsis, emojis (4-byte unicode).
        """
        replacements = {
            '\u2013': '-',
            '\u2014': '-',
            '\u2018': "'",
            '\u2019': "'",
            '\u201c': '"',
            '\u201d': '"',
            '\u2026': '...',
            '\u00a0': ' ',
            '\u00b0': '',
            '\ufffd': '',
        }
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        # Remove emojis and all 4-byte unicode (U+10000+) - causes Blogger 400 errors
        text = re.sub(r'[\U00010000-\U0010FFFF]', '', text)
        # Remove non-printable control chars (keep newline + tab)
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        return text

    @staticmethod
    def _sanitize_labels(labels_list, max_total_len=180, max_single_len=45):
        """
        Blogger API strictly limits:
        1. Combined total length of all labels cannot exceed 200 characters.
        2. Commas cannot be inside a label name.
        This method trims/sanitizes individual labels and keeps the total under 180 chars.
        """
        if not labels_list:
            return ["Government Jobs"]

        cleaned = []
        total_len = 0
        for l in labels_list:
            if not l:
                continue
            # Remove commas, newlines, tabs
            l_clean = re.sub(r'[\r\n\t,]', ' ', str(l))
            l_clean = re.sub(r'\s+', ' ', l_clean).strip()
            # Remove non-ascii
            l_clean = re.sub(r'[^\x00-\x7F]+', '', l_clean).strip()
            if not l_clean:
                continue

            # Shorten individual long label if needed
            if len(l_clean) > max_single_len:
                m = re.search(r'\(([^)]+)\)', l_clean)
                if m:
                    short_cand = m.group(1).strip()
                    if 'recruitment' in l_clean.lower():
                        l_clean = f"{short_cand} Recruitment"
                    elif 'jobs' in l_clean.lower():
                        l_clean = f"{short_cand} Jobs"
                    else:
                        l_clean = short_cand
                else:
                    l_clean = l_clean[:max_single_len].rstrip()

            # Ensure total combined length stays within safe budget (180 chars < 200 limit)
            if total_len + len(l_clean) <= max_total_len:
                if l_clean not in cleaned:
                    cleaned.append(l_clean)
                    total_len += len(l_clean)
            else:
                break

        return cleaned if cleaned else ["Government Jobs"]

    def create_post(self, title, content, labels=None, search_description="", is_draft=True):
        """
        Creates a new post on Blogger.
        Default is_draft=True (Safe Mode).
        Auto-refreshes token on 401.
        """
        if not self.access_token:
            logger.warning("No Blogger access token configured. Returning mock/offline draft ID.")
            return {
                "success": True,
                "mode": "OFFLINE_DRAFT",
                "id": f"draft_{int(time.time())}",
                "url": f"https://www.latestjobnotifications.online/preview-draft",
                "status": "DRAFT_READY"
            }

        url = f"https://www.googleapis.com/blogger/v3/blogs/{self.blog_id}/posts"
        params = {"isDraft": "true" if is_draft else "false"}
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        # Sanitize title, labels, and content to remove unicode/emoji chars and enforce label length budget
        clean_title = self._sanitize_text(title)
        clean_labels = self._sanitize_labels(labels)
        clean_content = self._sanitize_text(content)

        payload = {
            "kind": "blogger#post",
            "title": clean_title,
            "content": clean_content,
            "labels": clean_labels,
        }

        try:
            resp = requests.post(url, headers=headers, params=params, json=payload, timeout=25)
            # If token expired (401), auto-refresh and retry once
            if resp.status_code == 401:
                logger.info("Access token expired (401). Refreshing and retrying...")
                if self.refresh_access_token():
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    resp = requests.post(url, headers=headers, params=params, json=payload, timeout=25)

            if resp.status_code in [200, 201]:
                data = resp.json()
                return {
                    "success": True,
                    "id": data.get("id"),
                    "url": data.get("url"),
                    "status": "DRAFT" if is_draft else "PUBLISHED"
                }
            else:
                logger.error(f"Blogger API error: {resp.status_code} - {resp.text}")
                return {"success": False, "error": resp.text}
        except Exception as e:
            logger.error(f"Failed to create post via Blogger API: {e}")
            return {"success": False, "error": str(e)}

    def publish_draft(self, post_id):
        """Publishes an existing draft post upon admin approval."""
        if not self.access_token:
            return {
                "success": True,
                "mode": "OFFLINE_SIMULATED",
                "id": post_id,
                "url": f"https://www.latestjobnotifications.online/job-{post_id}.html",
                "status": "PUBLISHED"
            }

        url = f"https://www.googleapis.com/blogger/v3/blogs/{self.blog_id}/posts/{post_id}/publish"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        try:
            resp = requests.post(url, headers=headers, timeout=20)
            if resp.status_code in [200, 201]:
                data = resp.json()
                return {
                    "success": True,
                    "id": data.get("id"),
                    "url": data.get("url"),
                    "status": "PUBLISHED"
                }
            else:
                return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # -------------------------------------------------------------------------
    # Custom URL (Permalink) via Two-Step Title Trick
    # -------------------------------------------------------------------------

    @staticmethod
    def generate_slug(organization: str, year: int = None, post_name: str = "", max_len: int = 35) -> str:
        """
        Generates a clean, SEO-friendly slug within Blogger's ~35-character URL limit:
          <short-org>[-<post-keyword>]-recruitment-<year>

        Why ≤35 chars?
          Blogger's internal engine hard-truncates titles at ~35-39 characters when
          generating the .html permalink. If a slug exceeds ~35 chars, Blogger chops off
          the tail, which drops '-recruitment-2026' completely!
          By staying under 35 chars:
            - '-recruitment-2026' is 100% GUARANTEED at the end of the URL
            - No duplicate random number suffix (_01234)
            - Short org name / acronym is prioritized (e.g. DLSA, DVC, UPSSSC)
            - Post keyword added if space permits
        """
        import datetime, re
        if year is None:
            year = datetime.datetime.now().year

        suffix = f"-recruitment-{year}"  # 17 chars (e.g. '-recruitment-2026')
        budget = max(5, max_len - len(suffix))  # budget for org + post (e.g. 35 - 17 = 18 chars)

        def _clean(t: str) -> str:
            t = re.sub(r'[^\w\s]', ' ', t)
            t = re.sub(r'\s+', '-', t.strip().lower())
            return re.sub(r'-{2,}', '-', t).strip('-')

        # 1. Look for acronym or short name in parentheses: e.g. "(DLSA Kalimpong)", "(UPSSSC)", "(DVC)"
        paren_match = re.search(r'\(([^)]+)\)', organization or "")
        short_org = ""
        if paren_match:
            cand = _clean(paren_match.group(1))
            if len(cand) <= budget:
                short_org = cand

        # 2. If no paren or paren candidate too long, use initials or first words of org
        if not short_org:
            clean_org = _clean(organization or "jobs")
            words = clean_org.split('-')
            kept = []
            cur_len = 0
            for w in words:
                add_len = len(w) + (1 if kept else 0)
                if cur_len + add_len <= budget:
                    kept.append(w)
                    cur_len += add_len
                else:
                    break
            short_org = '-'.join(kept) if kept else clean_org[:budget].rstrip('-')

        if not short_org:
            short_org = "job"

        # 3. If there is remaining budget, add key post name words
        rem_budget = budget - len(short_org)
        post_slug = ""
        if post_name and rem_budget >= 4:  # room for '-' + at least 3 chars
            _FILLER = {
                'and', 'or', 'the', 'of', 'for', 'in', 'at', 'by', 'to', 'a',
                'an', 'various', 'posts', 'post', 'vacancy', 'vacancies',
                'recruitment', 'notification', 'jobs', 'job', 'more'
            }
            clean_post_words = [
                w.lower() for w in re.sub(r'[^\w\s]', ' ', post_name).split()
                if w.lower() not in _FILLER
            ]
            p_kept = []
            p_cur = 0
            for pw in clean_post_words:
                add_len = len(pw) + 1  # 1 for hyphen
                if p_cur + add_len <= rem_budget:
                    p_kept.append(pw)
                    p_cur += add_len
                else:
                    break
            if p_kept:
                post_slug = '-' + '-'.join(p_kept)

        slug = f"{short_org}{post_slug}{suffix}"
        slug = re.sub(r'[^a-z0-9-]', '-', slug)
        slug = re.sub(r'-{2,}', '-', slug).strip('-')
        return slug


    def patch_post_title(self, post_id: str, real_title: str) -> bool:
        """
        PATCHes the post title back to the real title after the URL has been
        locked by the first publish call.
        Returns True on success.
        """
        url = f"https://www.googleapis.com/blogger/v3/blogs/{self.blog_id}/posts/{post_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        try:
            resp = requests.patch(url, headers=headers,
                                  json={"title": self._sanitize_text(real_title)}, timeout=20)
            if resp.status_code in [200, 201]:
                logger.info(f"Post {post_id}: title patched to '{real_title}'")
                return True
            else:
                logger.error(f"Patch title failed: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Patch title exception: {e}")
            return False

    def delete_post(self, post_id: str) -> bool:
        """Deletes a Blogger post (used to clean up stale drafts before re-publish)."""
        url = f"https://www.googleapis.com/blogger/v3/blogs/{self.blog_id}/posts/{post_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            resp = requests.delete(url, headers=headers, timeout=20)
            return resp.status_code in [200, 204]
        except Exception as e:
            logger.error(f"Delete post exception: {e}")
            return False

    def create_post_with_custom_url(self, real_title: str, slug_title: str,
                                    content: str, labels=None,
                                    search_description: str = "") -> dict:
        """
        Two-step trick to get a clean custom permalink on Blogger:
          Step 1 – Publish the post with `slug_title` as the title.
                   Blogger locks the URL to /YYYY/MM/<slug>.html at this point.
          Step 2 – Immediately PATCH the title back to `real_title`.

        Returns a dict compatible with the existing `create_post` return value,
        plus a 'custom_slug' key with the slug used.
        """
        if not self.access_token:
            # Offline / no-token mode
            return {
                "success": True,
                "mode": "OFFLINE_DRAFT",
                "id": f"draft_{int(time.time())}",
                "url": "https://www.latestjobnotifications.online/preview-draft",
                "status": "PUBLISHED",
                "custom_slug": slug_title
            }

        # --- Step 1: Publish with slug as title ---
        api_url = f"https://www.googleapis.com/blogger/v3/blogs/{self.blog_id}/posts"
        params = {"isDraft": "false"}  # Must be PUBLISHED to lock the URL
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        clean_labels = self._sanitize_labels(labels)
        payload = {
            "kind": "blogger#post",
            "title": slug_title,       # <-- slug used as title to control URL
            "content": self._sanitize_text(content),
            "labels": clean_labels,
        }

        try:
            resp = requests.post(api_url, headers=headers, params=params,
                                 json=payload, timeout=30)
            if resp.status_code == 401:
                logger.info("Token expired (401). Refreshing and retrying...")
                if self.refresh_access_token():
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    resp = requests.post(api_url, headers=headers, params=params,
                                        json=payload, timeout=30)

            if resp.status_code not in [200, 201]:
                logger.error(f"Step-1 publish failed: {resp.status_code} {resp.text}")
                return {"success": False, "error": resp.text}

            data = resp.json()
            post_id = data.get("id")
            locked_url = data.get("url", "")
            logger.info(f"Step-1 done. Post ID={post_id}, locked URL={locked_url}")

            # --- Step 2: Patch real title back ---
            time.sleep(1)  # brief pause before patching
            self.patch_post_title(post_id, real_title)

            return {
                "success": True,
                "id": post_id,
                "url": locked_url,
                "status": "PUBLISHED",
                "custom_slug": slug_title
            }
        except Exception as e:
            logger.error(f"create_post_with_custom_url exception: {e}")
            return {"success": False, "error": str(e)}

if __name__ == "__main__":
    bc = BloggerClient()
    print("Blogger client initialized. Blog ID:", bc.blog_id)
