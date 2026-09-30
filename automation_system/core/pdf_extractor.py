"""
PDF Notification Data Extractor
Downloads the official notification PDF and extracts structured data.
"""
import re, logging, io, requests

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36"}

MONTH_MAP = {"jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06",
             "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12"}

POST_KW = ["engineer","officer","clerk","assistant","manager","doctor","nurse","technician",
           "teacher","inspector","constable","supervisor","accountant","analyst","executive",
           "trainee","apprentice","scientist","steno","driver","guard","director","junior","senior","specialist"]


def _normalize_date(raw: str) -> str:
    raw = raw.strip()
    m = re.match(r'^(\d{1,2})[\-/\.](\d{1,2})[\-/\.](\d{2,4})$', raw)
    if m:
        d, mo, y = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        if len(y) == 2: y = "20" + y
        return f"{d}-{mo}-{y}"
    m2 = re.match(r'^(\d{1,2})\s+([a-z]+)\.?\s+(\d{4})$', raw, re.IGNORECASE)
    if m2:
        d = m2.group(1).zfill(2)
        mo = MONTH_MAP.get(m2.group(2).lower()[:3], "??")
        return f"{d}-{mo}-{m2.group(3)}"
    return raw


def extract_pdf_data(pdf_url: str) -> dict:
    """Downloads PDF and returns all extracted structured data."""
    result = {
        "total_vacancies": "", "salary": "", "application_fee": "",
        "fee_breakup": [], "last_date": "", "dates_breakup": [],
        "qualification": "", "age_limit": "", "apply_mode": "",
        "job_type": "", "advt_no": "", "vacancy_breakup": [],
        "official_website_url": "", "official_apply_url": "",
    }
    if not pdf_url or not pdf_url.startswith("http"):
        return result
    try:
        resp = requests.get(pdf_url, headers=HEADERS, timeout=25)
        if resp.status_code != 200:
            logger.warning(f"PDF download failed {pdf_url}: {resp.status_code}")
            return result
        pdf_bytes = resp.content
    except Exception as e:
        logger.warning(f"PDF fetch error: {e}")
        return result
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:10]:
                pt = page.extract_text()
                if pt:
                    text += pt + "\n"
    except Exception as e:
        logger.warning(f"pdfplumber error: {e}")
        return result
    if not text.strip():
        logger.warning("PDF had no extractable text (scanned image PDF)")
        return result
    logger.info(f"PDF: extracted {len(text)} chars from {pdf_url}")
    _parse(text, result)
    return result


def _parse(text: str, r: dict):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    tl = text.lower()

    # 1. Advt No
    for p in [r"advt\.?\s*no\.?\s*[:\-]?\s*([A-Za-z0-9\-/\.]{4,40})",
              r"notification\s+no\.?\s*[:\-]?\s*([A-Za-z0-9\-/\.]{4,40})",
              r"advertisement\s+no\.?\s*[:\-]?\s*([A-Za-z0-9\-/\.]{4,40})"]:
        m = re.search(p, text, re.IGNORECASE)
        if m: r["advt_no"] = m.group(1).strip(); break

    # 2. Total Vacancies
    for p in [r"total\s+(?:no\.?\s+of\s+)?(?:posts?|vacancies?)\s*[:\-]?\s*(\d[\d,]*)",
              r"(?:no\.?\s+of\s+)?(?:posts?|vacancies?)\s*[:\-]\s*(\d[\d,]*)",
              r"(\d[\d,]*)\s+(?:posts?|vacancies?)"]:
        m = re.search(p, text, re.IGNORECASE)
        if m: r["total_vacancies"] = m.group(1).replace(",","") + " Posts"; break

    # 3. Post-wise Vacancy Breakup
    breakup = []
    for line in lines:
        for pat in [r"^(.{5,60}?)\s{2,}(\d+)\s*(?:posts?)?$",
                    r"^(.{5,60}?)\s*[\-\u2013]\s*(\d+)\s*(?:posts?)?$"]:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                pp, cnt = m.group(1).strip(), m.group(2)
                if any(k in pp.lower() for k in POST_KW) and 0 < int(cnt) < 10000:
                    if not any(b["post_name"] == pp for b in breakup):
                        breakup.append({"post_name": pp, "vacancies": cnt})
    if breakup: r["vacancy_breakup"] = breakup[:20]

    # 4. Salary
    m = re.search(r"(?:pay\s+scale|salary|pay\s+band|stipend|remuneration|pay\s+matrix)\s*[:\-]?\s*([^\n]{10,120})", text, re.IGNORECASE)
    if m: r["salary"] = re.sub(r"\s+", " ", m.group(1).strip()[:120])

    # 5. Fee
    fm = re.search(r"(?:application\s+fee|exam\s+fee|registration\s+fee)[^\n]{0,200}", text, re.IGNORECASE | re.DOTALL)
    if fm:
        fb = fm.group(0)[:400]
        if re.search(r"\bnil\b|no\s+fee|free", fb, re.IGNORECASE):
            r["application_fee"] = "Nil"
            r["fee_breakup"] = [{"category": "All Candidates", "fee": "Nil"}]
        else:
            ams = re.findall(r"(?:rs\.?\s*|inr\s*)?(\d[\d,]+)\s*(?:/-|/)?", fb, re.IGNORECASE)
            if ams: r["application_fee"] = f"Rs. {ams[0]}"
            rows = []
            for pat, lbl in [(r"(?:general|gen|ur)\s*[:\-]?\s*(?:rs\.?\s*)?(\d[\d,]+)", "General"),
                             (r"obc\s*[:\-]?\s*(?:rs\.?\s*)?(\d[\d,]+)", "OBC"),
                             (r"(?:sc|st|sc/st)\s*[:\-]?\s*(?:rs\.?\s*)?(\d[\d,]+)", "SC / ST"),
                             (r"(?:pwd|ews)\s*[:\-]?\s*(?:rs\.?\s*)?(\d[\d,]+)", "PWD / EWS")]:
                fm2 = re.search(pat, fb, re.IGNORECASE)
                if fm2: rows.append({"category": lbl, "fee": f"Rs. {fm2.group(1)}"})
            if rows: r["fee_breakup"] = rows

    # 6. Dates
    date_re = r"(\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4}|\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{4})"
    label_map = [
        (r"(?:start|begin|opening)\s*(?:date|of\s+application)", "Application Start Date"),
        (r"(?:last|closing|end)\s*date\s*(?:to\s+apply|for\s+application)?", "Last Date to Apply"),
        (r"(?:last\s+date\s+for|last\s+date\s+to)\s*(?:pay|payment|fee)", "Last Date for Fee Payment"),
        (r"exam(?:ination)?\s+date|written\s+test", "Exam Date"),
        (r"admit\s+card|hall\s+ticket", "Admit Card Date"),
    ]
    dates_found = []
    for lp, ln in label_map:
        combined = re.compile(lp + r"[^\n]{0,60}?" + date_re, re.IGNORECASE)
        m = combined.search(text)
        if m:
            ds = _normalize_date(m.group(m.lastindex))
            if ds and not any(d["event"] == ln for d in dates_found):
                dates_found.append({"event": ln, "date": ds})
    if dates_found:
        r["dates_breakup"] = dates_found
        for d in dates_found:
            if "last" in d["event"].lower() and "apply" in d["event"].lower():
                r["last_date"] = d["date"]; break
        if not r["last_date"]: r["last_date"] = dates_found[-1]["date"]
    if not r["last_date"]:
        m = re.search(r"last\s+date\s*[:\-]?\s*(\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4})", text, re.IGNORECASE)
        if m: r["last_date"] = _normalize_date(m.group(1))

    # 7. Qualification
    m = re.search(r"(?:educational\s+)?qualification\s*[:\-]?\s*([^\n]{15,200})", text, re.IGNORECASE)
    if m: r["qualification"] = re.sub(r"\s+", " ", m.group(1).strip()[:200])

    # 8. Age Limit
    m = re.search(r"age\s+limit\s*[:\-]?\s*([^\n]{10,150})", text, re.IGNORECASE)
    if m: r["age_limit"] = re.sub(r"\s+", " ", m.group(1).strip()[:150])

    # 9. Apply Mode
    if "online" in tl: r["apply_mode"] = "Online"
    if re.search(r"\boffline\b|\bpost\b|\bhand\s+deliver", tl): r["apply_mode"] = "Offline"

    # 10. URLs from PDF
    for url in re.findall(r"https?://[^\s<>\"\']{5,80}", text):
        if "freejobalert" not in url and "google" not in url:
            if not r["official_website_url"]: r["official_website_url"] = url
            if "apply" in url.lower() or "register" in url.lower():
                r["official_apply_url"] = url; break
