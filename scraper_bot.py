import os
import re
import html
import json
import time
import requests
from bs4 import BeautifulSoup
import urllib3
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

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
        cache_list = list(cache_set)[-800:]
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

def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', str(text)).strip()

def safe_escape(text):
    return html.escape(clean_text(text), quote=True)

def fix_relative_url(base_url, link_url):
    if not link_url: return ""
    u = link_url.strip()
    if u.startswith("http://") or u.startswith("https://"): return u
    if u.startswith("//"): return "https:" + u
    m = re.match(r'^(https?://[^/]+)', base_url)
    domain = m.group(1) if m else "https://sarkariresult.com.cm"
    if u.startswith("/"): return domain + u
    return domain + "/" + u

def generate_banner_html(title, bg_color="#004085"):
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
        r = SESSION.get(url, timeout=12)
        if r.status_code != 200:
            return data
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception:
        return data

    # 1. Dates & Fees
    try:
        for ul in soup.find_all('ul'):
            lis = [safe_escape(li.get_text()) for li in ul.find_all('li')]
            b = " ".join(lis).lower()
            if any(k in b for k in ["application begin", "last date", "start date", "exam date"]):
                if not data["dates"]: data["dates"] = lis
            elif any(k in b for k in ["general", "obc", "sc / st", "fee", "payment mode"]):
                if not data["fees"]: data["fees"] = lis
    except Exception:
        pass

    # 2. Age Details
    try:
        for p in soup.find_all(['p', 'div', 'td']):
            raw_t = clean_text(p.get_text(separator=' '))
            tl = raw_t.lower()
            if "minimum age" in tl and "maximum age" in tl and len(raw_t) < 500:
                raw_t = re.sub(r'Download.*?App.*?', '', raw_t, flags=re.IGNORECASE)
                data["age_text"] = safe_escape(raw_t)
                break
    except Exception:
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
    except Exception:
        pass

    # 4. Official Direct Links Extraction (Filter out Competitor Redirects)
    found_links = []
    seen = set()

    for tr in soup.find_all('tr'):
        cells = tr.find_all(['td', 'th'])
        if len(cells) >= 2:
            left_lbl = clean_text(cells[0].get_text())
            left_low = left_lbl.lower()
            important = ["apply", "notification", "official website", "admit card", "result", "answer key", "syllabus", "registration", "login"]
            if any(k in left_low for k in important) and len(left_lbl) < 80:
                for a in cells[1].find_all('a', href=True):
                    full_u = fix_relative_url(url, a['href'])
                    
                    # SarkariResult internal URLs aur social links block karein
                    if any(bad in full_u.lower() for bad in ["sarkariresult.com.cm", "t.me", "telegram", "whatsapp", "play.google.com"]):
                        continue

                    lbl = safe_escape(re.sub(r'click here|download|link', '', left_lbl, flags=re.IGNORECASE).strip(" :-|"))
                    if not lbl or len(lbl) < 3: lbl = safe_escape(left_lbl)
                    
                    if full_u not in seen:
                        seen.add(full_u)
                        found_links.append({"label": lbl, "url": full_u})

    data["links"] = found_links[:8]
    return data

def build_accurate_html(title, category_name, parsed, border_color="#004085"):
    clean_title = safe_escape(title)
    banner_header = generate_banner_html(title, border_color)

    dates = parsed.get("dates", [])
    dates_html = "".join([f"<li style='margin-bottom:6px;'>{d}</li>" for d in dates[:6]]) if dates else "<li style='margin-bottom:6px;'>Status: Active Notification Released</li><li style='margin-bottom:6px;'>Last Date: Check Official Notice</li>"

    fees = parsed.get("fees", [])
    fees_html = "".join([f"<li style='margin-bottom:6px;'>{f}</li>" for f in fees[:6]]) if fees else "<li style='margin-bottom:6px;'>Application Fee: As per official advertisement</li>"

    age_content = parsed.get("age_text") or "Candidate must check minimum & maximum age criteria in the official recruitment advertisement."
    vacancy_section = f"<div style='background:{border_color}; color:#fff; text-align:center; padding:8px; font-weight:bold; margin-top:15px;'>Vacancy Details &amp; Eligibility</div>" + parsed["vacancy_tables_html"] if parsed.get("vacancy_tables_html") else ""

    links = parsed.get("links", [])
    link_rows = ""
    for lk in links:
        btn_color = "#0056b3" if "official" in lk['label'].lower() else ("#d35400" if "notification" in lk['label'].lower() or "pdf" in lk['label'].lower() else "#28a745")
        link_rows += f"<tr><td style='border:1px solid #999; padding:10px; font-weight:bold;'>{lk['label']}</td><td style='border:1px solid #999; padding:10px; text-align:center;'><a href='{lk['url']}' target='_blank' rel='noopener noreferrer' style='background:{btn_color}; color:#fff; padding:7px 16px; font-weight:bold; border-radius:3px; text-decoration:none; display:inline-block;'>Click Here</a></td></tr>"

    if not link_rows:
        link_rows = f"<tr><td style='border:1px solid #999; padding:10px; font-weight:bold;'>Official Notification</td><td style='border:1px solid #999; padding:10px; text-align:center;'><span style='color:#666;'>Direct Circular In Official Release</span></td></tr>"

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

# ==================== DEDICATED CATEGORY EXTRACTOR ====================
def fetch_category_links(cat_url):
    results = []
    try:
        r = SESSION.get(cat_url, timeout=12)
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception:
        return results

    for a in soup.find_all('a', href=True):
        t = clean_text(a.get_text())
        h = a['href'].strip()

        if not h.startswith("http"):
            h = f"https://sarkariresult.com.cm/{h.lstrip('/')}"

        tl = t.lower()
        # Clean Junk Filters
        if len(t) < 14 or "2025" in tl or "2024" in tl: continue
        if any(bad in tl for bad in ["view more", "click here", "sarkari result", "skip to content", "privacy policy", "disclaimer"]): continue
        if any(bad in h.lower() for bad in ["/category/", "/tag/", "/p/", "/tools"]): continue

        results.append((t, h))
    return results

# ==================== MAIN EXECUTION ====================
def run():
    print(f"Connecting to Blogger API (Blog ID: {BLOG_ID})...")
    service = get_blogger_service()

    posts_res = service.posts().list(blogId=BLOG_ID, status=['LIVE'], maxResults=300).execute()
    existing_titles = {clean_text(p.get('title', '')).lower() for p in posts_res.get('items', [])}
    print(f"Loaded {len(existing_titles)} existing posts.")

    published_cache = load_published_cache()

    # HAR CATEGORY KA DEDICATED URL (NO GUESSING, NO MIXING)
    sources = [
        {"cat": "Latest Jobs", "url": "https://sarkariresult.com.cm/latest-jobs/", "color": "#155724", "limit": 6},
        {"cat": "Admit Card", "url": "https://sarkariresult.com.cm/admit-card/", "color": "#004085", "limit": 4},
        {"cat": "Result", "url": "https://sarkariresult.com.cm/result/", "color": "#b30000", "limit": 4},
        {"cat": "Answer Key", "url": "https://sarkariresult.com.cm/answer-key/", "color": "#6f42c1", "limit": 3},
        {"cat": "Syllabus", "url": "https://sarkariresult.com.cm/syllabus/", "color": "#d35400", "limit": 3}
    ]

    total_published = 0

    for s in sources:
        cat_name = s["cat"]
        print(f"\nScanning Dedicated Category: {cat_name} ({s['url']})...")
        items = fetch_category_links(s["url"])
        cat_count = 0

        for title, link in items:
            t_low = title.lower()
            if t_low in existing_titles or link in published_cache:
                continue

            print(f"Publishing -> [{cat_name}] {title}")
            parsed_data = parse_full_job_page(link)
            post_html = build_accurate_html(title, cat_name, parsed_data, border_color=s["color"])

            body = {
                "title": title,
                "content": post_html,
                "labels": [cat_name],
                "searchDescription": f"{title} official recruitment dates, eligibility and direct links."[:150]
            }

            try:
                service.posts().insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
                print("  ✔ Successfully Published!")
                published_cache.add(link)
                existing_titles.add(t_low)
                total_published += 1
                cat_count += 1
                time.sleep(2)

                if cat_count >= s["limit"]:
                    break
            except Exception as e:
                print(f"  ✖ Insert error: {e}")
                continue

    save_published_cache(published_cache)
    print(f"\nCompleted! Total fresh posts published: {total_published}")

if __name__ == "__main__":
    run()
