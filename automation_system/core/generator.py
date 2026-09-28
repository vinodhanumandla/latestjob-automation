"""
High-Fidelity Master Post Generator for LatestJobNotifications
Strictly conforms to the benchmark structure of latestjobnotifications.online:
1. Hidden Metadata div (<div class="job-fields">) for Android App & Homepage Cards
2. JSON-LD Schemas (JobPosting, FAQPage, BreadcrumbList)
3. SEO Intro with bold primary keywords
4. Centered Featured Image Banner with SEO ALT & Title tags
5. 12-item Table of Contents with working anchor jumps
6. About Organization Section
7. Quick Overview Table (.jp-table)
8. Important Dates Table (.jp-table)
9. Vacancy Details Table (.jp-table)
10. Eligibility Criteria (Qualification, Age Limit, Age Relaxation)
11. Salary Details (.jp-table)
12. Selection Process
13. Application Fee Table (.jp-table)
14. Required Documents for Application
15. Step-by-Step How to Apply Guide
16. 5 Comprehensive FAQs
17. Important Links Grid (.jp-links-grid): PDF, Website, WhatsApp, Android App
18. App & WhatsApp Promo Banner
19. High-Ranking Related Keywords & Blogger Labels Tag Cloud
20. Government Non-Affiliation Disclaimer & Official Sources Bar
"""
import os
import sys
import re
import json
import logging
from urllib.parse import urlparse
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from automation_system.config.config import (
    MASTER_PROMPT_PATH, ACTIVE_PROMPT_VERSION, GEMINI_API_KEY, WEBSITE_URL
)
from automation_system.core.location_detector import detect_job_location, get_state_label_for_seo

logger = logging.getLogger(__name__)

class ContentGenerator:
    def __init__(self, api_key=None):
        self.api_key = api_key or GEMINI_API_KEY

    def generate_post(self, job_data, thumbnail_url=""):
        """
        Builds a 100% complete, SEO-optimized post strictly following the benchmark format.
        """
        extracted = {}
        if job_data.get("extracted_data"):
            try:
                extracted = json.loads(job_data["extracted_data"])
            except Exception:
                pass

        org = (extracted.get("organization") or job_data.get("organization") or "Government Department").strip()
        raw_post = (extracted.get("post_name") or job_data.get("post_name") or "Various Posts").strip()
        # Clean post name by stripping trailing "- XX Posts"
        post_name = re.sub(r'[\-–—]\s*\d+[\+\s\w]*POSTS?.*$', '', raw_post, flags=re.IGNORECASE).strip()
        
        # Vacancies count
        vacancies = (extracted.get("total_vacancies") or job_data.get("total_vacancies") or "Various").strip()
        if vacancies and not re.search(r'posts?', vacancies, re.IGNORECASE):
            vac_digits = re.search(r'\d+', vacancies)
            if vac_digits:
                vacancies = f"{vac_digits.group(0)} Posts"

        advt_no = (extracted.get("advt_no") or job_data.get("notification_number") or "").strip()
        salary = (extracted.get("salary") or "").strip()
        if not salary:
            salary = "As per Government Norms / Pay Scale"

        qualification = (extracted.get("qualification") or job_data.get("qualification") or "Relevant Degree / Diploma / 10th / 12th").strip()
        age_limit = (extracted.get("age_limit") or "As per Government Rules (Refer to official notice)").strip()
        fee = (extracted.get("application_fee") or "Check official notification").strip()
        last_date = (extracted.get("last_date") or job_data.get("last_date") or "").strip()
        if not last_date or last_date.lower() in ["refer notification", "–", "-", "n/a"]:
            last_date = "Check Official Notification"
        apply_mode = (extracted.get("apply_mode") or "Online").strip()
        job_type = (extracted.get("job_type") or "Regular / Contract").strip()
        
        # Intelligently resolve specific Job Location
        detail_url = (job_data.get("notification_url") or extracted.get("detail_url") or "").strip()
        raw_text = (job_data.get("raw_content") or "").strip()
        job_location = detect_job_location(
            org=org,
            post_name=post_name,
            detail_url=detail_url,
            text_content=raw_text,
            extracted_location=extracted.get("job_location")
        )
        
        pdf_url = (extracted.get("official_pdf_url") or job_data.get("pdf_url") or "").strip()
        apply_url = (extracted.get("official_apply_url") or job_data.get("apply_url") or "").strip()
        website_url = (extracted.get("official_website_url") or job_data.get("official_website_url") or "").strip()
        post_date = job_data.get("post_date", "Today")

        # Category determination
        category = "Government Jobs"
        if any(b in org.lower() for b in ["bank", "sbi", "ibps", "idbi", "bob", "rbi", "pnb"]):
            category = "Bank Jobs"
        elif any(r in org.lower() for r in ["railway", "rrb", "rrc", "metro"]):
            category = "Railway Jobs"
        elif any(d in org.lower() for d in ["defence", "ordnance", "drdo", "iaf", "army", "navy"]):
            category = "Defence Jobs"
        elif any(m in org.lower() for m in ["medical", "health", "hospital", "doctor", "nurse"]):
            category = "Medical Jobs"
        elif "ssc" in org.lower():
            category = "SSC Jobs"
        elif "upsc" in org.lower():
            category = "UPSC Jobs"

        # Web Domain display
        web_domain = ""
        if website_url:
            try:
                parsed = urlparse(website_url)
                web_domain = parsed.netloc.replace("www.", "")
            except Exception:
                web_domain = website_url
        if not web_domain:
            web_domain = "Official Portal"

        # Clean vacancies number for title (e.g. '10' instead of '10 Posts')
        vac_count = re.sub(r'(?i)\s*posts?', '', vacancies).strip()
        
        # Target Title: "[Organization] Recruitment 2026 – Apply [Online/Offline] for [XX] [Post Name] Posts"
        clean_title = f"{org} Recruitment 2026 – Apply {apply_mode} for {vac_count} {post_name} Posts"
        search_desc = f"{org} Recruitment 2026: Apply {apply_mode.lower()} for {vacancies} {post_name} posts in {job_location}. Eligibility, salary, fee & last date {last_date}."[:155]

        # Labels (including State / Region label as per Master Prompt)
        state_label = get_state_label_for_seo(job_location)
        labels = [
            category,
            state_label,
            "Latest Jobs",
            "Government Jobs",
            f"{org} Recruitment",
            f"{post_name} Jobs 2026",
            "Sarkari Naukri 2026"
        ]

        # Format ISO Post Date
        iso_post_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+05:30")

        # Build Full HTML strictly matching benchmark
        html = self._build_benchmark_html(
            title=clean_title,
            org=org,
            post_name=post_name,
            vacancies=vacancies,
            advt_no=advt_no,
            salary=salary,
            qualification=qualification,
            age_limit=age_limit,
            fee=fee,
            last_date=last_date,
            apply_mode=apply_mode,
            job_type=job_type,
            job_location=job_location,
            pdf_url=pdf_url,
            apply_url=apply_url,
            website_url=website_url,
            web_domain=web_domain,
            post_date=post_date,
            iso_post_date=iso_post_date,
            category=category,
            thumbnail_url=thumbnail_url,
            extracted=extracted
        )

        return {
            "title": clean_title,
            "content": html,
            "labels": labels,
            "search_description": search_desc,
            "prompt_version": ACTIVE_PROMPT_VERSION
        }

    def _build_benchmark_html(self, **p):
        """Assembles the complete HTML structure strictly following master_prompt_v1.txt."""
        title = p["title"]
        org = p["org"]
        post_name = p["post_name"]
        vacancies = p["vacancies"]
        advt_no = p["advt_no"] or "Check Official Notification"
        salary = p["salary"]
        qualification = p["qualification"]
        age_limit = p["age_limit"]
        fee = p["fee"]
        last_date = p["last_date"]
        apply_mode = p["apply_mode"]
        job_type = p["job_type"]
        job_location = p["job_location"] or "All India"
        pdf_url = p["pdf_url"]
        apply_url = p["apply_url"]
        website_url = p["website_url"]
        web_domain = p["web_domain"]
        post_date = p["post_date"]
        iso_post_date = p["iso_post_date"]
        category = p["category"]
        thumb_url = p["thumbnail_url"] or "https://www.latestjobnotifications.online/favicon.ico"
        extracted = p["extracted"]

        vac_num = re.search(r'\d+', vacancies)
        vac_count_only = vac_num.group(0) if vac_num else "1"
        sal_nums = re.findall(r'\d[\d,]+', salary.replace(',', ''))
        sal_min = sal_nums[0] if sal_nums else "25000"
        sal_max = sal_nums[-1] if len(sal_nums) > 1 else sal_min

        meta_div = f'''<!--Hidden Metadata for Homepage Cards & App Feed-->
<div class="job-fields" data-applylink="{apply_url or website_url}" data-company="{org}" data-lastdate="{last_date}" data-location="{job_location}" data-logo="{thumb_url}" data-new="yes" data-pdflink="{pdf_url}" data-postdate="{iso_post_date}" data-posts="{vacancies}" data-qualification="{qualification}" data-salary="{salary}">
</div>'''

        schema_json = f'''<!--JSON-LD: JobPosting Schema-->
<script type="application/ld+json">
{{
  "@context": "https://schema.org/",
  "@type": "JobPosting",
  "title": "{post_name} Recruitment 2026",
  "description": "{org} recruitment 2026 for {vacancies} {post_name} vacancies. Educational qualification: {qualification}. Apply {apply_mode.lower()} before {last_date}.",
  "identifier": {{
    "@type": "PropertyValue",
    "name": "{org}",
    "value": "{advt_no}"
  }},
  "datePosted": "{iso_post_date[:10]}",
  "validThrough": "{last_date}",
  "employmentType": "{'CONTRACTOR' if 'contract' in job_type.lower() else 'FULL_TIME'}",
  "hiringOrganization": {{
    "@type": "Organization",
    "name": "{org}",
    "sameAs": "{website_url}"
  }},
  "jobLocation": {{
    "@type": "Place",
    "address": {{
      "@type": "PostalAddress",
      "addressLocality": "{job_location}",
      "addressCountry": "IN"
    }}
  }},
  "totalJobOpenings": "{vac_count_only}",
  "baseSalary": {{
    "@type": "MonetaryAmount",
    "currency": "INR",
    "value": {{ "@type": "QuantitativeValue", "minValue": "{sal_min}", "maxValue": "{sal_max}", "unitText": "MONTH" }}
  }}
}}
</script>
<!--JSON-LD: FAQPage Schema-->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {{"@type":"Question","name":"What is the last date to apply for {org} Recruitment 2026?","acceptedAnswer":{{"@type":"Answer","text":"The last date to apply for {org} recruitment is {last_date}."}}}},
    {{"@type":"Question","name":"How many vacancies are available in {org} Recruitment 2026?","acceptedAnswer":{{"@type":"Answer","text":"There are a total of {vacancies} vacancies announced for {post_name} posts."}}}},
    {{"@type":"Question","name":"What is the educational qualification required for {post_name}?","acceptedAnswer":{{"@type":"Answer","text":"Candidates must possess {qualification} from a recognized University or Institute."}}}},
    {{"@type":"Question","name":"What is the age limit for {org} Recruitment 2026?","acceptedAnswer":{{"@type":"Answer","text":"Age criteria: {age_limit}, with age relaxation applicable as per government norms."}}}},
    {{"@type":"Question","name":"What is the application fee for {org} Recruitment 2026?","acceptedAnswer":{{"@type":"Answer","text":"The application fee is {fee}. SC/ST/PWD candidates may be exempted as per rules."}}}},
    {{"@type":"Question","name":"How can I apply for {post_name} Recruitment 2026?","acceptedAnswer":{{"@type":"Answer","text":"Eligible candidates can apply {apply_mode.lower()} through the official portal {website_url} before the deadline {last_date}."}}}}
  ]
}}
</script>
<!--JSON-LD: BreadcrumbList Schema-->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [{{
    "@type": "ListItem",
    "position": 1,
    "name": "Home",
    "item": "https://www.latestjobnotifications.online/"
  }},{{
    "@type": "ListItem",
    "position": 2,
    "name": "{category}",
    "item": "https://www.latestjobnotifications.online/search/label/{category.replace(' ', '%20')}"
  }},{{
    "@type": "ListItem",
    "position": 3,
    "name": "{org} Recruitment 2026"
  }}]
}}
</script>'''

        intro_section = f'''<!--INTRO SECTION-->
<p class="jp-intro"><strong>{org} Recruitment 2026 Notification PDF</strong> has been officially released for <strong>{vacancies} {post_name} vacancies</strong>. Eligible candidates looking for <strong>{category} 2026</strong> or <strong>Sarkari Naukri</strong> updates can apply {apply_mode.lower()} before <strong>{last_date}</strong>. Detailed eligibility criteria, educational qualification, age limit, selection process, salary details, and direct apply link are provided below.</p>'''

        toc_section = f'''<!--TABLE OF CONTENTS-->
<div class="jp-toc">
<p class="jp-toc-title">Table of Contents</p>
<ol>
<li><a href="#organization-details">About {org}</a></li>
<li><a href="#job-overview">Job Overview 2026</a></li>
<li><a href="#important-dates">Important Dates</a></li>
<li><a href="#vacancy-details">Vacancy Break-up</a></li>
<li><a href="#eligibility-criteria">Eligibility Criteria (Age Limit &amp; Qualification)</a></li>
<li><a href="#salary">Salary Details &amp; Pay Scale</a></li>
<li><a href="#selection-process">Selection Process</a></li>
<li><a href="#application-fee">Application Fee</a></li>
<li><a href="#required-documents">Required Documents</a></li>
<li><a href="#how-to-apply">How to Apply {apply_mode}</a></li>
<li><a href="#faqs">Frequently Asked Questions (FAQs)</a></li>
<li><a href="#important-links">Official Notification PDF &amp; Apply Link</a></li>
</ol>
</div>'''

        about_section = f'''<!--ABOUT ORGANIZATION-->
<h2 class="jp-h2" id="organization-details">About {org}</h2>
<p class="jp-para">{org} is an esteemed government organization/public sector enterprise that periodically recruits eligible candidates on regular or contract basis. This <strong>{org} Recruitment 2026</strong> notification for <strong>{vacancies} {post_name}</strong> posts provides an excellent employment opportunity for candidates looking for reputable <strong>Sarkari Naukri</strong> in {job_location}. Interested and eligible candidates are encouraged to read the official notification carefully before applying.</p>'''

        thumb_section = f'''<!--THUMBNAIL BANNER-->
<div class="separator" style="clear: both; text-align: center; margin: 20px 0;">
  <a href="{thumb_url}" style="margin-left: 1em; margin-right: 1em;">
    <img src="{thumb_url}"
         alt="{org} Recruitment 2026 Notification PDF - Apply {apply_mode} for {vacancies} {post_name} Posts, Last Date {last_date} Sarkari Naukri"
         title="{org} Recruitment 2026 - {post_name} {vacancies} Vacancies Notification"
         class="jp-main-thumb"
         style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);"
         loading="eager" />
  </a>
</div>'''

        overview_table = f'''<!--JOB OVERVIEW TABLE-->
<h2 class="jp-h2" id="job-overview">{org} Recruitment 2026 – Quick Overview</h2>
<div class="jp-table-wrap">
<table class="jp-table">
<tbody>
<tr><th>Recruitment Board</th><td>{org}</td></tr>
<tr><th>Post Name</th><td>{post_name}</td></tr>
<tr><th>Advertisement No.</th><td>{advt_no}</td></tr>
<tr><th>Total Vacancies</th><td>{vacancies}</td></tr>
<tr><th>Job Category</th><td><a href="/search/label/{category.replace(' ', '%20')}" style="color: #0284c7; font-weight: 700;">{category} 2026</a> / Sarkari Naukri</td></tr>
<tr><th>Job Location</th><td>{job_location}</td></tr>
<tr><th>Job Type</th><td>{job_type}</td></tr>
<tr><th>Application Mode</th><td>{apply_mode}</td></tr>
<tr><th>Notification Date</th><td>{post_date}</td></tr>
<tr><th>Last Date to Apply</th><td><strong>{last_date}</strong></td></tr>
<tr><th>Official Website</th><td><a href="{website_url or '#'}" rel="noopener noreferrer" style="color: #0284c7; font-weight: 700;" target="_blank">{web_domain}</a></td></tr>
</tbody>
</table>
</div>'''

        dates_rows = ""
        if extracted.get("dates_breakup"):
            extracted_events = [d.get('event', '').lower() for d in extracted["dates_breakup"]]
            if not any('notification' in ev or 'release' in ev for ev in extracted_events):
                dates_rows = f"<tr><td>Notification Release Date</td><td>{post_date}</td></tr>\n"
            for d in extracted["dates_breakup"]:
                dates_rows += f"<tr><td>{d.get('event', 'Important Event')}</td><td><strong>{d.get('date', '')}</strong></td></tr>\n"
            ev_lower = [d.get('event','').lower() for d in extracted["dates_breakup"]]
            if not any('admit' in e for e in ev_lower):
                dates_rows += "<tr><td>Admit Card Release Date</td><td>To be notified soon</td></tr>\n"
            if not any('exam' in e for e in ev_lower):
                dates_rows += "<tr><td>Exam Date 2026</td><td>To be notified soon</td></tr>\n"
        else:
            dates_rows = f'''<tr><td>Notification Release Date</td><td>{post_date}</td></tr>
<tr><td>Online Application Start Date</td><td>{post_date}</td></tr>
<tr><td>Last Date to Apply Online</td><td><strong>{last_date}</strong></td></tr>
<tr><td>Last Date for Application Fee Payment</td><td>{last_date}</td></tr>
<tr><td>Admit Card Release Date</td><td>To be notified soon</td></tr>
<tr><td>Exam Date 2026</td><td>To be notified soon</td></tr>'''

        dates_section = f'''<!--IMPORTANT DATES-->
<h2 class="jp-h2" id="important-dates">Important Dates</h2>
<div class="jp-table-wrap">
<table class="jp-table">
<thead><tr><th>Event</th><th>Date</th></tr></thead>
<tbody>
{dates_rows}
</tbody>
</table>
</div>'''

        vac_rows = ""
        if extracted.get("vacancy_breakup"):
            for v in extracted["vacancy_breakup"]:
                vac_rows += f"<tr><td>{v.get('post_name', post_name)}</td><td>{v.get('vacancies', '')}</td><td>{qualification}</td></tr>\n"
            vac_rows += f'<tr class="jp-total-row"><td>Total Posts</td><td><strong>{vacancies}</strong></td><td>-</td></tr>'
        else:
            vac_rows = f'''<tr><td>{post_name}</td><td>{vacancies}</td><td>{qualification}</td></tr>
<tr class="jp-total-row"><td>Total Posts</td><td><strong>{vacancies}</strong></td><td>-</td></tr>'''

        vacancy_section = f'''<!--VACANCY DETAILS-->
<h2 class="jp-h2" id="vacancy-details">{org} Vacancy Details 2026</h2>
<p class="jp-para">The post-wise vacancy distribution for <strong>{org} Recruitment 2026</strong> is given in the table below:</p>
<div class="jp-table-wrap">
<table class="jp-table">
<thead><tr><th>Post Name</th><th>Vacancies</th><th>Educational Qualification</th></tr></thead>
<tbody>
{vac_rows}
</tbody>
</table>
</div>'''

        eligibility_section = f'''<!--ELIGIBILITY CRITERIA-->
<h2 class="jp-h2" id="eligibility-criteria">Eligibility Criteria 2026</h2>
<h3 class="jp-h3" id="qualification">Educational Qualification</h3>
<p class="jp-para">Candidates applying for <strong>{post_name}</strong> must possess <strong>{qualification}</strong> from a recognized Board or University in India. Candidates are advised to check the official notification PDF for post-wise qualification requirements.</p>
<h3 class="jp-h3" id="age-limit">Age Limit</h3>
<ul class="jp-list">
<li>{age_limit}</li>
</ul>
<h3 class="jp-h3" id="age-relaxation">Age Relaxation</h3>
<div class="jp-table-wrap">
<table class="jp-table">
<thead><tr><th>Category</th><th>Age Relaxation</th></tr></thead>
<tbody>
<tr><td>OBC (Non-Creamy Layer)</td><td>3 Years</td></tr>
<tr><td>SC / ST</td><td>5 Years</td></tr>
<tr><td>PWD Candidates</td><td>10 Years (as per govt rules)</td></tr>
</tbody>
</table>
</div>'''

        salary_section = f'''<!--SALARY DETAILS-->
<h2 class="jp-h2" id="salary">{org} Salary Details &amp; Pay Scale</h2>
<p class="jp-para">Selected candidates for <strong>{post_name}</strong> will receive monthly salary/remuneration as per government pay matrix standards:</p>
<div class="jp-table-wrap">
<table class="jp-table">
<thead><tr><th>Post Name</th><th>Pay Scale / Monthly Salary</th></tr></thead>
<tbody>
<tr><td>{post_name}</td><td><strong>{salary}</strong></td></tr>
</tbody>
</table>
</div>'''

        selection_section = f'''<!--SELECTION PROCESS-->
<h2 class="jp-h2" id="selection-process">Selection Process</h2>
<p class="jp-para">The selection process for <strong>{org} Recruitment 2026</strong> consists of the following stages:</p>
<ul class="jp-list jp-list-check">
<li>Written Test / Computer Based Examination (CBT)</li>
<li>Skill Test / Trade Test (if applicable)</li>
<li>Document Verification (DV)</li>
<li>Medical Examination</li>
</ul>'''

        fee_rows = ""
        if extracted.get("fee_breakup"):
            for f_item in extracted["fee_breakup"]:
                fee_rows += f"<tr><td>{f_item.get('category', 'Category')}</td><td>{f_item.get('fee', 'Fee')}</td></tr>\n"
        else:
            fee_lower = fee.lower()
            gen_fee = "Nil" if "nil" in fee_lower or "no fee" in fee_lower or not fee.strip() else fee
            sc_fee = "Nil"
            fee_rows = f'''<tr><td>General / OBC / EWS</td><td>{gen_fee}</td></tr>
<tr><td>SC / ST / PWD / Female</td><td>{sc_fee}</td></tr>'''
        fee_rows += "\n<tr><td>Payment Mode</td><td>Online via Net Banking, Debit Card, Credit Card, or UPI</td></tr>"

        fee_section = f'''<!--APPLICATION FEE-->
<h2 class="jp-h2" id="application-fee">Application Fee</h2>
<div class="jp-table-wrap">
<table class="jp-table">
<thead><tr><th>Category</th><th>Application Fee</th></tr></thead>
<tbody>
{fee_rows}
</tbody>
</table>
</div>'''

        docs_section = '''<!--REQUIRED DOCUMENTS-->
<h2 class="jp-h2" id="required-documents">Required Documents for Application</h2>
<ul class="jp-list">
<li>Recent Passport Size Photograph</li>
<li>Scanned Copy of Signature</li>
<li>Educational Certificates &amp; Marksheets</li>
<li>Age Proof Certificate (10th Class Certificate / Aadhaar Card)</li>
<li>Caste Certificate (if applicable)</li>
<li>Valid Email ID and Mobile Number</li>
</ul>'''

        if "offline" in apply_mode.lower():
            apply_steps = f'''<ol class="jp-steps">
<li>Visit the official website: <strong>{web_domain}</strong> ({website_url})</li>
<li>Download the official notification PDF and read instructions carefully.</li>
<li>Download the application form from the official website or notification PDF.</li>
<li>Fill out the application form with accurate personal, educational, and category details.</li>
<li>Attach self-attested photocopies of all required educational and ID certificates.</li>
<li>Send the completed application by Speed Post / Registered Post to the address given in the notification.</li>
<li>Ensure the application arrives on or before the last date: <strong>{last_date}</strong>.</li>
<li>Retain a copy of the filled application for future reference.</li>
</ol>'''
        else:
            apply_steps = f'''<ol class="jp-steps">
<li>Visit the official website: <strong>{web_domain}</strong> ({website_url})</li>
<li>Click on the <strong>Recruitment / Careers</strong> section on the home page.</li>
<li>Select <strong>{post_name} Recruitment 2026 Notification</strong> link.</li>
<li>Read the instructions carefully and click on <strong>New Registration</strong>.</li>
<li>Fill in your basic details, educational qualifications, and upload required documents.</li>
<li>Pay the application fee online through the payment gateway.</li>
<li>Verify all details before submitting and take a printout of the submitted application form.</li>
</ol>'''

        how_to_apply_section = f'''<!--HOW TO APPLY-->
<h2 class="jp-h2" id="how-to-apply">How to Apply {apply_mode} for {org} Recruitment 2026</h2>
{apply_steps}'''

        faqs_section = f'''<!--FAQs-->
<h2 class="jp-h2" id="faqs">Frequently Asked Questions (FAQs)</h2>
<div class="jp-faq">
<div class="jp-faq-item">
<p class="jp-faq-q">Q1. What is the last date to apply for {org} Recruitment 2026?</p>
<p class="jp-faq-a">Ans: The last date to apply {apply_mode.lower()} is <strong>{last_date}</strong>.</p>
</div>
<div class="jp-faq-item">
<p class="jp-faq-q">Q2. How many total vacancies are announced?</p>
<p class="jp-faq-a">Ans: A total of <strong>{vacancies}</strong> have been announced for {post_name} posts.</p>
</div>
<div class="jp-faq-item">
<p class="jp-faq-q">Q3. What is the required educational qualification?</p>
<p class="jp-faq-a">Ans: Candidates must possess <strong>{qualification}</strong> from a recognized Board/University.</p>
</div>
<div class="jp-faq-item">
<p class="jp-faq-q">Q4. Where can I download the official notification PDF?</p>
<p class="jp-faq-a">Ans: You can download the official notification PDF using the direct link provided below in the Important Links section.</p>
</div>
<div class="jp-faq-item">
<p class="jp-faq-q">Q5. What is the age limit for {org} Recruitment 2026?</p>
<p class="jp-faq-a">Ans: Age criteria: <strong>{age_limit}</strong>, with government reservations for reserved categories.</p>
</div>
<div class="jp-faq-item">
<p class="jp-faq-q">Q6. What is the salary for {post_name} posts?</p>
<p class="jp-faq-a">Ans: The pay scale / stipend is <strong>{salary}</strong>.</p>
</div>
</div>'''

        apply_box_html = ""
        if apply_url:
            apply_box_html = f'''<a class="jp-link-box jp-link-primary" href="{apply_url}" rel="nofollow noopener" target="_blank">
<span class="jp-link-title">Apply Online Form</span>
<span class="jp-link-cta">Click Here →</span>
</a>'''

        links_grid = f'''<!--IMPORTANT LINKS GRID-->
<h2 class="jp-h2" id="important-links">Important Links &amp; Direct Apply Links</h2>
<div class="jp-links-grid">
{apply_box_html}
<a class="jp-link-box jp-link-secondary" href="{pdf_url or '#'}" rel="nofollow noopener" target="_blank">
<span class="jp-link-title">Download Official Notification PDF</span>
<span class="jp-link-cta">Click Here →</span>
</a>
<a class="jp-link-box jp-link-info" href="{website_url or '#'}" rel="noopener noreferrer" target="_blank">
<span class="jp-link-title">Official Website Portal</span>
<span class="jp-link-cta">Click Here →</span>
</a>
<a class="jp-link-box jp-link-success" href="https://whatsapp.com/channel/0029VbDOYwH96H4JTb8uoi1u" rel="nofollow noopener" target="_blank">
<span class="jp-link-title">💬 Join WhatsApp Channel</span>
<span class="jp-link-cta">Join Now →</span>
</a>
</div>
<p class="jp-para" style="color: #64748b; font-size: 13px;"><em>Note: Please refer to the official notification PDF linked above for comprehensive instructions and annexures before submitting your application.</em></p>'''

        promo_box = '''<!--PROMO BANNER FOR APP & WHATSAPP-->
<div class="jp-app-promo-box" style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border: 1px solid #334155; border-radius: 14px; padding: 16px 20px; margin: 24px 0; color: #ffffff; font-family: sans-serif;">
<div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
<div>
<h4 style="margin: 0 0 4px 0; font-size: 15px; font-weight: 700; color: #38bdf8;">📲 Get Daily Instant Job Alerts On Your Phone</h4>
<p style="margin: 0; font-size: 12px; color: #94a3b8;">Never miss a government job update. Install our official Android App or join our WhatsApp Channel.</p>
</div>
<div style="display: flex; gap: 8px; flex-wrap: wrap;">
<a href="https://play.google.com/store/apps/details?id=com.latestjobnotifications.app" target="_blank" rel="noopener" style="background: #0284c7; color: #ffffff; font-weight: 700; font-size: 12px; padding: 8px 14px; border-radius: 8px; text-decoration: none; display: inline-block;">📱 Get Android App</a>
<a href="https://whatsapp.com/channel/0029VbDOYwH96H4JTb8uoi1u" target="_blank" rel="nofollow noopener" style="background: #25d366; color: #ffffff; font-weight: 700; font-size: 12px; padding: 8px 14px; border-radius: 8px; text-decoration: none; display: inline-block;">💬 Join WhatsApp</a>
</div>
</div>
</div>'''

        keywords_box = f'''<!--HIGH-RANKING SEO SEARCH KEYWORDS & BLOGGER LABELS TAG CLOUD-->
<div class="jp-post-keywords-box" style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 16px; margin: 20px 0; font-family: sans-serif;">
<div style="font-size: 13px; font-weight: 700; color: #0f172a; margin-bottom: 10px; display: flex; align-items: center; gap: 6px;">
<span>🏷️</span> <span>Explore Related Job Categories &amp; Search Keywords</span>
</div>
<div style="display: flex; flex-wrap: wrap; gap: 8px;">
<a href="/search/label/Government%20Jobs" style="background:#e0f2fe; color:#0369a1; font-size:11px; font-weight:600; padding:5px 12px; border-radius:20px; text-decoration:none;">Sarkari Naukri 2026</a>
<a href="/search/label/Government%20Jobs" style="background:#e0f2fe; color:#0369a1; font-size:11px; font-weight:600; padding:5px 12px; border-radius:20px; text-decoration:none;">Government Jobs 2026</a>
<a href="/search/label/{category.replace(' ', '%20')}" style="background:#e0f2fe; color:#0369a1; font-size:11px; font-weight:600; padding:5px 12px; border-radius:20px; text-decoration:none;">{category} 2026</a>
<a href="/search/label/Bank%20Jobs" style="background:#e0f2fe; color:#0369a1; font-size:11px; font-weight:600; padding:5px 12px; border-radius:20px; text-decoration:none;">Bank Jobs 2026</a>
<a href="/search/label/Railway%20Jobs" style="background:#e0f2fe; color:#0369a1; font-size:11px; font-weight:600; padding:5px 12px; border-radius:20px; text-decoration:none;">Railway Recruitment 2026</a>
<a href="/search/label/SSC%20Jobs" style="background:#e0f2fe; color:#0369a1; font-size:11px; font-weight:600; padding:5px 12px; border-radius:20px; text-decoration:none;">SSC Jobs 2026</a>
<a href="/search/label/10th%20Pass%20Jobs" style="background:#e0f2fe; color:#0369a1; font-size:11px; font-weight:600; padding:5px 12px; border-radius:20px; text-decoration:none;">10th Pass Govt Jobs</a>
<a href="/search/label/Degree%20Jobs" style="background:#e0f2fe; color:#0369a1; font-size:11px; font-weight:600; padding:5px 12px; border-radius:20px; text-decoration:none;">Degree Pass Jobs</a>
<a href="/search/label/AP%20Jobs" style="background:#e0f2fe; color:#0369a1; font-size:11px; font-weight:600; padding:5px 12px; border-radius:20px; text-decoration:none;">AP Govt Jobs</a>
<a href="/search/label/Telangana%20Jobs" style="background:#e0f2fe; color:#0369a1; font-size:11px; font-weight:600; padding:5px 12px; border-radius:20px; text-decoration:none;">Telangana Jobs</a>
<a href="https://play.google.com/store/apps/details?id=com.latestjobnotifications.app" target="_blank" rel="noopener" style="background:#0284c7; color:#ffffff; font-size:11px; font-weight:700; padding:5px 12px; border-radius:20px; text-decoration:none;">📱 Latest Job App</a>
</div>
</div>'''

        disclaimer_box = f'''<!--COMPLIANCE & NON-AFFILIATION DISCLAIMER-->
<div class="jp-disclaimer">
<strong>⚠️ Government Non-Affiliation Disclaimer:</strong> The information provided above is collected from publicly available official government portals (<strong>{web_domain}</strong>). Latest Job Notifications is an independent job portal and is <strong>NOT affiliated with, endorsed by, or representing any government entity</strong>. Candidates are strongly advised to verify all details on the official portal before submitting applications.
</div>'''

        official_source_bar = ''  # Removed per user request


        full_html = f'''{meta_div}
{schema_json}
<article class="jp-wrap">
{intro_section}
{thumb_section}
{toc_section}
{about_section}
{overview_table}
{dates_section}
{vacancy_section}
{eligibility_section}
{salary_section}
{selection_section}
{fee_section}
{docs_section}
{how_to_apply_section}
{faqs_section}
{links_grid}
{promo_box}
{keywords_box}
{disclaimer_box}
{official_source_bar}
</article>'''

        return full_html

if __name__ == "__main__":
    cg = ContentGenerator()
    sample_job = {
        "organization": "Ordnance Factory Dehu Road",
        "post_name": "Graduate/Diploma Project Engineer",
        "total_vacancies": "10 Posts",
        "last_date": "23-09-2026",
        "qualification": "B.E/B.Tech or Diploma in Chemical/Mechanical Engineering",
        "pdf_url": "https://img2.freejobalert.com/news/2026/09/4125878-6a9b99c57d54b38514675.pdf",
        "official_website_url": "https://munitionsindia.in",
        "extracted_data": json.dumps({
            "organization": "Ordnance Factory Dehu Road",
            "post_name": "Graduate/Diploma Project Engineer",
            "total_vacancies": "10 Posts",
            "advt_no": "1914/02/OFDR/Tenure Based/Project Engineer / 2026",
            "salary": "1st Year Rs. 36000/-, 2nd Year Rs. 37080/-, 3rd Year Rs. 38192/-, 4th Year Rs. 39338/-",
            "qualification": "B.E/B.Tech or Diploma in Chemical/Mechanical Engineering, B.Sc Graduate with Chemistry",
            "age_limit": "Max 30 years for General Category. 5 years relaxation for SC/ST, 3 years for OBC-NCL.",
            "application_fee": "Nil",
            "last_date": "23-09-2026",
            "apply_mode": "Offline",
            "job_type": "Contract",
            "job_location": "Dehu Road, Pune, Maharashtra",
            "official_pdf_url": "https://img2.freejobalert.com/news/2026/09/4125878-6a9b99c57d54b38514675.pdf",
            "official_website_url": "https://munitionsindia.in/"
        })
    }
    res = cg.generate_post(sample_job, thumbnail_url="https://example.com/test-thumb.jpg")
    print("Generated Title:", res["title"])
    print("Content Length:", len(res["content"]))
