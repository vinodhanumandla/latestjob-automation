"""
FreeJobAlert Date-Wise Notification Scanner & Deep Detail Extractor
Extracts exact Vacancies, Post Names, Advt No, Salary, Fees, Dates & Official Links.
"""
import requests
from bs4 import BeautifulSoup
import re
import json
import logging
from urllib.parse import urljoin
from datetime import datetime, timedelta
import pytz

from automation_system.config.config import FREEJOBALERT_LATEST_URL, REQUEST_HEADERS, TIMEZONE
from automation_system.database.db import get_db_connection, get_current_ist_time
from automation_system.core.location_detector import detect_job_location

logger = logging.getLogger(__name__)

class JobScanner:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)

    def get_latest_notifications(self, filter_date=None, max_days=3):
        """
        Scrapes https://www.freejobalert.com/latest-notifications/
        Extracts:
        - col 0: Post Date
        - col 1: Recruitment Board / Organization
        - col 2: Exam / Post Name (and parses exact Vacancies)
        - col 3: Qualification
        - col 4: Advt No
        - col 5: Last Date
        - col 6: Detail URL
        
        If filter_date is None, scans recent dates (Today, Yesterday, Day Before Yesterday).
        """
        try:
            resp = self.session.get(FREEJOBALERT_LATEST_URL, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch FreeJobAlert latest notifications: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        notifications = []
        seen_dates = set()

        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all(["td", "th"])
                if len(cols) < 6:
                    continue
                
                col_texts = [col.get_text(" ", strip=True) for col in cols]
                
                # Skip header rows
                if "Post Date" in col_texts[0] or "Recruitment Board" in col_texts[1]:
                    continue

                post_date_raw = col_texts[0].strip()
                recruitment_board = col_texts[1].strip()
                raw_post_name = col_texts[2].strip()
                qualification = col_texts[3].strip()
                advt_no = col_texts[4].strip() if len(col_texts) > 4 else ""
                last_date = col_texts[5].strip() if len(col_texts) > 5 else ""

                # Extract Detail URL from the last column or row link
                link_tag = cols[-1].find("a", href=True) or row.find("a", href=True)
                if not link_tag or not link_tag.get("href"):
                    continue

                detail_url = urljoin(FREEJOBALERT_LATEST_URL, link_tag["href"])

                # Extract exact Vacancies from Post Name column if present
                # e.g. "Part Time Doctor - 1 Posts" or "Wealth Executive - 1100 Posts"
                vacancies = ""
                post_name = raw_post_name
                vac_match = re.search(r'[\-–—]\s*(\d+[\+\s\w]*Posts?)', raw_post_name, re.IGNORECASE)
                if vac_match:
                    vacancies = vac_match.group(1).strip()
                    # Clean post name by removing the trailing "- XX Posts"
                    post_name = re.sub(r'[\-–—]\s*\d+[\+\s\w]*Posts?.*$', '', raw_post_name).strip()

                # Date Filtering
                if filter_date:
                    clean_filter = filter_date.strip().replace("/", "-")
                    clean_post_date = post_date_raw.strip().replace("/", "-")

                    filter_variants = [clean_filter]
                    parts = clean_filter.split("-")
                    if len(parts) == 3:
                        if len(parts[0]) == 4:  # YYYY-MM-DD from calendar -> DD-MM-YYYY
                            filter_variants.append(f"{parts[2]}-{parts[1]}-{parts[0]}")
                            filter_variants.append(f"{parts[2]}/{parts[1]}/{parts[0]}")
                        elif len(parts[2]) == 4:  # DD-MM-YYYY -> YYYY-MM-DD
                            filter_variants.append(f"{parts[2]}-{parts[1]}-{parts[0]}")
                            filter_variants.append(f"{parts[0]}/{parts[1]}/{parts[2]}")

                    matched = any(
                        v in clean_post_date or v in post_date_raw.strip()
                        for v in filter_variants
                    )
                    if not matched:
                        continue
                else:
                    # Multi-day scan: track distinct dates up to max_days (e.g. today, yesterday, day before)
                    clean_date = post_date_raw.replace("/", "-").strip()
                    if len(seen_dates) >= max_days and clean_date not in seen_dates:
                        # Stop if we went past the recent N days
                        continue
                    seen_dates.add(clean_date)

                item = {
                    "post_date": post_date_raw,
                    "organization": recruitment_board,
                    "post_name": post_name,
                    "raw_post_name": raw_post_name,
                    "qualification": qualification,
                    "total_vacancies": vacancies,
                    "advt_no": advt_no if advt_no != "–" else "",
                    "last_date": last_date,
                    "detail_url": detail_url
                }
                notifications.append(item)

        logger.info(f"Discovered {len(notifications)} notifications across dates: {list(seen_dates)}")
        return notifications

    def extract_deep_job_details(self, detail_url):
        """
        Fetches the FreeJobAlert [Get Details] page and extracts all structured tables:
        - Organization / Company Name
        - Post Name
        - No of Posts / Total Vacancies
        - Advt No
        - Salary / Pay Scale / Stipend
        - Qualification
        - Age Limit & Age Relaxation
        - Application Fee (General, OBC, SC, ST)
        - Last Date & Important Dates Breakup
        - Vacancy Breakup by Post
        - Official Links: Notification PDF, Apply Online, Official Website
        """
        try:
            resp = self.session.get(detail_url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch detail page {detail_url}: {e}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table")

        data = {
            "detail_url": detail_url,
            "title": soup.title.string.strip() if soup.title else "",
            "organization": "",
            "post_name": "",
            "total_vacancies": "",
            "advt_no": "",
            "salary": "",
            "qualification": "",
            "age_limit": "",
            "application_fee": "",
            "last_date": "",
            "apply_mode": "",
            "job_type": "",
            "job_location": "",
            "official_pdf_url": "",
            "official_apply_url": "",
            "official_website_url": "",
            "vacancy_breakup": [],
            "dates_breakup": [],
            "fee_breakup": []
        }

        # Parse each table on the detail page
        for t_idx, table in enumerate(tables):
            rows = table.find_all("tr")
            for tr in rows:
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
                links = tr.find_all("a", href=True)

                # 1. Key-Value Rows (Table 0 Overview or similar)
                if len(cells) == 2:
                    k = cells[0].strip().lower().replace(":", "").replace(".", "")
                    v = cells[1].strip()

                    if any(term in k for term in ["company", "organization", "board"]) and not data["organization"]:
                        data["organization"] = v
                    elif any(term in k for term in ["post name", "exam name"]) and not data["post_name"]:
                        data["post_name"] = v
                    elif any(term in k for term in ["no of post", "total post", "vacanc"]) and not data["total_vacancies"]:
                        data["total_vacancies"] = v
                    elif "advt" in k and not data["advt_no"]:
                        data["advt_no"] = v
                    elif any(term in k for term in ["salary", "pay scale", "stipend", "remuneration"]) and not data["salary"]:
                        data["salary"] = v
                    elif "qualification" in k and not data["qualification"]:
                        data["qualification"] = v
                    elif "age limit" in k and not data["age_limit"]:
                        data["age_limit"] = v
                    elif any(term in k for term in ["application fee", "fee"]) and not data["application_fee"]:
                        data["application_fee"] = v
                    elif "last date" in k and not data["last_date"]:
                        data["last_date"] = v
                    elif any(term in k for term in ["apply mode", "mode of application"]) and not data["apply_mode"]:
                        data["apply_mode"] = v
                    elif "job type" in k and not data["job_type"]:
                        data["job_type"] = v
                    elif any(term in k for term in ["location", "place of work", "posting", "work location", "place of posting", "station", "job place"]) and not data["job_location"]:
                        data["job_location"] = v

                # 2. Check for Links Table
                if links and len(cells) >= 2:
                    desc = cells[0].lower()
                    for a in links:
                        href = a["href"].strip()
                        # Must be a full absolute URL (http/https), not a relative FreeJobAlert path
                        if not href.startswith("http"):
                            continue
                        if "freejobalert.com" in href and not href.endswith(".pdf"):
                            continue
                        if any(term in desc for term in ["notification", "advt", "circular", "notice"]) or href.endswith(".pdf"):
                            if not data["official_pdf_url"]:
                                data["official_pdf_url"] = href
                        elif any(term in desc for term in ["apply online", "apply here", "registration", "online form"]):
                            if not data["official_apply_url"]:
                                data["official_apply_url"] = href
                        elif any(term in desc for term in ["official website", "official portal", "portal", "website"]):
                            if not data["official_website_url"]:
                                data["official_website_url"] = href

                # 3. Vacancy Breakup Rows (broad post type detection)
                VACANCY_KEYWORDS = [
                    "engineer", "officer", "clerk", "assistant", "manager", "doctor",
                    "trainee", "apprentice", "constable", "supervisor", "inspector",
                    "nurse", "technician", "teacher", "lecturer", "professor",
                    "accountant", "auditor", "analyst", "executive", "fellow",
                    "scientist", "researcher", "steno", "driver", "guard",
                    "peon", "head", "director", "chairman", "deputy", "junior",
                    "senior", "specialist", "coordinator", "associate"
                ]
                if len(cells) == 2 and any(term in cells[0].lower() for term in VACANCY_KEYWORDS):
                    # Only add if looks like a valid number or range in second cell
                    vac_val = cells[1].strip()
                    if vac_val and re.search(r'\d+', vac_val):
                        data["vacancy_breakup"].append({"post_name": cells[0], "vacancies": vac_val})

                # 4. Dates Breakup Rows — normalize event names for display
                DATE_KEYWORDS = ["start date", "last date", "notification date", "notification release",
                                  "exam date", "interview", "application begin", "apply online", "closing date"]
                if len(cells) == 2 and any(term in cells[0].lower() for term in DATE_KEYWORDS):
                    event_label = cells[0].strip()
                    date_val = cells[1].strip()
                    # Skip empty dates
                    if not date_val:
                        pass
                    else:
                        # Normalize "Last Date" to "Last Date to Apply"
                        if "last date" in event_label.lower() and "apply" not in event_label.lower():
                            event_label = "Last Date to Apply"
                        # Deduplicate: don't add same event twice
                        existing_events = [d["event"] for d in data["dates_breakup"]]
                        if event_label not in existing_events:
                            data["dates_breakup"].append({"event": event_label, "date": date_val})

                # 5. Fee Breakup Rows — only add if fee value looks like a real fee amount
                FEE_KEYWORDS = ["general", "obc", "sc/st", "sc ", "st ", "pwd", "female", "all other", "ex-servicemen", "all candidate"]
                if len(cells) == 2 and any(term in cells[0].lower() for term in FEE_KEYWORDS):
                    fee_val = cells[1].strip()
                    # Only add if fee value looks like money (Rs, INR, number) or Nil/No fee
                    if fee_val and (re.search(r'rs\.?\s*\d+|\d+\.?\d*\s*/-|nil|no fee|\d+ \d+', fee_val.lower()) or fee_val.lower() in ["nil", "no fee", "free", "exempt"]):
                        data["fee_breakup"].append({"category": cells[0].strip(), "fee": fee_val})

                # 5b. Single-cell fee detection (e.g. "Application Fee: Nil")
                if len(cells) >= 2:
                    k_lower = cells[0].lower()
                    if any(term in k_lower for term in ["application fee", "exam fee", "registration fee"]) and not data["application_fee"]:
                        fee_val = cells[1].strip()
                        data["application_fee"] = fee_val if fee_val else "Nil"
                    # Detect standalone "No Application Fee" or "Nil" in full-row context
                    full_text = " ".join(cells).lower()
                    if "no application fee" in full_text or ("nil" in full_text and "fee" in full_text):
                        if not data["application_fee"]:
                            data["application_fee"] = "Nil"

        # Fallback: Search all anchors for PDF / Official Website if not found in table
        if not data["official_pdf_url"] or not data["official_website_url"] or not data["official_apply_url"]:
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                txt = a.get_text(strip=True).lower()
                # Only absolute http/https URLs
                if not href.startswith("http"):
                    continue
                if "freejobalert" in href and not href.endswith(".pdf"):
                    continue
                if not data["official_pdf_url"] and (href.endswith(".pdf") or "notification" in txt):
                    data["official_pdf_url"] = href
                elif not data["official_website_url"] and any(term in txt for term in ["official website", "website", "portal"]):
                    data["official_website_url"] = href
                elif not data["official_apply_url"] and any(term in txt for term in ["apply online", "click here to apply"]):
                    data["official_apply_url"] = href

        # Normalize total vacancies string (e.g. if digit, add "Posts")
        if data["total_vacancies"]:
            clean_digits = re.search(r'\d+', data["total_vacancies"])
            if clean_digits and "post" not in data["total_vacancies"].lower():
                data["total_vacancies"] = f"{clean_digits.group(0)} Posts"

        # Intelligently detect Job Location if missing or generic
        if not data["job_location"] or data["job_location"].lower() in ["all india", "across india", "india"]:
            detected_loc = detect_job_location(
                org=data["organization"],
                post_name=data["post_name"],
                detail_url=detail_url,
                text_content=soup.get_text(" ", strip=True)[:3000],
                extracted_location=data["job_location"]
            )
            data["job_location"] = detected_loc

        return data

    def sync_and_save_job(self, notification_summary):
        """
        Extracts deep details from FreeJobAlert and stores/updates into the SQLite database.
        Returns job_id and status.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        detail_url = notification_summary["detail_url"]

        # Check for existing job
        cursor.execute("SELECT id, status FROM jobs WHERE notification_url = ?", (detail_url,))
        existing = cursor.fetchone()

        # Fetch deep details
        deep_details = self.extract_deep_job_details(detail_url)
        if not deep_details:
            if existing:
                conn.close()
                return existing["id"], "DUPLICATE"
            conn.close()
            return None, "EXTRACTION_FAILED"

        # Merge summary data with deep extracted data
        org = deep_details.get("organization") or notification_summary.get("organization", "")
        post_name = deep_details.get("post_name") or notification_summary.get("post_name", "")
        vacancies = deep_details.get("total_vacancies") or notification_summary.get("total_vacancies", "")
        advt_no = deep_details.get("advt_no") or notification_summary.get("advt_no", "")
        last_date = deep_details.get("last_date") or notification_summary.get("last_date", "")
        qualification = deep_details.get("qualification") or notification_summary.get("qualification", "")
        pdf_url = deep_details.get("official_pdf_url") or ""
        apply_url = deep_details.get("official_apply_url") or ""
        website_url = deep_details.get("official_website_url") or ""

        now_time = get_current_ist_time()

        if existing:
            # Update existing record with the clean deep details
            cursor.execute("""
            UPDATE jobs SET
                organization = ?, post_name = ?, total_vacancies = ?, notification_number = ?,
                qualification = ?, last_date = ?, pdf_url = ?, apply_url = ?, official_website_url = ?,
                extracted_data = ?, updated_at = ?
            WHERE id = ?
            """, (
                org, post_name, vacancies, advt_no, qualification, last_date,
                pdf_url, apply_url, website_url, json.dumps(deep_details), now_time, existing["id"]
            ))
            conn.commit()
            conn.close()
            return existing["id"], "DUPLICATE"

        # Insert new record
        cursor.execute("""
        INSERT INTO jobs (
            source_name, source_url, notification_url, pdf_url, apply_url, official_website_url,
            post_date, notification_number, organization, post_name, total_vacancies, qualification, last_date,
            raw_content, extracted_data, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DISCOVERED', ?, ?)
        """, (
            "FreeJobAlert",
            FREEJOBALERT_LATEST_URL,
            detail_url,
            pdf_url,
            apply_url,
            website_url,
            notification_summary.get("post_date", ""),
            advt_no,
            org,
            post_name,
            vacancies,
            qualification,
            last_date,
            soup_snippet(deep_details),
            json.dumps(deep_details),
            now_time,
            now_time
        ))

        job_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return job_id, "DISCOVERED"

def soup_snippet(details):
    """Formats details into a clean summary snippet for AI prompt."""
    lines = [
        f"Organization: {details.get('organization')}",
        f"Post Name: {details.get('post_name')}",
        f"Total Vacancies: {details.get('total_vacancies')}",
        f"Advt No: {details.get('advt_no')}",
        f"Salary/Pay Scale: {details.get('salary')}",
        f"Qualification: {details.get('qualification')}",
        f"Age Limit: {details.get('age_limit')}",
        f"Application Fee: {details.get('application_fee')}",
        f"Last Date: {details.get('last_date')}",
        f"Apply Mode: {details.get('apply_mode')}",
        f"Job Type: {details.get('job_type')}",
        f"Job Location: {details.get('job_location')}",
        f"Official PDF Link: {details.get('official_pdf_url')}",
        f"Official Apply Link: {details.get('official_apply_url')}",
        f"Official Website: {details.get('official_website_url')}"
    ]
    return "\n".join(lines)

if __name__ == "__main__":
    scanner = JobScanner()
    print("Scanning FreeJobAlert...")
    notifs = scanner.get_latest_notifications()
    print(f"Found {len(notifs)} notifications.")
    if notifs:
        print("First notification sample:", notifs[0])
