# System Memory — Automated Blogger Job Post & Thumbnail Pipeline

## 1. Project Overview & Boundaries
- **Target Site**: [https://latestjobnotifications.online/](https://latestjobnotifications.online/) (Blogger CMS)
- **Primary Goal**: Fully automate Government Job discovery, data extraction, Master Post generation, AI Thumbnail creation (1200x675), automatic internal linking, validation, and Blogger Draft creation.
- **Android App & Apps Script Boundary**:
  - The Android push notification system is ALREADY active via `AppsScript_Code.js` reading Blogger's RSS feed (`/feeds/posts/default?alt=json`).
  - **CRITICAL**: Because publishing immediately triggers app push alerts to all users within seconds, the default mode is **SAFE REVIEW MODE (Draft Only)**. Posts are created as Blogger Drafts for Admin Review and only published upon explicit Admin Approval.

---

## 2. Core Workflow & 2-Step Publishing Pipeline
```
[1. FreeJobAlert Date-Wise Scanner]
              ↓
  [2. Click "Get Details" URL]
              ↓
[3. Extract Official Details & Official PDF/Apply Links]
              ↓
[4. Gemini AI Post Generation (Master Template + SEO Prompt)]
              ↓
[5. Gemini AI 1200x675 HD Thumbnail Generator]
              ↓
[6. Automatic Internal Linking Engine (3–6 Contextual Backlinks)]
              ↓
[7. Validation & Fact Checking Engine]
              ↓
[8. Admin Dashboard Action 1: "Approve as Blogger Draft"] ───→ [Created as DRAFT in Blogger (Safe Preview)]
              ↓
[9. Admin Dashboard Action 2: "Publish to Blogger Live"] ────→ [Post Published Live in Blogger]
                                                                        ↓
                                                         [Existing Apps Script picks RSS]
                                                                        ↓
                                                          [Instant Android App Push Alert]
```

---

## 3. Thumbnail & Placement Specifications
- **Dimensions**: 1200x675 HD (16:9 ratio).
- **Required Details**:
  1. Organization Name & Job Post Title
  2. Total Vacancies / No of Posts (e.g. `150 Posts`)
  3. Last Date to Apply (e.g. `Last Date: 05 Oct 2026`)
  4. Qualification / Govt Badge
- **HTML Placement**:
  - Injected right below the **Post Title / Intro & "About Organization" Description** section.
  - Includes **Full SEO ALT and Title tags** with high-search keywords:
    ```html
    <div class="separator" style="clear: both; text-align: center; margin: 20px 0;">
      <img src="[Thumbnail_URL]" 
           alt="[Organization Name] Recruitment 2026 Notification PDF - Apply Online for [XXX] [Post Name] Posts, Last Date [Last Date] Sarkari Naukri" 
           title="[Organization Name] Recruitment 2026 - [Post Name] [XXX] Vacancies Notification" 
           class="jp-main-thumb" 
           style="max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);" 
           loading="eager" />
    </div>
    ```
  - Binds to `<div class="job-fields" data-logo="[Thumbnail_URL]" ...>` for mobile app & homepage cards.

---

## 4. Master Post Template Rules
- **Hidden Metadata**: `<div class="job-fields" data-company="..." data-salary="..." data-posts="..." data-qualification="..." data-location="..." data-lastdate="..." data-applylink="..." data-pdflink="..." data-logo="..." data-new="yes" data-postdate="...">`
- **JSON-LD Schemas**: `JobPosting`, `FAQPage`, `BreadcrumbList`.
- **Content Sections**: Table of Contents, About Org, Job Overview Table, Important Dates, Vacancy Break-up, Eligibility (Qualification & Age), Salary, Selection Process, Application Fee, Required Documents, How to Apply, FAQs, and Important Links Grid.
- **Keywords Box**: SEO Search Keywords & Tag Cloud.
- **Disclaimer**: Government Non-Affiliation Compliance box.

---

## 5. File & Module Structure
- `config/config.py`: Global configuration, Blogger credentials, API keys, `PUBLISH_MODE = "SAFE"`.
- `config/master_prompt_v1.txt`: Exact user Master Post Template + SEO Prompt.
- `database/db.py`: SQLite database for job tracking, drafts, and cached Blogger internal link index.
- `core/scanner.py`: Date-wise FreeJobAlert scanner + detail page extractor for official links.
- `core/generator.py`: Gemini AI article generation using the Master Prompt.
- `core/thumbnail_generator.py`: 1200x675 banner generator with Gemini/Pillow.
- `core/internal_linker.py`: Semantic internal link scoring and contextual insertion.
- `core/validator.py`: Content fact-checker, HTML/Schema validator.
- `core/blogger_client.py`: Google Blogger API v3 OAuth2 client.
- `web/app.py`: Web-based Admin Dashboard with live preview, date picker, in-browser editor, and 1-click publishing.
