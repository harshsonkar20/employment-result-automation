import os
import re
import html
import json
import time
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
import urllib3
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BLOG_ID = os.environ.get("BLOG_ID", "").strip()
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()

SITE_BRAND_NAME = "EMPLOYMENT RESULT"
CACHE_FILE = "published_cache.json"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
})

def load_published_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data) if isinstance(data, list) else set()
        except Exception as e:
            print(f"[Cache Load Warning] {e}")
            return set()
    return set()

def save_published_cache(cache_set):
    try:
        cache_list = list(cache_set)[-800:]
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_list, f, indent=2)
    except Exception as e:
        print(f"[Cache Save Warning] {e}")

def get_blogger_service():
    creds = Credentials(
        None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
    return build('blogger', 'v3', credentials=creds)

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', str(text))
    return text.strip()

def safe_escape(text):
    return html.escape(clean_text(text), quote=True)

def normalize_key(text):
    return re.sub(r'[^a-zA-Z0-9]', '', clean_text(text).lower())

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

def generate_banner_html(title, bg_color="#8b0000"):
    clean_t = safe_escape(title)
    line1 = clean_t[:55]
    line2 = clean_t[55:110] if len(clean_t) > 55 else ""
    badge_width = 290
    badge_x = (800 - badge_width) // 2

    return f"""
    <div style="text-align: center; margin-bottom: 20px;">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 380" style="width: 100%; max-width: 800px; height: auto; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.15);">
        <defs>
          <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:{bg_color};stop-opacity:1" />
            <stop offset="100%" style="stop-color:#1a1a1a;stop-opacity:1" />
          </linearGradient>
        </defs>
        <rect width="800" height="380" fill="url(#grad)" rx="8"/>
        <rect x="0" y="0" width="800" height="65" fill="rgba(0,0,0,0.35)"/>
        <text x="400" y="44" fill="#ffffff" font-size="24" font-family="Arial, Helvetica, sans-serif" font-weight="bold" text-anchor="middle" letter-spacing="2">
          ★ {SITE_BRAND_NAME} OFFICIAL NOTIFICATION ★
        </text>
        <rect x="{badge_x}" y="85" width="{badge_width}" height="36" rx="18" fill="#ffcc00"/>
        <text x="400" y="108" fill="#000000" font-size="14" font-family="Arial, Helvetica, sans-serif" font-weight="bold" text-anchor="middle" letter-spacing="0.5">
          LATEST RECRUITMENT UPDATE
        </text>
        <text x="400" y="175" fill="#ffffff" font-size="24" font-family="Arial, Helvetica, sans-serif" font-weight="bold" text-anchor="middle">
          {line1}
        </text>
        <text x="400" y="215" fill="#ffffff" font-size="22" font-family="Arial, Helvetica, sans-serif" font-weight="bold" text-anchor="middle">
          {line2}
        </text>
        <rect x="0" y="320" width="800" height="60" fill="rgba(255,255,255,0.1)"/>
        <text x="400" y="356" fill="#f0f0f0" font-size="16" font-family="Arial, Helvetica, sans-serif" font-weight="normal" text-anchor="middle">
          Online Form | Important Dates | Fee | Eligibility Details
        </text>
      </svg>
    </div>
    """

def parse_full_job_page(url):
    data = {"dates": [], "fees": [], "age_text": "", "links": [], "vacancy_tables_html": ""}
    try:
        r = SESSION.get(url, timeout=10)
        if r.status_code != 200:
            data["links"] = [{"label": "Official Notification & Direct Link", "url": url}]
            return data
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        print(f"  [HTTP Fetch Error] {e}")
        data["links"] = [{"label": "Official Notification & Direct Link", "url": url}]
        return data

    # 1. Dates & Fees
    try:
        for ul in soup.find_all('ul'):
            lis = [safe_escape(li.get_text()) for li in ul.find_all('li')]
            block = " ".join(lis).lower()
            if any(k in block for k in ["application begin", "last date", "start date", "notification date", "exam date", "admit card"]):
                if not data["dates"]: data["dates"] = lis
            elif any(k in block for k in ["general", "obc", "sc / st", "application fee", "no fee", "payment mode"]):
                if not data["fees"]: data["fees"] = lis
    except Exception as e:
        pass

    # 2. Age Details
    try:
        for p in soup.find_all(['p', 'div', 'td', 'li']):
            raw_t = clean_text(p.get_text(separator=' '))
            tl = raw_t.lower()
            if "minimum age" in tl and "maximum age" in tl and len(raw_t) < 500:
                raw_t = re.sub(r'Download.*?App.*?', '', raw_t, flags=re.IGNORECASE)
                data["age_text"] = safe_escape(raw_t)
                break
    except Exception as e:
        pass

    # 3. Vacancy & Eligibility Tables
    try:
        extracted_tables = []
        for tbl in soup.find_all('table'):
            tbl_text = clean_text(tbl.get_text()).lower()
            if "important links" in tbl_text or "apply online" in tbl_text:
                if not any(k in tbl_text for k in ["post name", "total post", "vacancy details"]):
                    continue

            if any(k in tbl_text for k in ["vacancy details", "post name", "no. of post", "eligibility", "total post"]):
                clean_table_rows = []
                for tr in tbl.find_all('tr'):
                    tr_text_low = clean_text(tr.get_text()).lower()
                    if any(bad in tr_text_low for bad in ["apply online", "download notification", "official website", "click here", "join telegram", "whatsapp"]):
                        continue
                    cells = tr.find_all(['th', 'td'])
                    if not cells: continue
                    is_head = any(c.name == 'th' for c in cells) or "post name" in tr_text_low or "eligibility" in tr_text_low
                    row_html = "<tr>"
                    for cell in cells:
                        ct = safe_escape(cell.get_text())
                        if is_head:
                            row_html += f"<th style='background:#f4f4f4; border:1px solid #999; padding:8px; font-size:13.5px;'>{ct}</th>"
                        else:
                            row_html += f"<td style='border:1px solid #999; padding:8px; font-size:13px;'>{ct}</td>"
                    row_html += "</tr>"
                    clean_table_rows.append(row_html)
                if len(clean_table_rows) > 1:
                    extracted_tables.append("<table style='width:100%; border-collapse:collapse; margin-bottom:15px; border:1px solid #999;'>" + "".join(clean_table_rows) + "</table>")
        if extracted_tables:
            data["vacancy_tables_html"] = "".join(extracted_tables[:3])
    except Exception as e:
        pass

    # 4. Multi-Link Extractor
    found_links = []
    seen_entries = set()

    def add_link_entry(label_text, raw_href):
        if not raw_href: return
        full_u = fix_relative_url(url, raw_href)
        ul = full_u.lower()
        ll = label_text.lower()

        bad_domains = [
            "whatsapp.com", "t.me", "telegram.me", "telegram.org",
            "facebook.com", "instagram.com", "twitter.com", "youtube.com",
            "play.google.com", "apple.com", "javascript:", "mailto:"
        ]
        if any(b in ul for b in bad_domains) or full_u.endswith("#"):
            return
        if any(b in ll for b in ["telegram", "whatsapp", "app", "channel", "follow", "join", "sarkari result", "sarkariresult"]):
            return

        clean_lbl = safe_escape(re.sub(r'(click here|link|download|check)$', '', label_text, flags=re.IGNORECASE).strip(" :-|"))
        if not clean_lbl or len(clean_lbl) < 3:
            clean_lbl = safe_escape(label_text)

        key = f"{clean_lbl.lower()}|{full_u}"
        if key not in seen_entries:
            seen_entries.add(key)
            found_links.append({"label": clean_lbl, "url": full_u})

    try:
        for tr in soup.find_all('tr'):
            cells = tr.find_all(['td', 'th'])
            if len(cells) >= 2:
                left_label = clean_text(cells[0].get_text())
                left_low = left_label.lower()
                important_keywords = [
                    "apply", "online", "registration", "login", "notification", "advt",
                    "advertisement", "official", "website", "admit card", "result",
                    "answer key", "syllabus", "cutoff", "cut off", "score", "admit"
                ]
                if any(k in left_low for k in important_keywords) and len(left_label) < 95:
                    row_anchors = []
                    for c in cells[1:]:
                        row_anchors.extend(c.find_all('a', href=True))

                    if len(row_anchors) == 1:
                        add_link_entry(left_label, row_anchors[0]['href'])
                    elif len(row_anchors) > 1:
                        for idx, a in enumerate(row_anchors[:4]):
                            sub_txt = clean_text(a.get_text())
                            if sub_txt and sub_txt.lower() not in ["click here", "link", "here"]:
                                combined_lbl = f"{left_label} ({sub_txt})"
                            else:
                                combined_lbl = f"{left_label} (Link {idx+1})"
                            add_link_entry(combined_lbl, a['href'])

        if len(found_links) < 2:
            for a in soup.find_all('a', href=True):
                at = clean_text(a.get_text())
                atl = at.lower()
                ah = a['href'].strip()
                if any(k in atl for k in ["apply online", "notification", "official website", "admit card", "result", "answer key"]):
                    if len(at) < 70:
                        add_link_entry(at, ah)
    except Exception as e:
        pass

    if not found_links:
        found_links.append({"label": "Official Notification & Direct Link", "url": url})

    data["links"] = found_links[:10]
    return data

def build_accurate_html(title, category_name, parsed, fallback_source_url="", border_color="#8b0000"):
    clean_title = safe_escape(title)
    banner_header = generate_banner_html(title, border_color)

    dates = parsed.get("dates", [])
    dates_html = "".join([f"<li style='margin-bottom:6px;'>{d}</li>" for d in dates[:6]]) if dates else "<li style='margin-bottom:6px;'>Status: Active Notification Released</li><li style='margin-bottom:6px;'>Last Date: Check Official Notice</li>"

    fees = parsed.get("fees", [])
    fees_html = "".join([f"<li style='margin-bottom:6px;'>{f}</li>" for f in fees[:6]]) if fees else "<li style='margin-bottom:6px;'>Application Fee: As per official advertisement</li>"

    age_content = parsed.get("age_text") or "Candidate must check minimum & maximum age criteria in the official recruitment advertisement."
    vacancy_section = f"<div style='background:{border_color}; color:#fff; text-align:center; padding:8px; font-weight:bold; margin-top:15px;'>Vacancy Details &amp; Eligibility</div>" + parsed["vacancy_tables_html"] if parsed.get("vacancy_tables_html") else ""

    links = parsed.get("links", [])
    if not links and fallback_source_url:
        links = [{"label": "Official Notification & Direct Link", "url": fallback_source_url}]

    link_rows = ""
    for lk in links:
        btn_color = "#0056b3" if "official" in lk['label'].lower() else ("#d35400" if "notification" in lk['label'].lower() or "pdf" in lk['label'].lower() else "#28a745")
        link_rows += f"<tr><td style='border:1px solid #999; padding:10px; font-weight:bold;'>{lk['label']}</td><td style='border:1px solid #999; padding:10px; text-align:center;'><a href='{lk['url']}' target='_blank' rel='noopener noreferrer' style='background:{btn_color}; color:#fff; padding:7px 16px; font-weight:bold; border-radius:3px; text-decoration:none; display:inline-block;'>Click Here</a></td></tr>"

    return f"""
    <div style='font-family: Arial, sans-serif; line-height: 1.5; max-width: 900px; margin: 0 auto; border: 2px solid {border_color}; padding: 12px; background: #fff;'>
      {banner_header}
      <div style='background-color: {border_color}; color: #fff; text-align: center; padding: 12px; font-size: 20px; font-weight: bold;'>{clean_title}</div>
      <p style='font-size: 14px; line-height: 1.7; color: #333; margin: 15px 0; padding: 12px; border-left: 4px solid {border_color}; background: #fafafa;'>
        <strong>{clean_title}:</strong> Government and recruitment authorities have officially published this notification. Candidates can check key eligibility details, age limit, application fee schedule, and access direct vacancy links below.
      </p>
      <table style='width: 100%; border-collapse: collapse; margin-bottom: 15px; border: 1px solid #999;'>
        <tr>
          <td style='width: 50%; vertical-align: top; padding: 10px; border-right: 1px solid #999; background: #fafafa;'>
            <div style='color: {border_color}; font-weight: bold; font-size: 15px; border-bottom: 2px solid {border_color}; margin-bottom: 8px;'>Important Dates</div>
            <ul style='padding-left: 18px; margin: 0; font-size: 13px; line-height: 1.8;'>{dates_html}</ul>
          </td>
          <td style='width: 50%; vertical-align: top; padding: 10px; background: #fafafa;'>
            <div style='color: #004085; font-weight: bold; font-size: 15px; border-bottom: 2px solid #004085; margin-bottom: 8px;'>Application Fee</div>
            <ul style='padding-left: 18px; margin: 0; font-size: 13px; line-height: 1.8;'>{fees_html}</ul>
          </td>
        </tr>
      </table>
      <div style='padding: 10px; background: #fffcf0; border: 1px solid #999; margin-bottom: 15px;'>
        <div style='color: #856404; font-weight: bold; font-size: 15px; margin-bottom: 6px;'>Age Limit &amp; Eligibility Summary</div>
        <p style='margin: 0; font-size: 13px; color: #222;'>{age_content}</p>
      </div>
      {vacancy_section}
      <div style='background-color: {border_color}; color: #fff; text-align: center; padding: 8px; font-size: 17px; font-weight: bold;'>Important Links</div>
      <table style='width: 100%; border-collapse: collapse; font-size: 14px; border: 1px solid #999;'>{link_rows}</table>
    </div>
    """

# ==================== YEAR & RELEVANCE FILTER (FIXES 2025 BUG) ====================
def is_valid_real_job(title, href):
    t_clean = clean_text(title)
    tl = t_clean.lower()
    hl = href.lower()

    if len(t_clean) < 14:
        return False

    # 1. STRICT YEAR FILTER (Blocks 2025, 2024, etc.)
    outdated_years = ["2025", "2024", "2023", "2022", "2021", "2020"]
    if any(y in tl for y in outdated_years) or any(f"-{y}" in hl or f"_{y}" in hl for y in outdated_years):
        return False

    # 2. BLOCKED SYSTEM LINKS
    forbidden_tokens = [
        "sarkari result", "sarkariresult", "skip to content",
        "result tools", "tools", "instagram", "telegram", "whatsapp",
        "facebook", "twitter", "youtube", "contact us", "privacy policy",
        "disclaimer", "about us", "admission", "view more", "home"
    ]
    if any(bad in tl for bad in forbidden_tokens):
        return False

    unwanted_url_slugs = ["/tools", "/p/", "privacy-policy", "disclaimer", "contact-us", "about-us", "/category/"]
    if any(bad in hl for bad in unwanted_url_slugs):
        return False

    return True

def extract_all_categories_from_homepage(soup):
    cat_map = {"Result": [], "Admit Card": [], "Latest Jobs": [], "Answer Key": [], "Syllabus": []}

    for a in soup.find_all('a', href=True):
        t = clean_text(a.get_text())
        h = a['href'].strip()

        if h.startswith('/'): h = f"https://sarkariresult.com.cm{h}"
        elif not h.startswith('http'): h = f"https://sarkariresult.com.cm/{h}"

        if not is_valid_real_job(t, h):
            continue

        tl, hl = t.lower(), h.lower()

        # 1. Answer Key Priority Check
        if "answer key" in tl or "ans key" in tl or "/answer-key" in hl:
            if not any(x[0] == t for x in cat_map["Answer Key"]): 
                cat_map["Answer Key"].append((t, h))

        # 2. Syllabus Priority Check
        elif "syllabus" in tl or "/syllabus" in hl:
            if not any(x[0] == t for x in cat_map["Syllabus"]): 
                cat_map["Syllabus"].append((t, h))

        # 3. Result Priority Check
        elif any(k in tl for k in ["result", "marks", "score card", "merit list"]) or "/result" in hl:
            if not any(x[0] == t for x in cat_map["Result"]): 
                cat_map["Result"].append((t, h))

        # 4. Strict Admit Card Check (Sirf Admit Card / Hall Ticket hona chahiye)
        elif any(k in tl for k in ["admit card", "hall ticket", "call letter"]) or "/admit" in hl:
            # Agar 'exam date' ke sath 'admit card' nahi likha hai, toh ye admit card nahi hai
            if not any(x[0] == t for x in cat_map["Admit Card"]): 
                cat_map["Admit Card"].append((t, h))

        # 5. Latest Jobs (Exam Date, Online Form, Recruitment, Vacancy etc.)
        else:
            if not any(x[0] == t for x in cat_map["Latest Jobs"]): 
                cat_map["Latest Jobs"].append((t, h))

    return cat_map

# ==================== MAIN EXECUTION ====================
def run():
    print(f"Connecting to Blogger API (Blog ID: {BLOG_ID})...")
    service = get_blogger_service()

    posts_res = service.posts().list(blogId=BLOG_ID, status=['DRAFT', 'LIVE'], maxResults=300).execute()
    # Sirf EXACT title comparison rakhenge taaki 'Exam Date' ke baad 'Admit Card' aane par block na ho
    existing_titles_exact = {clean_text(p.get('title', '')).lower() for p in posts_res.get('items', [])}
    print(f"Loaded {len(existing_titles_exact)} existing posts from Blogger.")

    published_cache = load_published_cache()
    print(f"Loaded {len(published_cache)} cached URLs.")

    total_created = 0

    print("\nFetching Live Updates from Primary Portal (sarkariresult.com.cm)...")
    url = f"https://sarkariresult.com.cm/?_t={int(time.time())}"
    try:
        r = SESSION.get(url, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            extracted_data = extract_all_categories_from_homepage(soup)
            
            # Prioritize Admit Card & Result updates first!
            category_settings = [
                {"key": "Admit Card", "label": "Admit Card", "color": "#004085", "limit": 6},
                {"key": "Result", "label": "Result", "color": "#b30000", "limit": 6},
                {"key": "Latest Jobs", "label": "Latest Jobs", "color": "#155724", "limit": 6},
                {"key": "Answer Key", "label": "Answer Key", "color": "#6f42c1", "limit": 4},
                {"key": "Syllabus", "label": "Syllabus", "color": "#d35400", "limit": 4}
            ]

            for cat in category_settings:
                raw_items = extracted_data.get(cat["key"], [])
                new_items = []
                for title, link in raw_items:
                    clean_t = clean_text(title)
                    t_low = clean_t.lower()

                    # Exact Title aur Exact URL check (Allows 'Admit Card' even if 'Exam Date' was published earlier)
                    if link not in published_cache and t_low not in existing_titles_exact:
                        new_items.append((clean_t, link))

                if not new_items:
                    continue

                for title, link in new_items[:cat["limit"]]:
                    print(f"  [Publishing Fresh Update] {title}")
                    parsed = parse_full_job_page(link)
                    content_html = build_accurate_html(title, cat['label'], parsed, fallback_source_url=link, border_color=cat['color'])
                    seo_desc = f"{title}: Check notification, dates, eligibility and direct links."[:150]

                    body = {
                        "title": title,
                        "content": content_html,
                        "labels": [cat['label']],
                        "searchDescription": seo_desc
                    }

                    try:
                        created = service.posts().insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
                        print(f"  -> SUCCESS: {created.get('title')}")
                        published_cache.add(link)
                        existing_titles_exact.add(title.lower())
                        total_created += 1
                        time.sleep(2)
                    except Exception as e:
                        print(f"  -> Insert Error: {e}")
                        break
        else:
            print(f"Target source HTTP Status: {r.status_code}")
    except Exception as e:
        print(f"Scraper error: {e}")

    save_published_cache(published_cache)

    print(f"\n==========================================")
    print(f"COMPLETED! Fresh 2026 Posts Published: {total_created}")
    print(f"Total Unique URLs in Cache: {len(published_cache)}")
    print(f"==========================================")

if __name__ == "__main__":
    run()
