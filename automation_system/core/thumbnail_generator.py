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

        # 3. Typography (Left Side) — 3-line format
        draw = ImageDraw.Draw(base)
        import datetime as _dt
        year = _dt.datetime.now().year

        f_line1 = self._get_font("impact", 52)   # Line 1: Org released Notification YYYY
        f_line2 = self._get_font("impact", 42)   # Line 2: Number of posts: N
        f_line3 = self._get_font("impact", 42)   # Line 3: Last date: DD-MM-YYYY
        f_post = self._get_font("arial", 24, bold=True)
        f_badge = self._get_font("impact", 22)
        f_btn = self._get_font("arial", 20, bold=True)
        f_card_vac = self._get_font("impact", 46)
        f_card_sub = self._get_font("arial", 18, bold=True)

        # Build 3-line text
        clean_org = organization.strip()
        pm = re.search(r'\(([^)]+)\)', clean_org)
        if pm and len(pm.group(1)) <= 20:
            display_org = pm.group(1).strip()
        else:
            display_org = clean_org[:30] + "..." if len(clean_org) > 30 else clean_org

        vn_d = re.search(r'\d+', str(vacancies))
        vac_num_str = vn_d.group(0) if vn_d else "Various"

        ld_pil = last_date.strip() if last_date and last_date.lower() not in ["refer notification", ""] else ""
        if ld_pil:
            parts = re.split(r'[\-/.]', ld_pil)
            if len(parts) == 3:
                dp, mp, yp = parts[0].zfill(2), parts[1].zfill(2), parts[2]
                if len(yp) == 2: yp = "20" + yp
                ld_pil = f"{dp}-{mp}-{yp}"

        text_line1 = f"{display_org} released Notification {year}"
        text_line2 = f"Number of posts: {vac_num_str}"
        text_line3 = f"Last date: {ld_pil}" if ld_pil else "Last date: Check Notification"

        # Draw Line 1 — white bold
        draw.text((43, 43), text_line1, fill=(4, 11, 26), font=f_line1)  # shadow
        draw.text((40, 40), text_line1, fill="#ffffff", font=f_line1)

        # Draw Line 2 — gold/yellow
        draw.text((43, 108), text_line2, fill=(146, 64, 14), font=f_line2)  # shadow
        draw.text((40, 105), text_line2, fill="#fbbf24", font=f_line2)

        # Draw Line 3 — red
        draw.text((43, 165), text_line3, fill=(100, 0, 0), font=f_line3)  # shadow
        draw.text((40, 162), text_line3, fill="#dc2626", font=f_line3)

        # Post Name below
        clean_post = re.sub(r'[-\u2013\u2014]\s*\d+[\+\s\w]*POSTS?.*$', '', post_name, flags=re.IGNORECASE).strip().upper()
        if len(clean_post) > 36:
            words = clean_post.split(" ")
            post_l1, post_l2 = "", ""
            for w in words:
                if len(post_l1 + " " + w) <= 32:
                    post_l1 = (post_l1 + " " + w).strip()
                else:
                    post_l2 = (post_l2 + " " + w).strip()
            post_lines = [post_l1, post_l2] if post_l2 else [post_l1]
        else:
            post_lines = [clean_post]

        py = 220
        for pline in post_lines:
            if pline:
                draw.text((42, py + 2), pline, fill=(4, 11, 26), font=f_post)
                draw.text((40, py), pline, fill="#ffffff", font=f_post)
                py += 36

        # Notification Badge
        badge_y = py + 12
        draw.rounded_rectangle([(40, badge_y), (320, badge_y + 40)], radius=8, fill="#facc15", outline="#eab308", width=2)
        draw.text((56, badge_y + 6), "NOTIFICATION OUT", fill="#0f172a", font=f_badge)

        # Apply Now Button
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
                logger.warning("Gemini AI failed; trying Pollinations.ai...")
                img_bytes = self._generate_with_pollinations(
                    organization=organization,
                    post_name=post_name,
                    vacancies=vacancies,
                    last_date=last_date,
                    sector=sector,
                )
                if img_bytes:
                    img_bytes = self._resize_to_1280x720(img_bytes)
                    logger.info(f"Pollinations.ai thumbnail OK: {organization}")

        # Also try Pollinations if no api_key at all
        if not img_bytes and not self.api_key:
            img_bytes = self._generate_with_pollinations(
                organization=organization,
                post_name=post_name,
                vacancies=vacancies,
                last_date=last_date,
                sector=sector,
            )
            if img_bytes:
                img_bytes = self._resize_to_1280x720(img_bytes)

        # PIL fallback if all AI unavailable or failed
        if not img_bytes:
            logger.warning("All AI generation failed; using PIL fallback.")
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

    def _generate_with_pollinations(
        self,
        organization: str,
        post_name: str,
        vacancies: str,
        last_date: str,
        sector: str,
    ):
        """
        Uses Pollinations.ai free AI image generation API.
        No API key required. Returns image bytes or None.
        """
        try:
            import requests as _req
            import datetime as _dt
            import urllib.parse

            year = _dt.datetime.now().year
            clean_org = organization.strip()
            paren_match = re.search(r'\(([^)]+)\)', clean_org)
            if paren_match and len(paren_match.group(1)) <= 25:
                display_org = paren_match.group(1).strip()
            else:
                display_org = clean_org[:30] + "..." if len(clean_org) > 30 else clean_org

            vac_digits = re.search(r'\d+', str(vacancies))
            vac_num = vac_digits.group(0) if vac_digits else "Various"

            ld = last_date.strip() if last_date and last_date.lower() not in ["refer notification", "check official notification", ""] else "Check Notification"

            theme = SECTOR_THEMES.get(sector, SECTOR_THEMES["uniform"])

            prompt = (
                f"Professional Indian government job recruitment banner thumbnail, 1280x720, "
                f"dark navy blue gradient background, large bold white text: '{display_org} released Notification {year}', "
                f"large bold gold text below: 'Number of posts: {vac_num}', "
                f"large bold red text below that: 'Last date: {ld}', "
                f"Indian professional characters on right side: {theme['character']}, "
                f"decorative elements: {theme['icons']}, "
                f"footer text: 'www.latestjobnotifications.online', "
                f"NOTIFICATION OUT badge in yellow, APPLY NOW button in navy, "
                f"ultra HD, vibrant colors, premium professional design, no watermarks"
            )

            encoded = urllib.parse.quote(prompt)
            url = f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&nologo=true&enhance=true"
            logger.info(f"Pollinations.ai request for: {display_org}")
            resp = _req.get(url, timeout=90)
            if resp.status_code == 200 and len(resp.content) > 5000:
                logger.info(f"Pollinations.ai image OK: {len(resp.content)} bytes")
                return resp.content
            else:
                logger.warning(f"Pollinations.ai: HTTP {resp.status_code}, size={len(resp.content)}")
                return None
        except Exception as e:
            logger.warning(f"Pollinations.ai error: {e}")
            return None




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
