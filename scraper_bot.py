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

def generate_banner_html(title, bg_color="#0f172a"):
    clean_t = safe_escape(title)
    line1 = clean_t[:55]
    line2 = clean_t[55:110] if len(clean_t) > 55 else ""
    return f"""
    <div style="text-align: center; margin-bottom: 20px;">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 380" style="width: 100%; max-width: 800px; height: auto; border-radius: 8px;">
        <rect width="800" height="380" fill="{bg_color}" rx="8"/>
        <text x="400" y="44" fill="#ffffff" font-size="22" font-family="Arial, sans-serif" font-weight="bold" text-anchor="middle">★ {SITE_BRAND_NAME} NOTIFICATION ★</text>
        <rect x="250" y="85" width="300" height="36" rx="18" fill="#ffcc00"/>
        <text x="400" y="108" fill="#000000" font-size="14" font-family="Arial, sans-serif" font-weight="bold" text-anchor="middle">OFFICIAL UPDATE</text>
        <text x="400" y="180" fill="#ffffff" font-size="22" font-family="Arial, sans-serif" font-weight="bold" text-anchor="middle">{line1}</text>
        <text x="400" y="220" fill="#ffffff" font-size="20" font-family="Arial, sans-serif" font-weight="bold" text-anchor="middle">{line2}</text>
      </svg>
    </div>
    """

def parse_full_job_page(url):
    data = {"dates": [], "fees": [], "age_text": "", "links": [], "vacancy_tables_html": ""}
    try:
        r = SESSION.get(url, timeout=8)
        if r.status_code != 200:
            data["links"] = [{"label": "Official Notification Link", "url": url}]
            return data
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception:
        data["links"] = [{"label": "Official Notification Link", "url": url}]
        return data

    try:
        for ul in soup.find_all('ul'):
            lis = [safe_escape(li.get_text()) for li in ul.find_all('li')]
            b = " ".join(lis).lower()
            if any(k in b for k in ["application begin", "last date", "start date", "exam date"]):
                if not data["dates"]: data["dates"] = lis
            elif any(k in b for k in ["general", "obc", "sc / st", "fee"]):
                if not data["fees"]: data["fees"] = lis
    except Exception:
        pass

    try:
        for p in soup.find_all(['p', 'div', 'td']):
            raw_t = clean_text(p.get_text())
            if "minimum age" in raw_t.lower() and len(raw_t) < 400:
                data["age_text"] = safe_escape(raw_t)
                break
    except Exception:
        pass

    found_links = []
    try:
        for tr in soup.find_all('tr'):
            cells = tr.find_all(['td', 'th'])
            if len(cells) >= 2:
                lbl = clean_text(cells[0].get_text())
                if any(k in lbl.lower() for k in ["apply", "notification", "official", "admit", "result", "answer"]):
                    a = cells[1].find('a', href=True)
                    if a and a['href'].startswith('http'):
                        found_links.append({"label": safe_escape(lbl), "url": a['href']})
    except Exception:
        pass

    if not found_links:
        found_links.append({"label": "Official Notification & Details", "url": url})
    data["links"] = found_links[:6]
    return data

def build_html(title, cat, parsed, border_color="#2563eb"):
    clean_title = safe_escape(title)
    dates_html = "".join([f"<li>{d}</li>" for d in parsed.get("dates", [])[:5]]) or "<li>Status: Active Update</li>"
    fees_html = "".join([f"<li>{f}</li>" for f in parsed.get("fees", [])[:5]]) or "<li>As per official rules</li>"
    
    link_rows = ""
    for lk in parsed.get("links", []):
        link_rows += f"<tr><td style='border:1px solid #ddd; padding:10px; font-weight:bold;'>{lk['label']}</td><td style='border:1px solid #ddd; padding:10px; text-align:center;'><a href='{lk['url']}' target='_blank' style='background:{border_color}; color:#fff; padding:6px 14px; text-decoration:none; border-radius:4px; font-weight:bold;'>Click Here</a></td></tr>"

    return f"""
    <div style='font-family: Arial, sans-serif; max-width:850px; margin:0 auto; border:1px solid #ddd; padding:15px;'>
      {generate_banner_html(title, border_color)}
      <h2 style='background:{border_color}; color:#fff; text-align:center; padding:10px; font-size:18px;'>{clean_title}</h2>
      <table style='width:100%; border-collapse:collapse; margin:15px 0;'>
        <tr>
          <td style='width:50%; vertical-align:top; padding:10px; border:1px solid #ddd;'>
            <b style='color:{border_color};'>Important Dates:</b>
            <ul style='padding-left:18px; margin-top:5px;'>{dates_html}</ul>
          </td>
          <td style='width:50%; vertical-align:top; padding:10px; border:1px solid #ddd;'>
            <b style='color:#0f172a;'>Application Fee:</b>
            <ul style='padding-left:18px; margin-top:5px;'>{fees_html}</ul>
          </td>
        </tr>
      </table>
      <div style='padding:10px; background:#f8fafc; border:1px solid #ddd; margin-bottom:15px;'>
        <b>Age Limit & Eligibility:</b>
        <p style='margin:5px 0 0 0;'>{parsed.get("age_text") or "Check official notification PDF."}</p>
      </div>
      <h3 style='background:#0f172a; color:#fff; text-align:center; padding:8px; font-size:16px;'>Important Links</h3>
      <table style='width:100%; border-collapse:collapse;'>{link_rows}</table>
    </div>
    """

def is_valid(title, href):
    tl = title.lower()
    # 2025 block rule
    if any(y in tl for y in ["2025", "2024", "2023"]):
        return False
    if len(title) < 14:
        return False
    if any(b in tl for b in ["sarkari result", "tools", "telegram", "whatsapp", "about us", "contact"]):
        return False
    return True

def run():
    print("Connecting to Blogger...")
    service = get_blogger_service()
    posts_res = service.posts().list(blogId=BLOG_ID, status=['DRAFT', 'LIVE'], maxResults=250).execute()
    existing_titles = {clean_text(p.get('title', '')).lower() for p in posts_res.get('items', [])}
    published_cache = load_published_cache()

    print("Fetching SarkariResult Directly (No Slow Govt Sites)...")
    url = f"https://sarkariresult.com.cm/?_t={int(time.time())}"
    r = SESSION.get(url, timeout=10)
    if r.status_code != 200:
        print("Failed to access source")
        return

    soup = BeautifulSoup(r.text, 'html.parser')
    cat_map = {"Admit Card": [], "Result": [], "Latest Jobs": []}

    for a in soup.find_all('a', href=True):
        t = clean_text(a.get_text())
        h = a['href'].strip()
        if not h.startswith("http"):
            h = f"https://sarkariresult.com.cm/{h.lstrip('/')}"
        
        if not is_valid(t, h):
            continue

        tl = t.lower()
        if "admit card" in tl or "hall ticket" in tl:
            cat_map["Admit Card"].append((t, h))
        elif "result" in tl or "score card" in tl:
            cat_map["Result"].append((t, h))
        else:
            cat_map["Latest Jobs"].append((t, h))

    total = 0
    settings = [
        ("Admit Card", "#2563eb", 5),
        ("Result", "#dc2626", 5),
        ("Latest Jobs", "#16a34a", 5)
    ]

    for label, color, limit in settings:
        items = cat_map.get(label, [])
        for title, link in items:
            if total >= 8: break
            if link in published_cache or title.lower() in existing_titles:
                continue

            print(f"Publishing: {title} [{label}]")
            parsed = parse_full_job_page(link)
            body = {
                "title": title,
                "content": build_html(title, label, parsed, color),
                "labels": [label],
                "searchDescription": f"{title} Notification, Exam Dates and Links."[:150]
            }

            try:
                service.posts().insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
                print(" -> Published!")
                published_cache.add(link)
                existing_titles.add(title.lower())
                total += 1
                time.sleep(1)
            except Exception as e:
                print(f"Error publishing: {e}")
                break

    save_published_cache(published_cache)
    print(f"Finished! Total fresh posts: {total}")

if __name__ == "__main__":
    run()
