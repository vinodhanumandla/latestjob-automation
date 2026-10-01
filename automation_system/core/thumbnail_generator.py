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

from automation_system.config.config import (
    MEDIA_DIR, GEMINI_API_KEY, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN
)

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
        self.cf_account_id = CLOUDFLARE_ACCOUNT_ID
        self.cf_api_token = CLOUDFLARE_API_TOKEN

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
        import datetime as _dt
        year = _dt.datetime.now().year

        # Build the 3-line info text exactly as user specified:
        #   Line 1: "<Organisation> released Notification <YYYY>"
        #   Line 2: "Number of posts: <N>"
        #   Line 3: "Last date: <DD-MM-YYYY>"
        clean_org = organization.strip()
        paren_match = re.search(r'\(([^)]+)\)', organization)
        if paren_match and len(paren_match.group(1)) <= 25:
            display_org = paren_match.group(1).strip()
        else:
            display_org = clean_org[:35] + "..." if len(clean_org) > 35 else clean_org

        vac_clean = re.sub(r'[^\d]', '', str(vacancies))
        if vac_clean:
            # Format with commas for display
            try:
                vac_num = f"{int(vac_clean):,}"
            except Exception:
                vac_num = vac_clean
        else:
            vac_num = "Various"

        # Ensure last_date is in DD-MM-YYYY format
        ld_clean = last_date.strip() if last_date and last_date.lower() not in ["refer notification", ""] else ""
        # Try to normalise to DD-MM-YYYY
        if ld_clean:
            parts = re.split(r'[\-/.]', ld_clean)
            if len(parts) == 3:
                d, m, y = parts[0].zfill(2), parts[1].zfill(2), parts[2]
                if len(y) == 2:
                    y = "20" + y
                ld_clean = f"{d}-{m}-{y}"

        line1 = f"{display_org} released Notification {year}"
        line2 = f"Number of posts: {vac_num}"
        line3 = f"Last date: {ld_clean}" if ld_clean else f"Last date: Check Notification"

        clean_post = re.sub(
            r'[-\u2013\u2014]\s*\d+[\+\s\w]*POSTS?.*$', '', post_name, flags=re.IGNORECASE
        ).strip().upper()
        if len(clean_post) > 55:
            clean_post = clean_post[:52] + "..."

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
            f"MAIN TEXT (center-left, must be LARGE and perfectly readable):\n"
            f"Display the following 3 lines of text PROMINENTLY on the thumbnail in bold clear fonts:\n"
            f"  LINE 1 (very large bold white font, 68pt+): \"{line1}\"\n"
            f"  LINE 2 (large bold yellow/gold font, 48pt+): \"{line2}\"\n"
            f"  LINE 3 (large bold red font, 48pt+): \"{line3}\"\n\n"
            f"ADDITIONAL TEXT ELEMENTS:\n"
            f"- POST NAME badge: \"{clean_post}\" in medium bold white text on a dark navy rounded strip below\n"
            f"- NOTIFICATION badge: bright yellow pill button with megaphone icon + \"NOTIFICATION OUT\" text\n"
            f"- APPLY NOW button: dark navy rounded pill with \"APPLY NOW \u25ba\" in white bold\n\n"
            f"RIGHT SIDE (40% of image width) - CHARACTER ILLUSTRATION:\n"
            f"- {theme['character']}\n"
            f"- Characters realistic, friendly, confident, clearly Indian professionals\n\n"
            f"FOOTER STRIP (narrow dark strip at very bottom):\n"
            f"- Left: \"www.latestjobnotifications.online\" in white\n"
            f"- Right: \"100% VERIFIED OFFICIAL RECRUITMENT\" in gold/yellow\n\n"
            f"LOCATION: {loc_str}\n\n"
            f"MANDATORY RULES:\n"
            f"- The 3 main text lines MUST be perfectly sharp, bold, large, and clearly readable\n"
            f"- No text blur, distortion, or spelling errors\n"
            f"- English text only\n"
            f"- No watermarks or third-party logos\n"
            f"- Ultra high quality, premium professional appearance\n"
            f"- Bright vibrant colors that stand out as social media thumbnails"
        )

    def _generate_with_cloudflare_ai(
        self,
        organization: str,
        post_name: str,
        vacancies: str,
        last_date: str,
        sector: str = "uniform",
    ):
        """
        Generates realistic photo using Cloudflare Workers AI (10,000 free requests/day),
        then cleanly overlays the Modern 3-line recruitment format on top.
        """
        if not self.cf_account_id or not self.cf_api_token:
            return None

        cf_prompts = {
            "medical": (
                "Cinematic photorealistic portrait photograph of two young confident Indian doctors, "
                "male and female doctor in clean white lab coats and stethoscope smiling, warm soft professional lighting, "
                "standing on right side of frame, ultra high detail 8k, modern hospital clinic background, "
                "dark blue subtle vignette on left side"
            ),
            "defence": (
                "Cinematic photorealistic portrait photograph of a proud Indian police officer in crisp khaki official uniform, "
                "standing tall and confident, warm golden sunlight, ultra high detail 8k, headquarters background, "
                "dark navy subtle vignette on left side"
            ),
            "banker": (
                "Cinematic photorealistic portrait photograph of two Indian corporate banking executives, man and woman in elegant "
                "dark navy business suits, smiling, modern glass banking office background, 8k resolution, "
                "warm ambient lighting, dark vignette on left side"
            ),
            "teacher": (
                "Cinematic photorealistic portrait photograph of an Indian lecturer in formal attire and professor in blazer "
                "holding books and tablet, smiling warmly, modern university college campus library background, 8k resolution, "
                "soft depth of field, dark vignette on left side"
            ),
            "engineer": (
                "Cinematic photorealistic portrait photograph of an Indian civil engineer in safety vest and helmet holding a tablet, "
                "standing confidently with modern high-tech building in background, warm natural lighting, 8k resolution, "
                "dark vignette on left side"
            ),
            "uniform": (
                "Cinematic photorealistic portrait photograph of two confident Indian administrative civil service officers, "
                "man and woman in formal business attire, smiling warmly, standing on right side, modern Indian secretariat building, "
                "8k resolution, soft cinematic lighting, dark navy vignette on left side"
            ),
        }
        prompt = cf_prompts.get(sector, cf_prompts["uniform"])

        models = [
            "@cf/black-forest-labs/flux-1-schnell",
            "@cf/stabilityai/stable-diffusion-xl-base-1.0",
            "@cf/bytedance/stable-diffusion-xl-lightning",
        ]
        
        import requests as _req
        headers = {
            "Authorization": f"Bearer {self.cf_api_token}",
            "Content-Type": "application/json"
        }
        
        raw_img = None
        for m in models:
            try:
                url = f"https://api.cloudflare.com/client/v4/accounts/{self.cf_account_id}/ai/run/{m}"
                payload = {"prompt": prompt}
                resp = _req.post(url, headers=headers, json=payload, timeout=60)
                if resp.status_code == 200 and resp.content:
                    c_type = resp.headers.get("content-type", "")
                    if "application/json" in c_type:
                        try:
                            data = resp.json()
                            b64_img = data.get("result", {}).get("image", "")
                            if b64_img:
                                raw_img = base64.b64decode(b64_img)
                        except Exception as e:
                            logger.warning(f"Error decoding Cloudflare JSON: {e}")
                    elif len(resp.content) > 5000:
                        raw_img = resp.content

                    if raw_img and len(raw_img) > 5000:
                        logger.info(f"Cloudflare Workers AI generated realistic photo via {m} ({len(raw_img)} bytes)")
                        break
                else:
                    logger.warning(f"Cloudflare AI {m} returned {resp.status_code}: {resp.text[:150]}")
            except Exception as e:
                logger.warning(f"Cloudflare AI {m} error: {e}")

        if not raw_img:
            return None

        return self._composite_realistic_thumbnail(
            bg_image_bytes=raw_img,
            organization=organization,
            post_name=post_name,
            vacancies=vacancies,
            last_date=last_date,
            sector=sector,
        )

    def _composite_realistic_thumbnail(
        self,
        bg_image_bytes: bytes,
        organization: str,
        post_name: str,
        vacancies: str,
        last_date: str,
        sector: str = "uniform",
    ) -> bytes:
        """
        Takes realistic AI image, resizes to 1280x720, applies a smooth dark gradient
        fade on the left (preserving the realistic character on the right), and overlays
        the sharp, perfect, Modern 3-Line High-Quality recruitment text.
        """
        W, H = 1280, 720
        img = Image.open(io.BytesIO(bg_image_bytes)).convert("RGB")
        w, h = img.size
        if w / h > 16 / 9:
            new_w = int(h * 16 / 9)
            img = img.crop(((w - new_w) // 2, 0, (w - new_w) // 2 + new_w, h))
        elif w / h < 16 / 9:
            new_h = int(w * 9 / 16)
            img = img.crop((0, (h - new_h) // 2, w, (h - new_h) // 2 + new_h))
        img = img.resize((W, H), Image.Resampling.LANCZOS)

        # Smooth dark gradient overlay on left 65% for high-contrast readability
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d_over = ImageDraw.Draw(overlay)
        cutoff_x = int(W * 0.68)  # ~870px
        for x in range(cutoff_x):
            prog = x / cutoff_x
            alpha = int(245 * max(0.0, 1.0 - (prog ** 1.3)))
            d_over.line([(x, 0), (x, H)], fill=(8, 16, 36, alpha))

        base = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(base)

        import datetime as _dt
        year = _dt.datetime.now().year

        # Fonts
        f_badge = self._get_font("arial", 24, bold=True)
        f_btn = self._get_font("arial", 24, bold=True)
        f_footer = self._get_font("arial", 18, bold=False)

        # 1. NOTIFICATION OUT badge (Top Left)
        bw, bh = 240, 50
        draw.rounded_rectangle([(60, 48), (60 + bw, 48 + bh)], radius=12, fill="#FACC15")
        draw.text((75, 60), "NOTIFICATION OUT", fill="#0A0F1D", font=f_badge)

        # Clean display org
        clean_org = organization.strip()
        pm = re.search(r'\(([^)]+)\)', clean_org)
        if pm and len(pm.group(1)) <= 22:
            display_org = pm.group(1).strip()
        else:
            display_org = clean_org[:26] + "..." if len(clean_org) > 26 else clean_org

        # Format vacancies
        vac_clean = re.sub(r'[^\d]', '', str(vacancies))
        if vac_clean:
            try:
                vac_num_str = f"{int(vac_clean):,}"
            except Exception:
                vac_num_str = vac_clean
        else:
            vac_num_str = "Various"

        # Format last date
        ld_pil = last_date.strip() if last_date and last_date.lower() not in ["refer notification", ""] else ""
        if ld_pil:
            parts = re.split(r'[\-/.]', ld_pil)
            if len(parts) == 3:
                dp, mp, yp = parts[0].zfill(2), parts[1].zfill(2), parts[2]
                if len(yp) == 2: yp = "20" + yp
                ld_pil = f"{dp}-{mp}-{yp}"

        # Dynamic Font Size for Line 1 so it never overlaps characters on right
        l1_p1 = f"{display_org} released"
        l1_p2 = f"Notification {year}"

        f_size = 52
        f_line1 = self._get_font("impact", f_size, bold=True)
        while f_size > 34:
            bbox = draw.textbbox((0, 0), l1_p1, font=f_line1)
            if (bbox[2] - bbox[0]) < 620:
                break
            f_size -= 4
            f_line1 = self._get_font("impact", f_size, bold=True)

        f_line2 = self._get_font("impact", 48, bold=True)
        f_line3 = self._get_font("impact", 48, bold=True)

        # Draw Line 1 (Two rows, large white text with drop shadow)
        y_pos = 135
        draw.text((63, y_pos + 3), l1_p1, fill=(2, 6, 16), font=f_line1)
        draw.text((60, y_pos), l1_p1, fill="#FFFFFF", font=f_line1)
        y_pos += (f_size + 14)
        draw.text((63, y_pos + 3), l1_p2, fill=(2, 6, 16), font=f_line1)
        draw.text((60, y_pos), l1_p2, fill="#FFFFFF", font=f_line1)

        # Draw Line 2: Number of posts (Vibrant Gold)
        y_pos += 85
        text_line2 = f"Number of posts: {vac_num_str}"
        draw.text((63, y_pos + 3), text_line2, fill=(120, 53, 15), font=f_line2)
        draw.text((60, y_pos), text_line2, fill="#FBBF24", font=f_line2)

        # Draw Line 3: Last date (Vibrant Red)
        y_pos += 78
        text_line3 = f"Last date: {ld_pil}" if ld_pil else "Last date: Check Notification"
        draw.text((63, y_pos + 3), text_line3, fill=(110, 15, 15), font=f_line3)
        draw.text((60, y_pos), text_line3, fill="#EF4444", font=f_line3)

        # APPLY NOW Button below
        btn_x, btn_y, btn_w, btn_h = 60, y_pos + 90, 230, 56
        draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)], radius=28, fill="#0B1528", outline="#FFFFFF", width=3)
        draw.text((btn_x + 48, btn_y + 13), "APPLY NOW", fill="#FFFFFF", font=f_btn)

        # Footer Watermark
        draw.text((60, H - 35), "www.latestjobnotifications.online", fill=(148, 163, 184), font=f_footer)

        out = io.BytesIO()
        base.save(out, "JPEG", quality=95)
        return out.getvalue()

    def _generate_with_gemini_api(self, prompt: str):
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set.")
            return None
        import requests as _req

        # 1. Try Gemini Interactions API (official 2026 native image endpoint)
        interactions_models = [
            "gemini-3.1-flash-image",
            "nano-banana-pro-preview",
            "gemini-3-pro-image",
            "gemini-3.1-flash-lite-image",
        ]
        interactions_url = f"https://generativelanguage.googleapis.com/v1beta/interactions?key={self.api_key}"
        for model in interactions_models:
            try:
                headers = {"Content-Type": "application/json"}
                payload = {"model": model, "input": prompt}
                resp = _req.post(interactions_url, json=payload, headers=headers, timeout=90)
                if resp.status_code == 200:
                    data = resp.json()
                    # Check for output image data in interactions format
                    for out_item in data.get("outputs", []):
                        if isinstance(out_item, dict):
                            raw_b64 = out_item.get("image", {}).get("data") or out_item.get("inlineData", {}).get("data")
                            if raw_b64:
                                logger.info(f"Gemini AI thumbnail OK via Interactions API ({model})")
                                return base64.b64decode(raw_b64)
                elif resp.status_code == 429:
                    logger.warning(f"Gemini Interactions API {model}: Quota/Free Tier limit reached (429).")
                    break  # If free tier limit 0, trying next model in same family will also be 429
                elif resp.status_code == 401:
                    logger.error("Gemini API key is invalid (401).")
                    return None
            except Exception as exc:
                logger.warning(f"Interactions API {model} error: {exc}")

        # 2. Try generateContent with native image models
        candidate_models = [
            "gemini-3.1-flash-image",
            "gemini-2.5-flash-image",
            "gemini-3-pro-image",
            "gemini-3.1-flash-lite-image",
        ]
        for model in candidate_models:
            try:
                url = (
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model}:generateContent?key={self.api_key}"
                )
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "responseModalities": ["IMAGE"]
                    },
                }
                resp = _req.post(
                    url, json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=90,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for candidate in data.get("candidates", []):
                        for part in candidate.get("content", {}).get("parts", []):
                            if "inlineData" in part:
                                raw = part["inlineData"].get("data", "")
                                if raw:
                                    logger.info(f"Gemini AI thumbnail OK via generateContent ({model})")
                                    return base64.b64decode(raw)
                elif resp.status_code == 429:
                    logger.warning(f"Gemini generateContent {model}: Quota/Free Tier limit reached (429).")
                    break
                elif resp.status_code == 401:
                    logger.error("Gemini API key is invalid (401).")
                    return None
            except Exception as exc:
                logger.warning(f"Gemini generateContent {model} error: {exc}")

        logger.warning("Gemini AI image generation unavailable. Using fallback.")
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
        # 1. Bundled assets fonts (cross-platform, works on Linux/Render and Windows)
        bundled_bold = self.assets_dir / "Roboto-Bold.ttf"
        bundled_reg = self.assets_dir / "Roboto-Regular.ttf"
        if bold and bundled_bold.exists():
            try:
                return ImageFont.truetype(str(bundled_bold), size)
            except Exception:
                pass
        elif not bold and bundled_reg.exists():
            try:
                return ImageFont.truetype(str(bundled_reg), size)
            except Exception:
                pass

        # 2. Windows font candidates
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

        # 3. Linux system font candidates
        linux_fonts = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for lf in linux_fonts:
            if os.path.exists(lf):
                try:
                    return ImageFont.truetype(lf, size)
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
        """
        Sleek, high-contrast, modern recruitment thumbnail matching premium AI design:
        - Deep navy corporate gradient background
        - Clean Indian professional officers on right side
        - Yellow NOTIFICATION OUT pill badge at top-left
        - Prominent 3-line format:
            Line 1: [Company] released Notification 2026 (Large White bold)
            Line 2: Number of posts: [N] (Vibrant Gold bold)
            Line 3: Last date: [DD-MM-YYYY] (Vibrant Red bold)
        - Sleek APPLY NOW button
        - Clean footer watermark
        """
        W, H = 1280, 720
        base = Image.new("RGB", (W, H), (10, 20, 45))
        draw = ImageDraw.Draw(base)

        # 1. Background gradient: deep navy left (#081226) to richer navy right (#132247)
        for x in range(W):
            factor = x / W
            r = int(8 + factor * 11)
            g = int(18 + factor * 16)
            b = int(38 + factor * 33)
            draw.line([(x, 0), (x, H)], fill=(r, g, b))

        # Right side subtle geometric diagonal accent
        poly_pts = [(int(W * 0.55), 0), (W, 0), (W, H), (int(W * 0.45), H)]
        draw.polygon(poly_pts, fill=(16, 32, 68))

        # 2. Sector Illustrated Cutout Character on right side
        cutout_name = f"{sector}_cutout.png"
        cutout_path = self.assets_dir / cutout_name
        if not cutout_path.exists():
            cutout_path = self.assets_dir / "uniform_cutout.png"

        if cutout_path.exists():
            try:
                char = Image.open(cutout_path).convert("RGBA")
                target_h = 660
                target_w = int(char.width * (target_h / char.height))
                char_resized = char.resize((target_w, target_h), Image.Resampling.LANCZOS)
                pos_x = W - target_w + 30
                pos_y = H - target_h
                base.paste(char_resized, (pos_x, pos_y), char_resized)
            except Exception as ex:
                logger.warning(f"Cutout paste failed: {ex}")

        # 3. Typography
        draw = ImageDraw.Draw(base)
        import datetime as _dt
        year = _dt.datetime.now().year

        f_line1 = self._get_font("impact", 54, bold=True)
        f_line2 = self._get_font("impact", 50, bold=True)
        f_line3 = self._get_font("impact", 50, bold=True)
        f_badge = self._get_font("arial", 24, bold=True)
        f_btn = self._get_font("arial", 24, bold=True)
        f_footer = self._get_font("arial", 18, bold=False)

        # NOTIFICATION OUT badge (Top Left)
        bw, bh = 240, 50
        draw.rounded_rectangle([(60, 48), (60 + bw, 48 + bh)], radius=12, fill="#FACC15")
        draw.text((75, 60), "NOTIFICATION OUT", fill="#0A0F1D", font=f_badge)

        # Build 3-line text
        clean_org = organization.strip()
        pm = re.search(r'\(([^)]+)\)', clean_org)
        if pm and len(pm.group(1)) <= 22:
            display_org = pm.group(1).strip()
        else:
            display_org = clean_org[:28] + "..." if len(clean_org) > 28 else clean_org

        # Parse vacancy cleanly with commas
        vac_clean = re.sub(r'[^\d]', '', str(vacancies))
        if vac_clean:
            try:
                vac_num_str = f"{int(vac_clean):,}"
            except Exception:
                vac_num_str = vac_clean
        else:
            vac_num_str = "Various"

        # Format last date
        ld_pil = last_date.strip() if last_date and last_date.lower() not in ["refer notification", ""] else ""
        if ld_pil:
            parts = re.split(r'[\-/.]', ld_pil)
            if len(parts) == 3:
                dp, mp, yp = parts[0].zfill(2), parts[1].zfill(2), parts[2]
                if len(yp) == 2: yp = "20" + yp
                ld_pil = f"{dp}-{mp}-{yp}"

        # Draw Line 1 (Two rows for perfect readability, dynamic sizing to prevent overlap)
        l1_p1 = f"{display_org} released"
        l1_p2 = f"Notification {year}"

        f_size = 52
        f_line1 = self._get_font("impact", f_size, bold=True)
        while f_size > 34:
            bbox = draw.textbbox((0, 0), l1_p1, font=f_line1)
            if (bbox[2] - bbox[0]) < 610:
                break
            f_size -= 4
            f_line1 = self._get_font("impact", f_size, bold=True)

        y_pos = 135
        draw.text((63, y_pos + 3), l1_p1, fill=(2, 6, 16), font=f_line1)
        draw.text((60, y_pos), l1_p1, fill="#FFFFFF", font=f_line1)
        y_pos += (f_size + 14)
        draw.text((63, y_pos + 3), l1_p2, fill=(2, 6, 16), font=f_line1)
        draw.text((60, y_pos), l1_p2, fill="#FFFFFF", font=f_line1)

        # Draw Line 2: Number of posts: [N] (Gold)
        y_pos += 92
        text_line2 = f"Number of posts: {vac_num_str}"
        draw.text((63, y_pos + 3), text_line2, fill=(120, 53, 15), font=f_line2)
        draw.text((60, y_pos), text_line2, fill="#FBBF24", font=f_line2)

        # Draw Line 3: Last date: [Date] (Red)
        y_pos += 82
        text_line3 = f"Last date: {ld_pil}" if ld_pil else "Last date: Check Notification"
        draw.text((63, y_pos + 3), text_line3, fill=(110, 15, 15), font=f_line3)
        draw.text((60, y_pos), text_line3, fill="#EF4444", font=f_line3)

        # APPLY NOW Button below
        btn_x, btn_y, btn_w, btn_h = 60, y_pos + 95, 230, 58
        draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)], radius=29, fill="#0B1528", outline="#FFFFFF", width=3)
        draw.text((btn_x + 48, btn_y + 13), "APPLY NOW", fill="#FFFFFF", font=f_btn)

        # Footer Watermark
        draw.text((60, H - 35), "www.latestjobnotifications.online", fill=(148, 163, 184), font=f_footer)

        out = io.BytesIO()
        base.save(out, "JPEG", quality=95)
        return out.getvalue()

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
        Primary: Gemini AI image generation if API key has quota.
        Fallback: Ultra-clean 3-line high-contrast renderer.
        Returns: (file_path: str, filename: str)
        """
        sector = self.detect_sector(organization, post_name)
        safe_filename = (
            f"thumb_{sector}_{int(time.time())}_"
            f"{int(abs(hash(organization + post_name))) % 100000}.jpg"
        )
        file_path = self.output_dir / safe_filename
        img_bytes = None

        # 1. Try Cloudflare Workers AI first (10,000 free requests/day with FLUX.1 / SDXL)
        if self.cf_account_id and self.cf_api_token:
            logger.info(f"Cloudflare Workers AI thumbnail attempt: {organization} | {post_name}")
            img_bytes = self._generate_with_cloudflare_ai(
                organization=organization,
                post_name=post_name,
                vacancies=vacancies,
                last_date=last_date,
                sector=sector,
            )
            if img_bytes:
                logger.info(f"Cloudflare AI realistic thumbnail OK: {organization}")

        # 2. Try Gemini AI image generation (when billing is enabled)
        if not img_bytes and self.api_key:
            logger.info(f"AI thumbnail attempt: {organization} | {post_name}")
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
                logger.info(f"Gemini AI thumbnail OK: {organization}")

        # 3. Modern 3-line high-contrast renderer (always reliable)
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
