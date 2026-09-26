"""
Validation & Quality Control Engine for Generated Blogger Job Posts
"""
import re
import json
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class PostValidator:
    def __init__(self):
        pass

    def validate_article(self, title, html_content, job_data):
        """
        Validates the generated HTML post against quality, SEO, and anti-hallucination standards.
        Returns: (score: int, is_valid: bool, report: dict)
        """
        issues = []
        checks_passed = 0
        total_checks = 6

        # 1. Check for unreplaced template placeholders
        unreplaced = re.findall(r'\[(?:Organization Name|Post Name|XXX|Qualification|Last Date|Amount|Official Website URL)\]', html_content)
        if unreplaced:
            issues.append(f"Unreplaced template placeholders found: {set(unreplaced)}")
        else:
            checks_passed += 1

        # 2. Check for hidden metadata (<div class="job-fields">)
        soup = BeautifulSoup(html_content, "html.parser")
        job_fields = soup.find("div", class_="job-fields")
        if job_fields and job_fields.has_attr("data-company") and job_fields.has_attr("data-lastdate"):
            checks_passed += 1
        else:
            issues.append("Missing or incomplete <div class=\"job-fields\"> metadata block.")

        # 3. Check JSON-LD Schemas
        schema_scripts = soup.find_all("script", type="application/ld+json")
        has_job_posting = False
        has_faq = False
        for s in schema_scripts:
            try:
                data = json.loads(s.string or "{}")
                if data.get("@type") == "JobPosting":
                    has_job_posting = True
                if data.get("@type") == "FAQPage":
                    has_faq = True
            except Exception as e:
                issues.append(f"Malformed JSON-LD schema: {e}")

        if has_job_posting and has_faq:
            checks_passed += 1
        else:
            issues.append("Missing required JobPosting or FAQPage JSON-LD Schema.")

        # 4. Check essential sections
        essential_sections = ["#job-overview", "#important-dates", "#vacancy-details", "#eligibility-criteria", "#how-to-apply", "#important-links"]
        missing_sections = [sec for sec in essential_sections if not soup.find(id=sec.replace("#", ""))]
        if not missing_sections:
            checks_passed += 1
        else:
            issues.append(f"Missing essential article sections: {missing_sections}")

        # 5. Check Official Links Presence
        apply_link = soup.find("a", class_=lambda c: c and "jp-link-primary" in c)
        pdf_link = soup.find("a", class_=lambda c: c and "jp-link-secondary" in c)
        if apply_link or pdf_link:
            checks_passed += 1
        else:
            issues.append("Missing primary Apply Online or Official Notification CTA buttons.")

        # 6. Check Title & Word Count
        if len(title.strip()) > 15 and len(html_content.strip()) > 1500:
            checks_passed += 1
        else:
            issues.append("Article content is too brief or title is missing.")

        score = int((checks_passed / total_checks) * 100)
        is_valid = score >= 80

        report = {
            "score": score,
            "checks_passed": checks_passed,
            "total_checks": total_checks,
            "is_valid": is_valid,
            "issues": issues
        }

        return score, is_valid, report

if __name__ == "__main__":
    val = PostValidator()
    score, valid, rep = val.validate_article("Test Title", "<p>Short</p>", {})
    print(f"Validation Score: {score}, Valid: {valid}")
    print("Report:", rep)
