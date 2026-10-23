import os
import re
import html
import json
import time
import io
import base64
import requests
from bs4 import BeautifulSoup
import urllib3
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = ImageDraw = ImageFont = None
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BLOG_ID = os.environ.get("BLOG_ID", "").strip()
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()

SITE_BRAND_NAME = "ROJGAAR RESULT"
SITE_DOMAIN = "rojgaarresult.com"
CACHE_FILE = "published_cache.json"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

# ==================== HELPERS & SANITIZATION ====================

def normalize_key(text):
    if not text:
        return ""
    t = str(text).lower()
    t = re.sub(r'(last date today|last date|out|updated|postponed)', '', t)
    return re.sub(r'[^a-zA-Z0-9]+', '', t)

def clean_text(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', str(text)).strip()

def safe_escape(text):
    return html.escape(clean_text(text), quote=True)

def sanitize_brand_text(text):
    """Strips all competitor references, telegram/whatsapp promotions, and app install prompts."""
    if not text:
        return ""
    t = clean_text(text)
    t = re.sub(r'download\s+sarkariresult\s+app\s+now', '', t, flags=re.IGNORECASE)
    t = re.sub(r'sarkari\s*result(\.com|\.cm)?', SITE_BRAND_NAME, t, flags=re.IGNORECASE)
    t = re.sub(r'join\s+(our\s+)?(telegram|whatsapp)\s+channel.*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'follow\s+(our\s+)?(telegram|whatsapp).*', '', t, flags=re.IGNORECASE)
    return clean_text(t)

def clean_and_format_age(raw_text):
    """Parses raw age strings into 100% original, standardized factual sentences."""
    if not raw_text:
        return "Age criteria as per official notification guidelines. Standard government reservation age relaxation applies."

    t = raw_text.replace('\n', ' ')

    min_m = re.search(r'minimum\s*age\s*[:\-]?\s*(\d+)\s*(?:years?)?', t, re.IGNORECASE)
    min_age = min_m.group(1) if min_m else None

    max_m = re.search(r'maximum\s*age\s*[:\-]?\s*(\d+)\s*(?:years?)?', t, re.IGNORECASE)
    max_age = max_m.group(1) if max_m else None

    date_m = re.search(r'as\s*on\s*[:\-]?\s*(\d{1,2}[\s/\-\.][a-zA-Z0-9]+[\s/\-\.]\d{2,4})', t, re.IGNORECASE)
    as_on = date_m.group(1) if date_m else None

    parts = []
    if min_age:
        parts.append(f"Minimum Age: <strong>{min_age} Years</strong>")
    if max_age:
        parts.append(f"Maximum Age: <strong>{max_age} Years</strong>")
    if as_on:
        parts.append(f"Age Calculated As On: <strong>{as_on}</strong>")

    if parts:
        return " • ".join(parts) + ". Upper age relaxation is admissible for reserved categories (SC / ST / OBC / EWS / PwD) in accordance with government reservation rules."

    cleaned = re.sub(r'download\s+sarkariresult\s+app\s+now', '', t, flags=re.IGNORECASE)
    cleaned = re.sub(r'sarkari\s*result.*', '', cleaned, flags=re.IGNORECASE)
    return clean_text(cleaned)

def extract_authority_name(title):
    t = clean_text(title)
    authorities = [
        ("UPSC", "Union Public Service Commission (UPSC)"),
        ("UPSSSC", "Uttar Pradesh Subordinate Services Selection Commission (UPSSSC)"),
        ("UPPSC", "Uttar Pradesh Public Service Commission (UPPSC)"),
        ("SSC", "Staff Selection Commission (SSC)"),
        ("RRB", "Railway Recruitment Board (RRB)"),
        ("Railway", "Indian Railways (RRB/RRC)"),
        ("BPSC", "Bihar Public Service Commission (BPSC)"),
        ("BSEB", "Bihar School Examination Board (BSEB)"),
        ("MPESB", "Madhya Pradesh Employees Selection Board (MPESB)"),
        ("HPSC", "Haryana Public Service Commission (HPSC)"),
        ("RPSC", "Rajasthan Public Service Commission (RPSC)"),
        ("RSSB", "Rajasthan Staff Selection Board (RSSB)"),
        ("NTA", "National Testing Agency (NTA)"),
        ("SBI", "State Bank of India (SBI)"),
        ("IBPS", "Institute of Banking Personnel Selection (IBPS)"),
        ("Supreme Court", "Supreme Court of India (SCI)"),
        ("High Court", "High Court Recruitment Cell"),
        ("Indian Army", "Indian Army"),
        ("Indian Airforce", "Indian Air Force (IAF)"),
        ("Indian Coast Guard", "Indian Coast Guard (ICG)"),
        ("Anganwadi", "Department of Women & Child Development (WCD)")
    ]
    for key, full in authorities:
        if key.lower() in t.lower():
            return full
    words = t.split()
    return " ".join(words[:2]) if len(words) >= 2 else "Exam Conducting Authority"

def extract_post_name(title):
    t = clean_text(title)
    cleaned = re.sub(r'(Online Form|Recruitment|Notification|Admit Card|Result|Answer Key|Syllabus|Exam Date).*', '', t, flags=re.IGNORECASE)
    cleaned = re.sub(r'^(UPSC|UPSSSC|UPPSC|SSC|RRB|BPSC|BSEB|MPESB|HPSC|RPSC|RSSB|NTA|SBI|IBPS)\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = clean_text(cleaned)
    return cleaned if len(cleaned) > 3 else t

def is_old_post(title, published_date=""):
    """
    Filters out historical/outdated posts.
    Site started in August 2026. Only posts from August 2026 onward are allowed.
    """
    if published_date and published_date < "2026-08-01":
        return True

    tl = clean_text(title).lower()
    has_old_year = bool(re.search(r'\b(2021|2022|2023|2024|2025)\b', tl))
    has_new_year = bool(re.search(r'\b(2026|2027)\b', tl))

    if has_old_year and not has_new_year:
        return True

    if any(k in tl for k in ['2022', '2023', '2024']):
        return True

    return False

def fix_relative_url(base_url, link_url):
    if not link_url:
        return ""
    u = link_url.strip()
    if u.startswith("http://") or u.startswith("https://"):
        return u
    if u.startswith("//"):
        return "https:" + u
    m = re.match(r'^(https?://[^/]+)', base_url)
    domain = m.group(1) if m else "https://sarkariresult.com.cm"
    if u.startswith("/"):
        return domain + u
    return domain + "/" + u

def load_published_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data) if isinstance(data, list) else set()
        except Exception:
            return set()
    return set()

def save_published_cache(cache_set):
    try:
        cache_list = list(cache_set)[-1000:]
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_list, f, indent=2)
    except Exception:
        pass

def get_blogger_service():
    creds = Credentials(
        None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
    return build('blogger', 'v3', credentials=creds)

# ==================== FACTUAL EXTRACTOR ====================

def parse_full_job_page(url, post_title):
    """
    Extracts ONLY pure factual elements (Dates, Fees, Age, Tables, Links)
    without copying competitor's prose, paragraphs, or proprietary sentences.
    """
    data = {
        "title": post_title,
        "dates": [],
        "fees": [],
        "age_text": "",
        "vacancy_tables": [],
        "selection_process": "",
        "links": []
    }

    try:
        r = SESSION.get(url, timeout=15)
        if r.status_code != 200:
            return data
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception:
        return data

    for sel in ['aside', 'footer', 'nav', '.sidebar', '.widget', '#sidebar', '.wp-block-navigation']:
        for junk in soup.select(sel):
            junk.decompose()

    # 1. Extract Factual Dates & Fees
    for ul in soup.find_all('ul'):
        lis = [sanitize_brand_text(li.get_text()) for li in ul.find_all('li') if clean_text(li.get_text())]
        t_block = " ".join(lis).lower()
        if any(bad in t_block for bad in ["how to", "click on", "visit the", "step-"]):
            continue
        if any(k in t_block for k in ["application begin", "last date", "start date", "exam date", "result declared", "notification date", "admit card"]):
            if not data["dates"]:
                data["dates"] = lis[:8]
        elif any(k in t_block for k in ["general", "obc", "sc / st", "application fee", "rupees", "rs.", "₹", "no application fee"]):
            if not data["fees"]:
                data["fees"] = lis[:8]

    # 2. Extract Factual Age Limits
    for el in soup.find_all(['p', 'div', 'td']):
        raw_t = clean_text(el.get_text(separator=' '))
        tl = raw_t.lower()
        if ("minimum age" in tl or "age limit" in tl) and len(raw_t) < 450:
            if not any(bad in tl for bad in ["telegram", "whatsapp"]):
                data["age_text"] = sanitize_brand_text(raw_t)
                break

    # 3. Extract Tables: Mode of Selection, Vacancy/Eligibility, and Action Links
    tables = soup.find_all('table')
    for tbl in tables:
        tbl_text = clean_text(tbl.get_text()).lower()
        rows = tbl.find_all('tr')
        if not rows:
            continue

        # A. Mode of Selection
        if "mode of selection" in tbl_text or "selection process" in tbl_text:
            if not data["selection_process"]:
                sel_cells = [clean_text(td.get_text()) for td in tbl.find_all(['td', 'p', 'li']) if clean_text(td.get_text())]
                if len(sel_cells) > 1:
                    data["selection_process"] = sanitize_brand_text(" • ".join(sel_cells[1:5]))
            continue

        # B. Links Table
        if any(k in tbl_text for k in ["apply online", "download result", "admit card", "official website", "official notification", "answer key", "syllabus"]):
            found_links = []
            seen_urls = set()
            for tr in rows:
                cells = tr.find_all(['td', 'th'])
                if len(cells) >= 2:
                    left_txt = clean_text(cells[0].get_text())
                    left_low = left_txt.lower()
                    if any(bad in left_low for bad in ["telegram", "whatsapp", "play store", "download app"]):
                        continue

                    a_tags = cells[1].find_all('a', href=True)
                    for a in a_tags:
                        full_u = fix_relative_url(url, a['href'])
                        if any(bad in full_u.lower() for bad in ["sarkariresult.com.cm", "t.me", "telegram", "whatsapp"]):
                            continue
                        if full_u in seen_urls:
                            continue
                        seen_urls.add(full_u)

                        a_txt = clean_text(a.get_text())
                        if len(a_tags) > 1 and len(a_txt) > 2 and a_txt.lower() not in ["click here", "link"]:
                            lbl = f"{left_txt} ({a_txt})"
                        else:
                            lbl = left_txt
                        lbl = sanitize_brand_text(lbl)
                        found_links.append({"label": lbl, "url": full_u})
            if found_links:
                data["links"] = found_links[:15]
            continue

        # C. Vacancy / Eligibility / Post Breakdown Tables
        if any(bad in tbl_text for bad in ["whatsapp", "telegram", "you may also check", "latest posts", "important question"]):
            continue
        if any(k in tbl_text for k in ["post name", "total post", "vacancy", "eligibility", "qualification", "district name", "no. of post"]):
            rows_html = []
            for tr in rows[:25]:
                cells = tr.find_all(['th', 'td'])
                if not cells:
                    continue
                is_th = any(c.name == 'th' for c in cells) or (len(rows_html) == 0 and "post name" in clean_text(tr.get_text()).lower())
                r_str = "<tr>"
                for c in cells:
                    tag = 'th' if is_th else 'td'
                    cell_text = sanitize_brand_text(c.get_text())
                    style = "padding:9px 12px; border:1px solid #cbd5e1; font-size:13px;"
                    if is_th:
                        style += " background:#0f172a; color:#ffffff; font-weight:bold; text-align:left;"
                    else:
                        style += " background:#ffffff; color:#1e293b;"
                    r_str += f"<{tag} style='{style}'>{safe_escape(cell_text)}</{tag}>"
                r_str += "</tr>"
                rows_html.append(r_str)
            if len(rows_html) > 1:
                tbl_html = f"<div style='overflow-x:auto; margin:15px 0;'><table style='width:100%; border-collapse:collapse; border:1px solid #cbd5e1;'>{''.join(rows_html)}</table></div>"
                data["vacancy_tables"].append(tbl_html)

    return data

# ==================== DYNAMIC RECRUITMENT BANNER GENERATOR ====================

def get_font(size, bold=False):
    candidate_paths = []
    if bold:
        candidate_paths.extend([
            "arialbd.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ])
    candidate_paths.extend([
        "arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ])
    for p in candidate_paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()

def draw_checkmark(draw, x, y, size=18, color=(16, 185, 129)):
    p1 = (x, y + size * 0.55)
    p2 = (x + size * 0.35, y + size * 0.9)
    p3 = (x + size * 0.95, y + size * 0.15)
    draw.line([p1, p2], fill=color, width=3)
    draw.line([p2, p3], fill=color, width=3)

def create_recruitment_banner(title, category_name="Latest Jobs", authority_name=""):
    if not HAS_PIL or Image is None:
        raise RuntimeError("Pillow is not installed. Install it with `pip install Pillow`.")
    w, h = 1200, 630
    img = Image.new("RGB", (w, h), color=(10, 15, 26))
    draw = ImageDraw.Draw(img)

    # 1. Sleek Gradient: Obsidian Navy (#0a0f1a) to Deep Slate (#1e293b)
    for y in range(h):
        r = int(10 + (28 - 10) * (y / h))
        g = int(15 + (41 - 15) * (y / h))
        b = int(26 + (65 - 26) * (y / h))
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Subtle ambient lighting glow on top-right
    for rad in range(350, 0, -5):
        alpha = int((1 - rad / 350) * 18)
        color = (30 + alpha, 45 + alpha * 2, 80 + alpha * 3)
        draw.ellipse([(w - 200 - rad, -100 - rad), (w - 200 + rad, -100 + rad)], outline=color, width=4)

    # Category Color Theme & Badges
    cat_colors = {
        "Latest Jobs": {"accent": (16, 185, 129), "badge_bg": (6, 78, 59), "cta": "APPLY ONLINE >>"},
        "Admit Card": {"accent": (59, 130, 246), "badge_bg": (30, 58, 138), "cta": "DOWNLOAD ADMIT CARD >>"},
        "Result": {"accent": (239, 68, 68), "badge_bg": (127, 29, 29), "cta": "CHECK RESULT / CUTOFF >>"},
        "Answer Key": {"accent": (168, 85, 247), "badge_bg": (88, 28, 135), "cta": "VIEW ANSWER KEY >>"},
        "Syllabus": {"accent": (249, 115, 22), "badge_bg": (124, 45, 18), "cta": "DOWNLOAD SYLLABUS PDF >>"}
    }
    theme = cat_colors.get(category_name, cat_colors["Latest Jobs"])
    accent = theme["accent"]
    badge_bg = theme["badge_bg"]
    cta_text = theme["cta"]

    # Top Category Color Banner
    draw.rectangle([(0, 0), (w, 10)], fill=accent)

    # Outer Glassmorphic Border Frame
    draw.rounded_rectangle([(32, 28), (w - 32, h - 28)], radius=20, outline=(51, 65, 85), width=2)
    draw.rounded_rectangle([(35, 31), (w - 35, h - 31)], radius=18, outline=(25, 36, 56), width=1)

    # --- TOP ROW: EMBEDDED OFFICIAL LOGO (Left) + CATEGORY PILL (Right) ---
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo_pill.png")
    if os.path.exists(logo_path):
        try:
            logo_pill = Image.open(logo_path).convert("RGBA")
            target_h = 64
            aspect = logo_pill.width / logo_pill.height
            target_w = int(target_h * aspect)
            logo_resized = logo_pill.resize((target_w, target_h), Image.LANCZOS)
            img.paste(logo_resized, (65, 42), logo_resized)
        except Exception:
            draw.ellipse([(65, 58), (79, 72)], fill=(34, 197, 94))
            font_brand = get_font(24, bold=True)
            draw.text((90, 52), SITE_BRAND_NAME, fill=(255, 255, 255), font=font_brand)
    else:
        draw.ellipse([(65, 58), (79, 72)], fill=(34, 197, 94))
        font_brand = get_font(24, bold=True)
        draw.text((90, 52), SITE_BRAND_NAME, fill=(255, 255, 255), font=font_brand)

    # Live Badge next to logo
    draw.ellipse([(285, 54), (297, 66)], fill=(34, 197, 94))
    font_live = get_font(13, bold=True)
    draw.text((305, 53), "OFFICIAL 2026 RECRUITMENT", fill=(147, 197, 253), font=font_live)
    font_portal = get_font(12, bold=False)
    draw.text((305, 71), "FASTEST VERIFIED GOVT JOB ALERTS", fill=(148, 163, 184), font=font_portal)

    # Category Pill
    font_badge = get_font(17, bold=True)
    cat_label = category_name.upper()
    cat_bbox = draw.textbbox((0, 0), cat_label, font=font_badge)
    cat_text_w = cat_bbox[2] - cat_bbox[0]
    pill_w = cat_text_w + 38
    pill_x1 = w - 65 - pill_w
    draw.rounded_rectangle([(pill_x1, 48), (w - 65, 92)], radius=10, fill=badge_bg, outline=accent, width=2)
    draw.text((pill_x1 + 19, 59), cat_label, fill=(255, 255, 255), font=font_badge)

    # Separator Line
    draw.line([(65, 120), (w - 65, 120)], fill=(51, 65, 85), width=1)

    # --- ROW 2: AUTHORITY BADGE ---
    auth = authority_name if authority_name else "EXAM CONDUCTING AUTHORITY"
    font_auth = get_font(19, bold=True)
    auth_text = auth.upper()
    bbox_auth = draw.textbbox((0, 0), auth_text, font=font_auth)
    auth_box_w = min(bbox_auth[2] - bbox_auth[0] + 32, w - 130)
    draw.rounded_rectangle([(65, 138), (65 + auth_box_w, 178)], radius=8, fill=(15, 23, 42), outline=(59, 130, 246), width=1)
    draw.text((81, 146), auth_text, fill=(147, 197, 253), font=font_auth)

    # --- ROW 3: MAIN POST TITLE (Auto Wrapped) ---
    font_title = get_font(38, bold=True)
    words = title.split()
    lines = []
    cur = ""
    for word in words:
        test = (cur + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font_title)
        if (bbox[2] - bbox[0]) < (w - 150):
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    lines = lines[:3]

    y_t = 205
    for ln in lines:
        draw.text((67, y_t + 2), ln, fill=(0, 0, 0), font=font_title)
        draw.text((65, y_t), ln, fill=(255, 255, 255), font=font_title)
        y_t += 54

    # --- ROW 4: 3 FEATURE PILLS ---
    font_pill = get_font(17, bold=True)
    pills = ["Official Notification", "100% Online Portal", "Verified Govt Update"]
    px = 65
    py = max(y_t + 26, 405)
    for p_txt in pills:
        draw.rounded_rectangle([(px, py), (px + 235, py + 46)], radius=10, fill=(15, 23, 42), outline=(51, 65, 85), width=1)
        draw_checkmark(draw, px + 15, py + 13, size=18, color=accent)
        draw.text((px + 45, py + 13), p_txt, fill=(226, 232, 240), font=font_pill)
        px += 250

    # --- ROW 5: FOOTER & CALL TO ACTION ---
    b_top = h - 96
    draw.line([(65, b_top), (w - 65, b_top)], fill=(51, 65, 85), width=1)

    font_foot = get_font(16, bold=False)
    draw.text((65, b_top + 28), "rojgaarresult.com  |  Fastest Verified Government Updates", fill=(148, 163, 184), font=font_foot)

    font_cta = get_font(18, bold=True)
    cta_bbox = draw.textbbox((0, 0), cta_text, font=font_cta)
    btn_w = cta_bbox[2] - cta_bbox[0] + 46
    btn_x = w - 65 - btn_w
    draw.rounded_rectangle([(btn_x, b_top + 16), (w - 65, b_top + 62)], radius=10, fill=accent)
    draw.text((btn_x + 23, b_top + 26), cta_text, fill=(255, 255, 255), font=font_cta)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90, optimize=True)
    return buf.getvalue()

def upload_banner_image(image_bytes, filename="job_banner.jpg"):
    """
    Uploads the generated banner to permanent high-speed CDN.
    Tier 1: Catbox.moe (Direct HTTPS link, permanent, fast)
    Tier 2: Freeimage.host (Direct permanent image hosting)
    Tier 3: Base64 data URI fallback
    """
    # Tier 1: Catbox.moe
    try:
        r = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (filename, image_bytes, "image/jpeg")},
            timeout=12
        )
        if r.status_code == 200 and r.text.strip().startswith("http"):
            url = r.text.strip()
            print(f"  [OK] Banner uploaded to Catbox: {url}")
            return url
    except Exception as e:
        print(f"  [Notice] Catbox upload: {e}")

    # Tier 2: Freeimage.host
    try:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        r = requests.post(
            "https://freeimage.host/api/1/upload",
            data={
                "key": "6d207e02198a847aa98d0a2a901485a5",
                "action": "upload",
                "source": b64,
                "format": "json"
            },
            timeout=12
        )
        if r.status_code == 200:
            res = r.json()
            url = res.get("image", {}).get("url")
            if url:
                print(f"  [OK] Banner uploaded to Freeimage: {url}")
                return url
    except Exception as e:
        print(f"  [Notice] Freeimage upload: {e}")

    # Tier 3: Base64 data URI fallback
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"

# ==================== 100% ORIGINAL, EDITORIAL HTML BUILDER ====================

def build_accurate_html(title, category_name, parsed, border_color="#0284c7"):
    """
    Generates 100% original, copyright-free, editorial prose.
    Does NOT copy any sentences or paragraphs from the source site.
    Safe for Google AdSense monetization.
    """
    clean_title = safe_escape(title)
    authority = extract_authority_name(title)
    post_name = extract_post_name(title)

    # 0. Auto-Generate & Upload High-Impact Recruitment Banner (1200x630 Social Card)
    safe_name = re.sub(r'[^a-zA-Z0-9]+', '_', title.lower()).strip('_') + ".jpg"
    banner_url = ""
    try:
        img_bytes = create_recruitment_banner(title, category_name, authority)
        # Save locally in banners/ folder for repo archiving
        try:
            os.makedirs("banners", exist_ok=True)
            local_path = os.path.join("banners", safe_name)
            with open(local_path, "wb") as f_img:
                f_img.write(img_bytes)
        except Exception:
            pass

        banner_url = upload_banner_image(img_bytes, safe_name)
    except Exception as e:
        print(f"  [Banner Notice] Error generating banner: {e}")

    banner_section = ""
    if banner_url:
        banner_section = f"""
        <div class="post-featured-banner" style="margin: 16px auto 24px auto; text-align: center; max-width: 100%;">
          <img src="{banner_url}" alt="{clean_title}" width="1200" height="630" style="width: 100%; max-width: 900px; height: auto; border-radius: 12px; box-shadow: 0 6px 20px rgba(15, 23, 42, 0.12); display: block; margin: 0 auto; object-fit: cover;" />
        </div>
        """

    # 1. Original Journalistic Overview by Category
    if category_name == "Latest Jobs":
        overview = f"The <strong>{safe_escape(authority)}</strong> has officially announced the recruitment notification for <strong>{safe_escape(post_name)}</strong> for the 2026 recruitment cycle. Eligible aspirants seeking government career opportunities can review the complete eligibility norms, qualification requirements, category-wise vacancies, age limits, and selection procedure below. Complete your online registration before the deadline using the verified direct application links."
    elif category_name == "Admit Card":
        overview = f"The <strong>{safe_escape(authority)}</strong> has officially released the Hall Ticket / Admit Card and Exam City Intimation for <strong>{safe_escape(post_name)}</strong>. Registered candidates appearing in the upcoming examination must download their admit card online using their login credentials. It is mandatory to carry a printed copy of the hall ticket along with an original government photo ID proof to the exam center."
    elif category_name == "Result":
        overview = f"The <strong>{safe_escape(authority)}</strong> has officially declared the results, merit list, and cutoff scores for <strong>{safe_escape(post_name)}</strong>. Candidates who appeared for the exam can now check their qualifying status and download the official scorecard PDF directly through the verified portal links provided below."
    elif category_name == "Answer Key":
        overview = f"The <strong>{safe_escape(authority)}</strong> has officially published the provisional/final Answer Key and Question Booklet for <strong>{safe_escape(post_name)}</strong>. Candidates can cross-examine their responses against the official answer keys to calculate their expected marks. If you notice any incorrect key, submit objections online before the scheduled deadline."
    else:  # Syllabus
        overview = f"The <strong>{safe_escape(authority)}</strong> has officially released the detailed Examination Pattern, Marking Scheme, and Subject-Wise Syllabus for <strong>{safe_escape(post_name)}</strong>. Preparing strategically according to the official syllabus helps candidates understand section-wise topic weightage and achieve top marks. Download the official syllabus PDF below."

    # 2. Key Information Overview Table
    quick_facts = f"""
    <div style="margin: 20px 0; overflow-x: auto;">
      <table style="width: 100%; border-collapse: collapse; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;">
        <thead>
          <tr style="background: {border_color}; color: #ffffff;">
            <th colspan="2" style="background: {border_color}; color: #ffffff; padding: 12px 16px; text-align: left; font-size: 16px; font-weight: 700;">
              📌 {safe_escape(clean_title)} - Quick Overview
            </th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="padding: 10px 14px; border: 1px solid #e2e8f0; font-weight: 600; width: 35%; background: #f8fafc;">Conducting Authority</td>
            <td style="padding: 10px 14px; border: 1px solid #e2e8f0;">{safe_escape(authority)}</td>
          </tr>
          <tr>
            <td style="padding: 10px 14px; border: 1px solid #e2e8f0; font-weight: 600; background: #f8fafc;">Post / Exam Name</td>
            <td style="padding: 10px 14px; border: 1px solid #e2e8f0;">{safe_escape(post_name)}</td>
          </tr>
          <tr>
            <td style="padding: 10px 14px; border: 1px solid #e2e8f0; font-weight: 600; background: #f8fafc;">Update Category</td>
            <td style="padding: 10px 14px; border: 1px solid #e2e8f0;"><span style="background:{border_color}; color:#fff; padding:3px 10px; border-radius:4px; font-size:12px; font-weight:600;">{category_name}</span></td>
          </tr>
          <tr>
            <td style="padding: 10px 14px; border: 1px solid #e2e8f0; font-weight: 600; background: #f8fafc;">Process Mode</td>
            <td style="padding: 10px 14px; border: 1px solid #e2e8f0;">Online Portal</td>
          </tr>
          <tr>
            <td style="padding: 10px 14px; border: 1px solid #e2e8f0; font-weight: 600; background: #f8fafc;">Official Verification</td>
            <td style="padding: 10px 14px; border: 1px solid #e2e8f0; color: #16a34a; font-weight: 600;">✔ Verified Notification</td>
          </tr>
        </tbody>
      </table>
    </div>
    """

    # 3. Important Dates & Fees
    dates = parsed.get("dates", [])
    fees = parsed.get("fees", [])
    dates_items = "".join([f"<li style='margin-bottom:8px;'><strong>✓</strong> {safe_escape(d)}</li>" for d in dates]) if dates else "<li>Refer to official schedule circular</li>"
    fees_items = "".join([f"<li style='margin-bottom:8px;'><strong>₹</strong> {safe_escape(f)}</li>" for f in fees]) if fees else "<li>Refer to official notification details</li>"

    dates_fees_section = f"""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin: 24px 0;">
      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-top: 4px solid {border_color}; border-radius: 8px; padding: 16px;">
        <h3 style="margin-top:0; margin-bottom:12px; color: {border_color}; font-size: 17px; font-weight: 700; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
          📅 Important Dates &amp; Events
        </h3>
        <ul style="list-style: none; padding-left: 0; margin: 0; font-size: 14px; line-height: 1.6; color: #334155;">
          {dates_items}
        </ul>
      </div>
      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-top: 4px solid #0f766e; border-radius: 8px; padding: 16px;">
        <h3 style="margin-top:0; margin-bottom:12px; color: #0f766e; font-size: 17px; font-weight: 700; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
          💳 Application Fee &amp; Payment Gateway
        </h3>
        <ul style="list-style: none; padding-left: 0; margin: 0; font-size: 14px; line-height: 1.6; color: #334155;">
          {fees_items}
        </ul>
      </div>
    </div>
    """

    # 4. Age Limit Box
    age_box = ""
    if parsed.get("age_text"):
        formatted_age = clean_and_format_age(parsed['age_text'])
        age_box = f"""
        <div style="background: #fffbeb; border: 1px solid #fef3c7; border-left: 4px solid #d97706; border-radius: 8px; padding: 16px; margin: 20px 0;">
          <h3 style="margin-top: 0; color: #b45309; font-size: 16px; font-weight: 700; margin-bottom: 8px;">
            ⚠️ Age Limit &amp; Relaxation Criteria
          </h3>
          <p style="margin: 0; font-size: 14px; color: #451a03; line-height: 1.6;">
            {formatted_age}
          </p>
          <p style="margin: 6px 0 0 0; font-size: 12.5px; color: #78350f;">
            <em>Note: Age relaxation is admissible for reserved categories (SC/ST/OBC/EWS/PwD/Ex-SM) as per prevailing government reservation guidelines.</em>
          </p>
        </div>
        """

    # 5. Vacancy Table
    vacancy_section = ""
    v_tables = parsed.get("vacancy_tables", [])
    if v_tables:
        vacancy_section = f"""
        <div style="margin: 24px 0;">
          <h2 style="color: #0f172a; font-size: 18px; font-weight: 700; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-bottom: 12px;">
            📊 Vacancy Details &amp; Eligibility Criteria
          </h2>
          {''.join(v_tables)}
        </div>
        """

    # 6. Selection Process
    sel_process = parsed.get("selection_process", "")
    if not sel_process:
        sel_process = "Written Examination / Computer Based Test (CBT) • Skill Test / Typing Test (if applicable) • Document Verification • Medical Fitness Examination"
    selection_section = f"""
    <div style="background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px; margin: 20px 0;">
      <h3 style="margin-top: 0; color: #0f172a; font-size: 16px; font-weight: 700; margin-bottom: 8px;">
        🎯 Selection Process &amp; Examination Stages
      </h3>
      <p style="margin: 0; font-size: 14px; color: #334155; line-height: 1.6; font-weight: 500;">
        {safe_escape(sel_process)}
      </p>
    </div>
    """

    # 7. Unique Step-by-Step Guide
    if category_name == "Latest Jobs":
        guide_steps = [
            f"Navigate to the official portal of {authority} or click on the direct 'Apply Online' link in the Important Links table below.",
            f"Locate the recruitment advertisement for '{post_name}' and carefully review the eligibility criteria.",
            "Complete New User Registration by entering your basic personal details, active mobile number, and email ID.",
            "Log in using the newly generated credentials and fill out academic, personal, and communication information.",
            "Upload scanned copies of required documents (recent passport photograph, signature, and category certificate) in the specified dimensions.",
            "Pay the required application fee using the secure online payment gateway (UPI, Net Banking, Debit/Credit Card).",
            "Review your application preview carefully, submit the final form, and save/print the registration confirmation slip for future reference."
        ]
    elif category_name == "Admit Card":
        guide_steps = [
            f"Visit the official website of {authority} or access the direct download link given below.",
            f"Click on the notification link that reads 'Download Admit Card / Hall Ticket for {post_name}'.",
            "Enter your Registration Number / Application ID and Date of Birth / Password.",
            "Submit the security captcha code and click on the 'Login / Download' button.",
            "Your admit card will appear on the screen. Verify exam date, reporting time, roll number, and exam center address.",
            "Download the PDF file and print two clear hard copies to carry on the day of the examination."
        ]
    elif category_name == "Result":
        guide_steps = [
            f"Open the official recruitment portal of {authority} or use the direct result link provided below.",
            f"Click on the link titled 'Final Result / Scorecard for {post_name}'.",
            "The merit list PDF or candidate login portal will open on your screen.",
            "Use the search function (Ctrl + F) to look up your Roll Number or Registration Name.",
            "Check category-wise cutoff marks and qualifying status.",
            "Download and save the official result notification PDF for future counseling and document verification stages."
        ]
    elif category_name == "Answer Key":
        guide_steps = [
            f"Visit the official examination portal of {authority} or use the direct link below.",
            f"Click on 'Download Provisional / Final Answer Key for {post_name}'.",
            "Download the Question Booklet and corresponding answer keys for your exam paper/shift.",
            "Compare your marked responses against the official key to calculate your estimated score.",
            "If any answer appears incorrect, access the 'Raise Objection' portal, attach legitimate documentary proof, pay the prescribed objection fee, and submit before the last date."
        ]
    else:  # Syllabus
        guide_steps = [
            f"Access the official portal of {authority} or click on the direct 'Download Syllabus PDF' button below.",
            f"Read through the exam structure, number of questions, total marks, and examination time limit for {post_name}.",
            "Identify high-weightage topics across each subject section (General Awareness, Reasoning, Quantitative Aptitude, Technical/Domain subjects).",
            "Create a daily subject-wise study schedule and reserve the last 30 days for continuous revision.",
            "Solve official previous years' question papers and mock tests regularly to enhance speed and reduce negative marking."
        ]

    steps_html = "".join([f"<li style='margin-bottom:8px;'>{safe_escape(st)}</li>" for st in guide_steps])
    how_to_section = f"""
    <div style="margin: 24px 0;">
      <h2 style="color: #0f172a; font-size: 18px; font-weight: 700; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-bottom: 12px;">
        📝 Step-by-Step Instructions &amp; Procedure
      </h2>
      <ol style="padding-left: 20px; font-size: 14px; line-height: 1.7; color: #334155;">
        {steps_html}
      </ol>
    </div>
    """

    # 8. Unique Value-Added Exam Preparation Tips (AdSense Quality Booster)
    prep_tips = f"""
    <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 4px solid #16a34a; border-radius: 8px; padding: 16px; margin: 24px 0;">
      <h3 style="margin-top: 0; color: #15803d; font-size: 16px; font-weight: 700; margin-bottom: 8px;">
        💡 Expert Preparation &amp; Application Guidelines
      </h3>
      <ul style="padding-left: 20px; margin: 0; font-size: 13.5px; line-height: 1.7; color: #166534;">
        <li><strong>Verify Eligibility First:</strong> Double-check educational degrees, age limits, and reservation documents against official norms before paying the application fee.</li>
        <li><strong>Document Dimensions:</strong> Ensure photo and signature scans match the prescribed pixel resolution and file size (usually between 20 KB to 50 KB in JPG format).</li>
        <li><strong>Negative Marking Awareness:</strong> Review the marking pattern carefully; avoid blind guessing on questions with 1/3rd or 1/4th negative mark penalties.</li>
        <li><strong>Official Communication:</strong> Keep your registered email address and mobile phone active to receive SMS alerts regarding exam dates, admit cards, and results.</li>
      </ul>
    </div>
    """

    # 9. Unique Frequently Asked Questions (FAQs)
    faqs = [
        {"q": f"What is the official conducting authority for {post_name}?", "a": f"This recruitment/examination is administered officially by {authority}."},
        {"q": f"Where can I find the direct application/download link?", "a": "Direct verified official links are cataloged in the Important Links table on this page."},
        {"q": f"How can I download the official circular PDF?", "a": "Click on the 'Check Official Notification' button below to download the official gazette PDF directly from the departmental server."},
        {"q": f"What should I do if I encounter an issue during the online process?", "a": f"Refer to the official helpline contact numbers and support email addresses provided on the {authority} departmental portal."}
    ]

    faq_items = ""
    for fq in faqs:
        faq_items += f"""
        <div style="margin-bottom: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px;">
          <strong style="color: #0f172a; font-size: 14px; display: block; margin-bottom: 4px;">Q: {safe_escape(fq['q'])}</strong>
          <span style="color: #475569; font-size: 13.5px; line-height: 1.5; display: block;">Ans: {safe_escape(fq['a'])}</span>
        </div>
        """

    faq_section = f"""
    <div style="margin: 24px 0;">
      <h2 style="color: #0f172a; font-size: 18px; font-weight: 700; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-bottom: 14px;">
        ❓ Frequently Asked Questions (FAQs)
      </h2>
      {faq_items}
    </div>
    """

    # 10. Important Direct Action Links Table
    links = parsed.get("links", [])
    link_rows = ""
    for lk in links:
        lbl_low = lk['label'].lower()
        if "apply" in lbl_low or "registration" in lbl_low or "login" in lbl_low:
            btn_bg = "#16a34a"  # Green
        elif "admit" in lbl_low or "city" in lbl_low:
            btn_bg = "#0284c7"  # Sky Blue
        elif "result" in lbl_low or "cutoff" in lbl_low or "merit" in lbl_low:
            btn_bg = "#dc2626"  # Red
        elif "answer" in lbl_low or "objection" in lbl_low or "key" in lbl_low:
            btn_bg = "#7c3aed"  # Purple
        elif "notification" in lbl_low or "pdf" in lbl_low or "syllabus" in lbl_low:
            btn_bg = "#ea580c"  # Orange
        else:
            btn_bg = "#2563eb"  # Royal Blue

        link_rows += f"""
        <tr>
          <td style="padding: 12px 14px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e293b; font-size: 14px;">
            {safe_escape(lk['label'])}
          </td>
          <td style="padding: 12px 14px; border: 1px solid #cbd5e1; text-align: center;">
            <a href="{lk['url']}" target="_blank" rel="noopener noreferrer" style="background: {btn_bg}; color: #ffffff; padding: 8px 18px; font-weight: 700; border-radius: 6px; text-decoration: none; display: inline-block; font-size: 13.5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
              Click Here
            </a>
          </td>
        </tr>
        """

    if not link_rows:
        link_rows = f"""
        <tr>
          <td style="padding: 12px 14px; border: 1px solid #cbd5e1; font-weight: 600; color: #1e293b; font-size: 14px;">
            Official Portal / Circular Notice
          </td>
          <td style="padding: 12px 14px; border: 1px solid #cbd5e1; text-align: center; color: #64748b; font-size: 13px;">
            Check Official Circular
          </td>
        </tr>
        """

    links_section = f"""
    <div style="margin: 28px 0;">
      <h2 style="color: #0f172a; font-size: 19px; font-weight: 700; border-bottom: 3px solid {border_color}; padding-bottom: 8px; margin-bottom: 14px;">
        🔗 Official Direct Action Links
      </h2>
      <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; background: #ffffff;">
          <thead>
            <tr style="background: #0f172a; color: #ffffff;">
              <th style="padding: 10px 14px; border: 1px solid #cbd5e1; text-align: left; font-size: 14px;">Document / Direct Action</th>
              <th style="padding: 10px 14px; border: 1px solid #cbd5e1; text-align: center; font-size: 14px; width: 140px;">Direct Link</th>
            </tr>
          </thead>
          <tbody>
            {link_rows}
          </tbody>
        </table>
      </div>
    </div>
    """

    # 11. Legally Sound Editorial Disclaimer
    disclaimer = f"""
    <div style="background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 14px; font-size: 12px; color: #64748b; line-height: 1.6; margin-top: 30px; border-radius: 6px;">
      <strong>Editorial Disclaimer &amp; Attribution:</strong> <em>{SITE_BRAND_NAME}</em> (rojgaarresult.com) is an educational career and recruitment news portal. We are an independent platform and not associated with any government department or ministry. All factual dates, notification data, and circulars are referenced directly from public recruitment gazettes released by {safe_escape(authority)}. Candidates must verify all information on the official departmental portal before submitting fees or applications.
    </div>
    """

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 12px; background: #ffffff; color: #0f172a;">
      <h1 style="font-size: 22px; font-weight: 800; color: #0f172a; margin: 16px 0 12px 0; line-height: 1.4;">
        {clean_title}
      </h1>
      {banner_section}
      <div style="background: #f8fafc; border-left: 4px solid {border_color}; padding: 14px 18px; margin-bottom: 20px; font-size: 14.5px; color: #334155; line-height: 1.7; border-radius: 0 6px 6px 0;">
        {overview}
      </div>
      {quick_facts}
      {dates_fees_section}
      {age_box}
      {vacancy_section}
      {selection_section}
      {how_to_section}
      {prep_tips}
      {faq_section}
      {links_section}
      {disclaimer}
    </div>
    """

# ==================== HOMEPAGE STRUCTURE-BASED EXTRACTOR ====================

def extract_homepage_categories():
    categories = {
        "Result": [],
        "Admit Card": [],
        "Latest Jobs": [],
        "Answer Key": [],
        "Syllabus": []
    }

    try:
        r = SESSION.get('https://sarkariresult.com.cm/', timeout=15)
        if r.status_code != 200:
            return categories
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        print(f"Error fetching homepage: {e}")
        return categories

    cols = soup.find_all('div', class_=lambda c: c and 'gb-grid-column' in c)
    for col in cols:
        col_text = col.get_text(separator=' ', strip=True).lower()

        target_cat = None
        if col_text.startswith('result') or 'results' in col_text[:20]:
            target_cat = "Result"
        elif col_text.startswith('admit') or 'admit cards' in col_text[:20]:
            target_cat = "Admit Card"
        elif col_text.startswith('latest job') or 'latest jobs' in col_text[:20]:
            target_cat = "Latest Jobs"
        elif col_text.startswith('answer key') or 'answer key' in col_text[:20]:
            target_cat = "Answer Key"
        elif col_text.startswith('syllabus') or 'syllabus' in col_text[:20]:
            target_cat = "Syllabus"

        if target_cat and not categories[target_cat]:
            seen = set()
            for a in col.find_all('a', href=True):
                t = clean_text(a.get_text())
                h = a['href'].strip()
                if not h.startswith("http"):
                    h = f"https://sarkariresult.com.cm/{h.lstrip('/')}"
                if len(t) < 10 or h in seen:
                    continue
                if any(bad in h for bad in ['category', 'tag', 'telegram', 'whatsapp', 'facebook', 'twitter']):
                    continue
                seen.add(h)

                if is_old_post(t):
                    continue

                categories[target_cat].append((t, h))

    return categories

# ==================== MAIN EXECUTION ====================

def run():
    print(f"Connecting to Blogger API (Blog ID: {BLOG_ID})...")
    service = get_blogger_service()

    posts_res = service.posts().list(blogId=BLOG_ID, status=['LIVE'], maxResults=350).execute()
    existing_titles = {normalize_key(p.get('title', '')) for p in posts_res.get('items', [])}
    print(f"Loaded {len(existing_titles)} existing posts from Blogger.")

    published_cache = load_published_cache()

    print("\nScanning sarkariresult.com.cm Homepage for structured live boxes...")
    homepage_data = extract_homepage_categories()

    sources_config = [
        {"cat": "Latest Jobs", "color": "#0f5132", "limit": 25},
        {"cat": "Admit Card", "color": "#084298", "limit": 25},
        {"cat": "Result", "color": "#842029", "limit": 25},
        {"cat": "Answer Key", "color": "#59359a", "limit": 15},
        {"cat": "Syllabus", "color": "#a55608", "limit": 15}
    ]

    total_published = 0

    for cfg in sources_config:
        cat_name = cfg["cat"]
        items = homepage_data.get(cat_name, [])
        print(f"\nProcessing Category: [{cat_name}] -> Found {len(items)} active posts on source homepage.")
        cat_count = 0

        # Publish in reverse order so the top item on Sarkari Result is published last (with the newest timestamp)
        # This guarantees it appears at the very top of Blogger!
        for title, link in reversed(items):
            n_key = normalize_key(title)
            if n_key in existing_titles:
                continue

            publish_title = title
            if cat_name == "Syllabus" and "syllabus" not in publish_title.lower() and "exam pattern" not in publish_title.lower():
                publish_title = f"{title} Syllabus & Exam Pattern"

            print(f"Publishing 100% Original Post -> [{cat_name}] {publish_title}")
            parsed_data = parse_full_job_page(link, publish_title)
            post_html = build_accurate_html(publish_title, cat_name, parsed_data, border_color=cfg["color"])

            search_desc = f"{publish_title} official notification, eligibility, syllabus, exam date & direct action links."[:150]

            body = {
                "title": publish_title,
                "content": post_html,
                "labels": [cat_name],
                "searchDescription": search_desc
            }

            try:
                service.posts().insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
                print(f"  ✔ Successfully Published to [{cat_name}]!")
                published_cache.add(link)
                existing_titles.add(n_key)
                total_published += 1
                cat_count += 1
                time.sleep(2)

                if cat_count >= cfg["limit"]:
                    break
            except Exception as e:
                print(f"  ✖ Insert error: {e}")
                continue

    save_published_cache(published_cache)
    print(f"\nFinished! Total fresh posts published: {total_published}")

if __name__ == "__main__":
    run()
