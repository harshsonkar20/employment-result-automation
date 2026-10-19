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

# ==================== STRICT ZERO-TOLERANCE FILTER ====================
def is_valid_real_job(title, href):
    t = clean_text(title)
    tl = t.lower()
    hl = href.lower()

    # 1. Reject Short or Junk Nav Strings
    if len(t) < 16 or len(t.split()) < 3:
        return False

    # 2. Permanent Blacklist for Menu/Static items
    junk_exact = [
        "skip to content", "sarkariresult.com.cm", "sarkari result", "bihar police result",
        "up police result", "delhi police result", "mp police result", "police result",
        "view more", "click here", "home", "contact us", "privacy policy", "disclaimer",
        "about us", "tools", "admission", "certificate verification"
    ]
    if any(j in tl for j in junk_exact) or tl in junk_exact:
        return False

    # 3. Strict Outdated Year Filter (Blocks 2025, 2024, etc.)
    outdated = ["2025", "2024", "2023", "2022", "2021", "2020"]
    if any(y in tl for y in outdated) or any(f"-{y}" in hl or f"_{y}" in hl for y in outdated):
        return False

    # 4. Block Navigation or Category URLs
    if any(bad in hl for bad in ["/category/", "/tag/", "/tools", "/p/", "privacy-policy", "disclaimer"]):
        return False

    return True

# ==================== CATEGORY CLASSIFIER ====================
def determine_correct_category(title, href, source_box_hint=""):
    tl = title.lower()
    hl = href.lower()

    # Priority 1: Answer Key
    if "answer key" in tl or "ans key" in tl or "/answer-key" in hl:
        return "Answer Key"

    # Priority 2: Syllabus
    if "syllabus" in tl or "/syllabus" in hl:
        return "Syllabus"

    # Priority 3: Form / Recruitment Keywords -> ALWAYS "Latest Jobs"
    # (Yeh rule JSSC Online form ya kisi bhi 'Last Date' ko Admit Card me jane se rokega)
    if any(k in tl for k in ["online form", "apply online", "recruitment", "vacancy", "post online", "bharti", "exam date"]):
        if "admit card" not in tl and "hall ticket" not in tl:
            return "Latest Jobs"

    # Priority 4: Admit Card (STRICT)
    if any(k in tl for k in ["admit card", "hall ticket", "call letter"]) or "/admit" in hl:
        return "Admit Card"

    # Priority 5: Result (STRICT)
    if any(k in tl for k in ["result", "marks", "score card", "merit list"]) or "/result" in hl:
        return "Result"

    # Fallback to Box Hint or Latest Jobs
    if source_box_hint in ["Result", "Admit Card", "Latest Jobs", "Answer Key", "Syllabus"]:
        return source_box_hint

    return "Latest Jobs"

# ==================== POST BODY GENERATOR ====================
def build_clean_post_html(title, category_name, link):
    clean_t = safe_escape(title)
    color_map = {
        "Result": "#dc2626",
        "Admit Card": "#2563eb",
        "Latest Jobs": "#16a34a",
        "Answer Key": "#9333ea",
        "Syllabus": "#ea580c"
    }
    theme_color = color_map.get(category_name, "#2563eb")

    return f"""
    <div style='font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; max-width:850px; margin:0 auto; border:1px solid #e2e8f0; border-radius:12px; overflow:hidden; background:#ffffff;'>
      <div style='background:{theme_color}; color:#ffffff; padding:18px; text-align:center;'>
        <div style='font-size:13px; font-weight:bold; letter-spacing:1px; text-transform:uppercase;'>★ {SITE_BRAND_NAME} NOTIFICATION ★</div>
        <h1 style='font-size:22px; margin:10px 0 0 0; font-weight:800;'>{clean_t}</h1>
      </div>
      <div style='padding:22px;'>
        <p style='font-size:14.5px; line-height:1.7; color:#334155; margin-bottom:20px; background:#f8fafc; padding:14px; border-left:4px solid {theme_color}; border-radius:4px;'>
          <strong>{clean_t}:</strong> Recruitment and exam conducting authorities have released this official notice. Check schedule details, eligibility criteria, and use verified portal links below.
        </p>
        <div style='background:{theme_color}; color:#ffffff; padding:10px 14px; font-weight:bold; font-size:16px; border-radius:6px; margin-bottom:12px;'>
          Official Important Links
        </div>
        <table style='width:100%; border-collapse:collapse; margin-bottom:20px;'>
          <tr style='border-bottom:1px solid #e2e8f0;'>
            <td style='padding:14px 10px; font-weight:700; color:#0f172a;'>Official Notification &amp; Application Portal</td>
            <td style='padding:14px 10px; text-align:right;'>
              <a href='{link}' target='_blank' rel='noopener noreferrer' style='background:{theme_color}; color:#ffffff; padding:8px 18px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:13.5px; display:inline-block;'>Open Direct Portal &#8599;</a>
            </td>
          </tr>
        </table>
        <div style='padding:14px; background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px;'>
          <p style='margin:0; font-size:13.5px; color:#1e40af; line-height:1.5;'>
            &#128204; <strong>Note:</strong> Online form apply karne se pehle official PDF circular zaroor padhein.
          </p>
        </div>
      </div>
    </div>
    """

# ==================== MAIN CRAWLER PIPELINE ====================
def run():
    print(f"Connecting to Blogger API (Blog ID: {BLOG_ID})...")
    service = get_blogger_service()

    posts_res = service.posts().list(blogId=BLOG_ID, status=['DRAFT', 'LIVE'], maxResults=300).execute()
    existing_titles = {clean_text(p.get('title', '')).lower() for p in posts_res.get('items', [])}
    print(f"Loaded {len(existing_titles)} existing posts.")

    published_cache = load_published_cache()
    print(f"Loaded {len(published_cache)} cached records.")

    print("\nFetching Live Updates from sarkariresult.com.cm...")
    url = f"https://sarkariresult.com.cm/?_t={int(time.time())}"
    r = SESSION.get(url, timeout=12)
    if r.status_code != 200:
        print(f"Failed to fetch source: HTTP {r.status_code}")
        return

    soup = BeautifulSoup(r.text, 'html.parser')
    candidates = []

    # Har anchor ko inspect karein
    for a in soup.find_all('a', href=True):
        t = clean_text(a.get_text())
        h = a['href'].strip()

        if not h.startswith("http"):
            h = f"https://sarkariresult.com.cm/{h.lstrip('/')}"

        # Hard validation
        if not is_valid_real_job(t, h):
            continue

        tl = t.lower()
        if t.lower() in existing_titles or h in published_cache:
            continue

        # Correct Category Classification
        cat = determine_correct_category(t, h)
        candidates.append({"title": t, "url": h, "category": cat})

    print(f"Discovered {len(candidates)} fresh & clean posts for 2026.")

    # Deduplicate in batch
    seen_in_run = set()
    unique_candidates = []
    for c in candidates:
        if c['title'].lower() not in seen_in_run:
            seen_in_run.add(c['title'].lower())
            unique_candidates.append(c)

    # Publish up to 6 fresh posts per execution to keep quota & index safe
    published_count = 0
    for item in unique_candidates[:8]:
        title = item["title"]
        cat = item["category"]
        link = item["url"]

        print(f"Publishing -> [{cat}] {title}")
        html_content = build_clean_post_html(title, cat, link)
        seo_desc = f"{title}: Check notification details, eligibility and official portal links."[:150]

        body = {
            "title": title,
            "content": html_content,
            "labels": [cat],
            "searchDescription": seo_desc
        }

        try:
            service.posts().insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
            print("  ✔ Successfully Published!")
            published_cache.add(link)
            existing_titles.add(title.lower())
            published_count += 1
            time.sleep(2)
        except Exception as e:
            print(f"  ✖ Publish Error: {e}")
            break

    save_published_cache(published_cache)
    print(f"\nCompleted! Total fresh posts published: {published_count}")

if __name__ == "__main__":
    run()
