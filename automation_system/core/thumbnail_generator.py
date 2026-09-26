"""
AI-Powered Professional Job Thumbnail Generator for LatestJobNotifications
Uses Google Gemini Image Generation API as primary engine.
Fallback to enhanced PIL rendering if AI unavailable.

Reference style: Delhi High Court / OFDR thumbnails
- Illustrated Indian professional characters
- Bold org name + RECRUITMENT 2026 in gold
- Circular vacancy badge + LAST DATE + APPLY NOW button
- Sector-specific background gradients and icons
"""
import os
import sys
import re
import time
import base64
import logging
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from automation_system.config.config import MEDIA_DIR, GEMINI_API_KEY

logger = logging.getLogger(__name__)
ASSETS_DIR = BASE_DIR / "automation_system" / "media" / "assets"

SECTOR_THEMES = {
    "medical": {
        "character": "Indian male and female doctors in white lab coats and stethoscopes, smiling confidently",
        "bg_colors": "deep teal blue (#0b3954) to vibrant cyan (#06b6d4) gradient left to right",
        "icons": "medical cross symbol, hospital building, stethoscope, heartbeat line as decorative background elements",
        "badge_color": "red #dc2626",
    },
    "defence": {
        "character": "Indian male army officer in olive/khaki uniform with rank badge and beret, standing tall and confident",
        "bg_colors": "deep navy blue (#1e293b) to amber gold (#f59e0b) gradient",
        "icons": "five-pointed star badge, shield emblem, Indian flag tricolor accents, military insignia as decorative background elements",
        "badge_color": "amber #d97706",
    },
    "engineer": {
        "character": "Indian male and female engineers in orange safety vests and yellow hard hats, holding blueprints and tablets, smiling",
        "bg_colors": "light sky blue (#dbeafe) background with dark navy blue header bar at top",
        "icons": "gear cogs, technical blueprint grid, industrial factory building silhouette, wrench and gear as decorative background elements",
        "badge_color": "orange #ea580c",
    },
    "banker": {
        "character": "Indian male and female professionals in formal dark business suits, holding documents and briefcase, smiling",
        "bg_colors": "deep navy blue (#1e1b4b) to light blue (#bfdbfe) gradient",
        "icons": "Indian Rupee symbol, bank building with columns, upward bar chart, calculator as decorative background elements",
        "badge_color": "blue #2563eb",
    },
    "teacher": {
        "character": "Indian female teacher in blue saree holding textbooks, and male teacher in formal shirt, both smiling and giving thumbs up",
        "bg_colors": "light blue (#e0f2fe) to white gradient with dark navy header bar",
        "icons": "open books, graduation mortarboard cap, university building, academic scroll as decorative background elements",
        "badge_color": "emerald green #059669",
    },
    "uniform": {
        "character": "Indian male and female government officers in smart formal navy uniform with ID badge, standing confident and smiling",
        "bg_colors": "dark navy blue (#0f2b5c) to gold (#f59e0b) gradient",
        "icons": "Indian government Ashoka Lion Capital emblem, official seal, Indian national flag, laurel wreath as decorative background elements",
        "badge_color": "red #dc2626",
    },
}

PIL_THEMES = {
    "medical":  {"header_bg": "#0b3954", "header_accent": "#06b6d4", "vac_color": "#dc2626"},
    "defence":  {"header_bg": "#1e293b", "header_accent": "#f59e0b", "vac_color": "#d97706"},
    "engineer": {"header_bg": "#0f172a", "header_accent": "#ea580c", "vac_color": "#ea580c"},
    "banker":   {"header_bg": "#1e1b4b", "header_accent": "#38bdf8", "vac_color": "#2563eb"},
    "teacher":  {"header_bg": "#1e293b", "header_accent": "#10b981", "vac_color": "#059669"},
    "uniform":  {"header_bg": "#0f2b5c", "header_accent": "#f59e0b", "vac_color": "#dc2626"},
}


class ThumbnailGenerator:
    def __init__(self):
        self.output_dir = MEDIA_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir = ASSETS_DIR
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.api_key = GEMINI_API_KEY

    def detect_sector(self, org: str, post: str) -> str:
        text = (org + " " + post).lower()

        def has_any(keywords):
            for k in keywords:
                if len(k) <= 3:
                    if re.search(rf'\b{re.escape(k)}\b', text):
                        return True
                else:
                    if k in text:
                        return True
            return False

        if has_any(["medical", "health", "hospital", "doctor", "nurse", "resident", "pharmacist",
                    "aiims", "esic", "ayush", "mbbs", "dental", "veterinary", "paramedical",
                    "clinical", "mo", "gdmo"]):
            return "medical"
        if has_any(["police", "defence", "army", "navy", "air force", "sainik", "constable",
                    "sub inspector", "si", "cisf", "crpf", "bsf", "itbp", "ssb", "assam rifles",
                    "coast guard", "security", "jail"]):
            return "defence"
        if has_any(["bank", "sbi", "ibps", "rbi", "nabard", "sidbi", "bob", "pnb", "canara",
                    "union bank", "clerk", "po", "probationary", "manager", "accountant",
                    "finance", "audit", "tax", "treasury", "credit analyst", "wealth"]):
            return "banker"
        if has_any(["teacher", "professor", "lecturer", "school", "faculty", "kvs", "nvs",
                    "education", "university", "college", "tutor", "tgt", "pgt", "prt", "b.ed",
                    "tet", "dsc", "ugc", "fellowship", "research fellow", "jrf", "srf",
                    "project associate", "scholar", "iit", "nit", "iim"]):
            return "teacher"
        if has_any(["engineer", "technician", "b.tech", "diploma", "isro", "drdo",
                    "project engineer", "apprentice", "factory", "ordnance", "ntpc",
                    "iocl", "ongc", "sail", "bhel", "hal", "bel", "pwd", "cpwd", "mining"]):
            return "engineer"
        return "uniform"

    def _build_ai_prompt(
        self,
        organization: str,
        post_name: str,
        vacancies: str,
        last_date: str,
        qualification: str,
        location: str,
        sector: str,
    ) -> str:
        theme = SECTOR_THEMES.get(sector, SECTOR_THEMES["uniform"])
        clean_org = organization.strip().upper()
        paren_match = re.search(r'\(([^)]+)\)', organization)
        if paren_match and len(paren_match.group(1)) <= 22:
            short_org = paren_match.group(1).upper()
        else:
            short_org = clean_org[:30] + "..." if len(clean_org) > 30 else clean_org
        clean_post = re.sub(
            r'[-\u2013\u2014]\s*\d+[\+\s\w]*POSTS?.*$', '', post_name, flags=re.IGNORECASE
        ).strip().upper()
        if len(clean_post) > 55:
            clean_post = clean_post[:52] + "..."
        vac_digits = re.search(r'\d+', str(vacancies))
        vac_num = vac_digits.group(0) if vac_digits else "VARIOUS"
        qual_short = qualification[:55] if qualification else "10th / 12th / Graduation"
        loc_str = location.upper() if location else "ALL INDIA"

        return (
            f"Create a professional, eye-catching 1280x720 pixel (16:9 widescreen) job recruitment "
            f"banner thumbnail for an Indian government job notification website called "
            f"LatestJobNotifications.online.\n\n"
            f"VISUAL STYLE: Modern flat semi-realistic illustration style. Bold vibrant typography. "
            f"Similar to high-quality Indian government job notification YouTube banner thumbnails. "
            f"Clean, professional, premium look.\n\n"
            f"BACKGROUND:\n"
            f"- {theme['bg_colors']}\n"
            f"- Subtle decorative: {theme['icons']}\n\n"
            f"LEFT SIDE (55-60% of image width) - TEXT CONTENT AREA:\n"
            f"1. ORGANIZATION NAME: \"{short_org}\" in very large (72pt+) bold white Impact/Arial Black font at top\n"
            f"2. YELLOW BANNER: \"RECRUITMENT 2026\" text in large bold gold/amber font on a dark navy horizontal strip\n"
            f"3. POST NAME: \"{clean_post}\" in large bold (40pt+) dark or white text below\n"
            f"4. NOTIFICATION BADGE: Bright yellow rounded rectangle with megaphone icon + \"NOTIFICATION OUT\" text in red\n"
            f"5. VACANCY CIRCLE: Large dark navy circle with thick {theme['badge_color']} outline ring, "
            f"containing \"{vac_num}\" number in huge bold white font, and \"POSTS\" text below it\n"
            f"6. DATE INFO: Calendar icon + \"LAST DATE: {last_date}\" in bold dark text on white/cream rounded background\n"
            f"7. APPLY BUTTON: Dark navy blue rounded rectangle pill button with \"APPLY NOW \u25ba\" in white bold text\n\n"
            f"RIGHT SIDE (40-45% of image width) - CHARACTER ILLUSTRATION:\n"
            f"- {theme['character']}\n"
            f"- Characters realistic, friendly, confident, clearly Indian professionals\n"
            f"- Circular frame or placed naturally against the themed background\n\n"
            f"SMALL QUALIFICATION TEXT (bottom left, small readable font):\n"
            f"Qualification: {qual_short} | Location: {loc_str}\n\n"
            f"FOOTER STRIP (narrow dark strip at very bottom edge):\n"
            f"- Left: globe icon + \"www.latestjobnotifications.online\" in white\n"
            f"- Right: \"100% VERIFIED OFFICIAL RECRUITMENT\" in gold/yellow\n\n"
            f"MANDATORY RULES:\n"
            f"- ALL TEXT must be perfectly sharp, clear, readable - zero blur or distortion\n"
            f"- English text only, no spelling errors\n"
            f"- No watermarks or third-party logos\n"
            f"- Ultra high quality, premium professional appearance\n"
            f"- Bright vibrant colors that stand out as social media thumbnails\n"
            f"- Characters look like realistic Indian professionals, not cartoons"
        )

    def _generate_with_gemini_api(self, prompt: str):
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set. Skipping AI thumbnail generation.")
            return None
        import requests
        candidate_models = [
            "gemini-2.5-flash-image",
            "gemini-3.1-flash-image-preview",
            "gemini-3.1-flash-image",
            "gemini-3-pro-image-preview",
        ]
        for model in candidate_models:
            try:
                url = (
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model}:generateContent?key={self.api_key}"
                )
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
                }
                resp = requests.post(
                    url, json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=90,
                )
                if resp.status_code == 200:
                    for candidate in resp.json().get("candidates", []):
                        for part in candidate.get("content", {}).get("parts", []):
                            if "inlineData" in part:
                                raw = part["inlineData"].get("data", "")
                                if raw:
                                    logger.info(f"Successfully generated thumbnail using {model}!")
                                    return base64.b64decode(raw)
                    logger.warning(f"Gemini {model} returned no image data.")
                else:
                    logger.warning(f"Gemini {model} returned {resp.status_code}: {resp.text[:200]}")
            except Exception as exc:
                logger.warning(f"Gemini AI thumbnail error on {model}: {exc}")
        return None

    def _resize_to_1280x720(self, img_bytes: bytes) -> bytes:
        try:
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            w, h = img.size
            if w / h > 16 / 9:
                new_w = int(h * 16 / 9)
                img = img.crop(((w - new_w) // 2, 0, (w - new_w) // 2 + new_w, h))
            elif w / h < 16 / 9:
                new_h = int(w * 9 / 16)
                img = img.crop((0, (h - new_h) // 2, w, (h - new_h) // 2 + new_h))
            img = img.resize((1280, 720), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            img.save(out, "JPEG", quality=95)
            return out.getvalue()
        except Exception as exc:
            logger.warning(f"Resize failed: {exc}")
            return img_bytes

    def upload_to_public_host(self, local_path: str) -> str:
        """
        Uploads generated thumbnail to public CDN (freeimage.host)
        so Blogger dashboard can display the thumbnail image.
        """
        try:
            import requests
            with open(local_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")
            resp = requests.post(
                "https://freeimage.host/api/1/upload",
                data={
                    "key": "6d207e02198a847aa98d0a2a901485a5",
                    "action": "upload",
                    "source": b64_data,
                    "format": "json",
                },
                timeout=20,
            )
            if resp.status_code == 200:
                img_url = resp.json().get("image", {}).get("url")
                if img_url:
                    logger.info(f"Thumbnail CDN URL: {img_url}")
                    return img_url
        except Exception as exc:
            logger.warning(f"CDN upload failed: {exc}")
        return ""

    # â”€â”€ PIL Fallback Renderer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _get_font(self, name: str, size: int, bold: bool = True):
        candidates = [
            f"c:/windows/fonts/{name}bd.ttf" if bold else f"c:/windows/fonts/{name}.ttf",
            f"c:/windows/fonts/{name}.ttf",
            "c:/windows/fonts/arialbd.ttf" if bold else "c:/windows/fonts/arial.ttf",
            "c:/windows/fonts/arial.ttf",
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    return ImageFont.truetype(c, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def _draw_globe(self, draw, x, y, size=18, color="#ffffff"):
        r = size // 2
        cx, cy = x + r, y + r
        draw.ellipse([(x, y), (x + size, y + size)], outline=color, width=2)
        draw.ellipse([(cx - r // 2, y), (cx + r // 2, y + size)], outline=color, width=1)
        draw.line([(x, cy), (x + size, cy)], fill=color, width=1)

    def _draw_doc(self, draw, x, y, w=14, h=18, color="#ffffff"):
        draw.rectangle([(x, y), (x + w, y + h)], outline=color, width=2)
        draw.line([(x + 3, y + 5), (x + w - 3, y + 5)], fill=color, width=1)
        draw.line([(x + 3, y + 9), (x + w - 3, y + 9)], fill=color, width=1)

    def _draw_download(self, draw, x, y, w=16, h=18, color="#ffffff"):
        cx = x + w // 2
        draw.line([(cx, y + 2), (cx, y + 12)], fill=color, width=2)
        draw.polygon([(cx - 4, y + 8), (cx + 4, y + 8), (cx, y + 13)], fill=color)
        draw.line([(x + 2, y + 15), (x + w - 2, y + 15)], fill=color, width=2)

    def _generate_pil_fallback(
        self,
        organization: str,
        post_name: str,
        vacancies: str,
        last_date: str,
        qualification: str = "",
        location: str = "",
        salary: str = "",
        age_limit: str = "",
        sector: str = "uniform",
    ) -> bytes:
        W, H = 1280, 720
        base = Image.new("RGBA", (W, H), (250, 252, 255, 255))

        # 1. Diagonal Navy Blue Gradient Wave
        poly_pts = []
        for x in range(W + 1):
            prog = x / W
            y_wave = 520 - 130 * (prog ** 0.8)
            poly_pts.append((x, int(y_wave)))
        poly_pts = [(0, 0), (W, 0), (W, poly_pts[-1][1])] + list(reversed(poly_pts))

        navy_grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d_grad = ImageDraw.Draw(navy_grad)
        for y in range(540):
            factor = y / 540.0
            r = int(8 + factor * 14)
            g = int(24 + factor * 36)
            b = int(60 + factor * 76)
            d_grad.line([(0, y), (W, y)], fill=(r, g, b, 255))

        wave_mask = Image.new("L", (W, H), 0)
        d_mask = ImageDraw.Draw(wave_mask)
        d_mask.polygon(poly_pts, fill=255)
        base.paste(navy_grad, (0, 0), wave_mask)

        # Golden accent divider line
        d_base = ImageDraw.Draw(base)
        curve_pts = []
        for x in range(0, W + 1, 4):
            prog = x / W
            y_wave = 520 - 130 * (prog ** 0.8)
            curve_pts.append((x, int(y_wave)))
        for i in range(len(curve_pts) - 1):
            d_base.line([curve_pts[i], curve_pts[i+1]], fill=(245, 158, 11, 235), width=4)

        # 2. Sector Illustrated Cutout Character
        cutout_name = f"{sector}_cutout.png"
        cutout_path = self.assets_dir / cutout_name
        if not cutout_path.exists():
            cutout_path = self.assets_dir / "uniform_cutout.png"

        if cutout_path.exists():
            try:
                char = Image.open(cutout_path).convert("RGBA")
                target_h = 670
                target_w = int(char.width * (target_h / char.height))
                char_resized = char.resize((target_w, target_h), Image.Resampling.LANCZOS)
                pos_x = W - target_w + 30
                pos_y = H - target_h - 5
                base.paste(char_resized, (pos_x, pos_y), char_resized)
            except Exception as ex:
                logger.warning(f"Cutout paste failed: {ex}")

        # 3. Typography (Left Side)
        draw = ImageDraw.Draw(base)
        f_org = self._get_font("impact", 62)
        f_rec = self._get_font("impact", 52)
        f_post = self._get_font("arial", 28, bold=True)
        f_badge = self._get_font("impact", 24)
        f_dates_lbl = self._get_font("arial", 20, bold=True)
        f_date_val = self._get_font("impact", 28)
        f_btn = self._get_font("arial", 20, bold=True)
        f_card_vac = self._get_font("impact", 50)
        f_card_sub = self._get_font("arial", 20, bold=True)

        # Organization Name
        clean_org = organization.strip().upper()
        pm = re.search(r'\(([^)]+)\)', clean_org)
        if pm and len(pm.group(1)) <= 18:
            short_org = pm.group(1).upper()
        else:
            short_org = clean_org[:32] + "..." if len(clean_org) > 32 else clean_org

        draw.text((43, 43), short_org, fill=(4, 11, 26), font=f_org)
        draw.text((40, 40), short_org, fill="#ffffff", font=f_org)

        # RECRUITMENT 2026
        draw.text((43, 118), "RECRUITMENT 2026", fill=(146, 64, 14), font=f_rec)
        draw.text((40, 115), "RECRUITMENT 2026", fill="#fbbf24", font=f_rec)

        # Post Name
        clean_post = re.sub(r'[-\u2013\u2014]\s*\d+[\+\s\w]*POSTS?.*$', '', post_name, flags=re.IGNORECASE).strip().upper()
        if len(clean_post) > 36:
            words = clean_post.split(" ")
            line1, line2 = "", ""
            for w in words:
                if len(line1 + " " + w) <= 32:
                    line1 = (line1 + " " + w).strip()
                else:
                    line2 = (line2 + " " + w).strip()
            post_lines = [line1, line2] if line2 else [line1]
        else:
            post_lines = [clean_post]

        py = 190
        for pline in post_lines:
            if pline:
                draw.text((42, py + 2), pline, fill=(4, 11, 26), font=f_post)
                draw.text((40, py), pline, fill="#ffffff", font=f_post)
                py += 38

        # Yellow Notification Badge
        badge_y = py + 12
        draw.rounded_rectangle([(40, badge_y), (320, badge_y + 44)], radius=8, fill="#facc15", outline="#eab308", width=2)
        draw.text((56, badge_y + 8), "📢 NOTIFICATION OUT", fill="#0f172a", font=f_badge)

        # 4. Bottom-Left Dates & Action Button
        draw.text((40, 540), "IMPORTANT DATES:", fill="#334155", font=f_dates_lbl)
        draw.rounded_rectangle([(40, 572), (390, 624)], radius=10, fill="#fef3c7", outline="#f59e0b", width=2)
        draw.text((54, 580), f"LAST DATE: {last_date.upper()}", fill="#991b1b", font=f_date_val)

        draw.rounded_rectangle([(40, 640), (220, 688)], radius=22, fill="#0f172a", outline="#3b82f6", width=2)
        draw.text((68, 652), "APPLY NOW >>", fill="#ffffff", font=f_btn)

        # 5. Floating Vacancies Card on Bottom Right
        card_w, card_h = 420, 120
        card_x = W - card_w - 40
        card_y = H - card_h - 25

        draw.rounded_rectangle([(card_x + 5, card_y + 5), (card_x + card_w + 5, card_y + card_h + 5)], radius=16, fill=(0, 0, 0, 40))
        draw.rounded_rectangle([(card_x, card_y), (card_x + card_w, card_y + card_h)], radius=16, fill="#ffffff", outline="#0f172a", width=3)

        vn = re.search(r'\d+', str(vacancies))
        vac_count = f"{vn.group(0)} VACANCIES" if vn else "MULTIPLE VACANCIES"
        draw.text((card_x + 30, card_y + 12), vac_count, fill="#0f172a", font=f_card_vac)

        sub_info = f"QUALIFICATION: {qualification[:24]}" if qualification else f"LOCATION: {location[:24]}"
        draw.text((card_x + 32, card_y + 72), sub_info.upper(), fill="#1d4ed8", font=f_card_sub)

        out = io.BytesIO()
        base.convert("RGB").save(out, "JPEG", quality=95)
        return out.getvalue()

    # â”€â”€ Main Entry Point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def generate_hd_thumbnail(
        self,
        organization: str,
        post_name: str,
        vacancies: str,
        last_date: str,
        qualification: str = "",
        location: str = "",
        salary: str = "",
        age_limit: str = "",
    ):
        """
        Generates a 1280x720 professional thumbnail.
        Primary: Gemini AI image generation (Delhi High Court illustrated style).
        Fallback: Enhanced PIL rendering if AI unavailable.
        Returns: (file_path: str, filename: str)
        """
        sector = self.detect_sector(organization, post_name)
        safe_filename = (
            f"thumb_{sector}_{int(time.time())}_"
            f"{int(abs(hash(organization + post_name))) % 100000}.jpg"
        )
        file_path = self.output_dir / safe_filename
        img_bytes = None

        # Try Gemini AI image generation first
        if self.api_key:
            logger.info(f"AI thumbnail: {organization} | {post_name}")
            prompt = self._build_ai_prompt(
                organization=organization,
                post_name=post_name,
                vacancies=vacancies,
                last_date=last_date,
                qualification=qualification,
                location=location,
                sector=sector,
            )
            img_bytes = self._generate_with_gemini_api(prompt)
            if img_bytes:
                img_bytes = self._resize_to_1280x720(img_bytes)
                logger.info(f"AI thumbnail OK: {organization}")
            else:
                logger.warning("AI generation failed; using PIL fallback.")

        # PIL fallback if AI unavailable or failed
        if not img_bytes:
            img_bytes = self._generate_pil_fallback(
                organization=organization,
                post_name=post_name,
                vacancies=vacancies,
                last_date=last_date,
                qualification=qualification,
                location=location,
                salary=salary,
                age_limit=age_limit,
                sector=sector,
            )

        with open(file_path, "wb") as fobj:
            fobj.write(img_bytes)
        logger.info(f"Saved thumbnail: {file_path}")
        return str(file_path), safe_filename


if __name__ == "__main__":
    tg = ThumbnailGenerator()
    path, name = tg.generate_hd_thumbnail(
        organization="Delhi High Court",
        post_name="Senior Personal Assistant (SPA) and Personal Assistant (PA)",
        vacancies="150",
        last_date="05-10-2026",
        qualification="Graduate with Typing Speed 45 WPM",
        location="Delhi",
        salary="Rs.47,600 - Rs.1,51,100 per month",
        age_limit="18 - 27 Years",
    )
    print("Generated:", path)
