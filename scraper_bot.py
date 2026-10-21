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

# ==================== HELPERS & SANITIZATION ====================

def normalize_key(text):
    if not text:
        return ""
    return re.sub(r'[^a-zA-Z0-9]+', '', str(text).lower())

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
    # Remove competitor app advertisements & promotional banners
    t = re.sub(r'download\s+sarkariresult\s+app\s+now', '', t, flags=re.IGNORECASE)
    t = re.sub(r'sarkari\s*result(\.com|\.cm)?', SITE_BRAND_NAME, t, flags=re.IGNORECASE)
    t = re.sub(r'join\s+(our\s+)?(telegram|whatsapp)\s+channel.*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'follow\s+(our\s+)?(telegram|whatsapp).*', '', t, flags=re.IGNORECASE)
    return clean_text(t)

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

def generate_banner_html(title, bg_color="#004085"):
    clean_t = safe_escape(title)
    line1 = clean_t[:52]
    line2 = clean_t[52:104] if len(clean_t) > 52 else ""

    return f"""
    <div style="text-align: center; margin-bottom: 22px;">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 320" style="width: 100%; max-width: 800px; height: auto; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.12);">
        <defs>
          <linearGradient id="bannerGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:{bg_color};stop-opacity:1" />
            <stop offset="100%" style="stop-color:#0f172a;stop-opacity:1" />
          </linearGradient>
        </defs>
        <rect width="800" height="320" fill="url(#bannerGrad)" rx="10"/>
        <rect x="0" y="0" width="800" height="54" fill="rgba(0,0,0,0.3)"/>
        <text x="400" y="36" fill="#ffffff" font-size="20" font-family="'Segoe UI', Roboto, sans-serif" font-weight="700" text-anchor="middle" letter-spacing="2">
          ★ {SITE_BRAND_NAME} OFFICIAL UPDATE ★
        </text>
        <rect x="250" y="70" width="300" height="32" rx="16" fill="#facc15"/>
        <text x="400" y="91" fill="#1e293b" font-size="13" font-family="'Segoe UI', Roboto, sans-serif" font-weight="700" text-anchor="middle" letter-spacing="1">
          VERIFIED &amp; UPDATED CIRCULAR
        </text>
        <text x="400" y="160" fill="#ffffff" font-size="22" font-family="'Segoe UI', Roboto, sans-serif" font-weight="bold" text-anchor="middle">
          {line1}
        </text>
        <text x="400" y="195" fill="#e2e8f0" font-size="19" font-family="'Segoe UI', Roboto, sans-serif" font-weight="600" text-anchor="middle">
          {line2}
        </text>
        <rect x="0" y="265" width="800" height="55" fill="rgba(255,255,255,0.08)"/>
        <text x="400" y="298" fill="#cbd5e1" font-size="15" font-family="'Segoe UI', Roboto, sans-serif" font-weight="normal" text-anchor="middle">
          Direct Links, Eligibility Criteria, Schedule &amp; Official Notice Below
        </text>
      </svg>
    </div>
    """

# ==================== PARSER ENGINE ====================

def parse_full_job_page(url, post_title):
    data = {
        "title": post_title,
        "overview": "",
        "dates": [],
        "fees": [],
        "age_text": "",
        "vacancy_tables": [],
        "selection_process": "",
        "how_to_apply": [],
        "faqs": [],
        "links": []
    }

    try:
        r = SESSION.get(url, timeout=15)
        if r.status_code != 200:
            return data
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception:
        return data

    # 1. Clean out sidebars, footer, and navigation junk properly via CSS selectors
    for sel in ['aside', 'footer', 'nav', '.sidebar', '.widget', '#sidebar', '.wp-block-navigation']:
        for junk in soup.select(sel):
            junk.decompose()

    # 2. Extract Lead Overview / Short Details
    for p in soup.find_all('p'):
        pt = clean_text(p.get_text())
        if len(pt) > 50 and any(w in pt.lower() for w in ["released", "notification", "conducted", "recruitment", "invited", "exam date", "admit card", "result"]):
            if not any(bad in pt.lower() for bad in ["telegram", "whatsapp", "download app"]):
                data["overview"] = sanitize_brand_text(pt)
                break

    # 3. Extract Dates & Fees (from ULs or Two-Column Tables)
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

    # 4. Extract Age Limits & Cutoff Dates
    for el in soup.find_all(['p', 'div', 'td']):
        raw_t = clean_text(el.get_text(separator=' '))
        tl = raw_t.lower()
        if ("minimum age" in tl or "age limit" in tl) and len(raw_t) < 450:
            if not any(bad in tl for bad in ["telegram", "whatsapp"]):
                data["age_text"] = sanitize_brand_text(raw_t)
                break

    # 5. Extract Tables: Mode of Selection, How-to-Apply, FAQs, Vacancy/Eligibility, and Action Links
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

        # B. How to Apply / How to Fill / How to Check
        if any(h in tbl_text for h in ["how to fill", "how to apply", "how to check", "how to download"]):
            if not data["how_to_apply"]:
                steps = []
                for p in tbl.find_all(['p', 'li', 'td']):
                    st = sanitize_brand_text(p.get_text())
                    if len(st) > 25 and not any(h in st.lower() for h in ["how to fill", "how to apply", "how to check"]):
                        steps.append(st)
                data["how_to_apply"] = steps[:6]
            continue

        # C. FAQs (Question & Answer Table)
        if "important question" in tbl_text or "question:" in tbl_text:
            if not data["faqs"]:
                for r_el in rows:
                    txt = clean_text(r_el.get_text())
                    q_m = re.search(r'Question:\s*(.*?)\s*Answer:\s*(.*)', txt, flags=re.IGNORECASE)
                    if q_m:
                        data["faqs"].append({
                            "question": sanitize_brand_text(q_m.group(1)),
                            "answer": sanitize_brand_text(q_m.group(2))
                        })
            continue

        # D. Links Table
        if any(k in tbl_text for k in ["apply online", "download result", "admit card", "official website", "official notification", "answer key"]):
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

        # E. Vacancy / Eligibility / Post Breakdown Tables
        if any(bad in tbl_text for bad in ["whatsapp", "telegram", "you may also check", "latest posts"]):
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

# ==================== HTML GENERATOR (ADSENSE OPTIMIZED) ====================

def build_accurate_html(title, category_name, parsed, border_color="#0284c7"):
    clean_title = safe_escape(title)
    banner = generate_banner_html(title, border_color)

    # 1. Dynamic Overview Synopsis
    overview_text = parsed.get("overview", "")
    if not overview_text or len(overview_text) < 40:
        overview_text = f"Candidates preparing for central and state government recruitment exams can check the official details for <strong>{clean_title}</strong>. The recruitment authority has officially published the schedule, eligibility rules, and examination details. Read below for full information and verified direct action links."
    else:
        overview_text = safe_escape(overview_text)

    # 2. Two-Column Card: Important Dates & Application Fee
    dates = parsed.get("dates", [])
    fees = parsed.get("fees", [])
    dates_items = "".join([f"<li style='margin-bottom:8px;'><strong>✓</strong> {safe_escape(d)}</li>" for d in dates]) if dates else "<li>Check official circular</li>"
    fees_items = "".join([f"<li style='margin-bottom:8px;'><strong>₹</strong> {safe_escape(f)}</li>" for f in fees]) if fees else "<li>Refer to official notification</li>"

    dates_fees_section = f"""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin: 20px 0;">
      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-top: 4px solid {border_color}; border-radius: 8px; padding: 16px;">
        <h3 style="margin-top:0; margin-bottom:12px; color: {border_color}; font-size: 17px; font-weight: 700; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
          📅 Important Dates
        </h3>
        <ul style="list-style: none; padding-left: 0; margin: 0; font-size: 14px; line-height: 1.6; color: #334155;">
          {dates_items}
        </ul>
      </div>
      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-top: 4px solid #0f766e; border-radius: 8px; padding: 16px;">
        <h3 style="margin-top:0; margin-bottom:12px; color: #0f766e; font-size: 17px; font-weight: 700; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">
          💳 Application Fee &amp; Payment Mode
        </h3>
        <ul style="list-style: none; padding-left: 0; margin: 0; font-size: 14px; line-height: 1.6; color: #334155;">
          {fees_items}
        </ul>
      </div>
    </div>
    """

    # 3. Age Limit & Relaxation
    age_box = ""
    if parsed.get("age_text"):
        age_box = f"""
        <div style="background: #fffbeb; border: 1px solid #fef3c7; border-left: 4px solid #d97706; border-radius: 8px; padding: 16px; margin: 20px 0;">
          <h3 style="margin-top: 0; color: #b45309; font-size: 16px; font-weight: 700; margin-bottom: 8px;">
            ⚠️ Age Limit &amp; Relaxation Criteria
          </h3>
          <p style="margin: 0; font-size: 14px; color: #451a03; line-height: 1.6;">
            {safe_escape(parsed['age_text'])}
          </p>
        </div>
        """

    # 4. Vacancy Details & Eligibility
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

    # 5. Selection Process
    selection_section = ""
    if parsed.get("selection_process"):
        selection_section = f"""
        <div style="background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px; margin: 20px 0;">
          <h3 style="margin-top: 0; color: #0f172a; font-size: 16px; font-weight: 700; margin-bottom: 8px;">
            🎯 Selection Process / Mode of Selection
          </h3>
          <p style="margin: 0; font-size: 14px; color: #334155; line-height: 1.6; font-weight: 500;">
            {safe_escape(parsed['selection_process'])}
          </p>
        </div>
        """

    # 6. Step-by-Step Instructions Guide
    steps = parsed.get("how_to_apply", [])
    how_to_section = ""
    if steps:
        steps_html = "".join([f"<li style='margin-bottom:8px;'>{safe_escape(st)}</li>" for st in steps])
        how_to_section = f"""
        <div style="margin: 24px 0;">
          <h2 style="color: #0f172a; font-size: 18px; font-weight: 700; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-bottom: 12px;">
            📝 Step-by-Step Guide / Instructions
          </h2>
          <ol style="padding-left: 20px; font-size: 14px; line-height: 1.7; color: #334155;">
            {steps_html}
          </ol>
        </div>
        """

    # 7. Frequently Asked Questions (FAQs)
    faqs = parsed.get("faqs", [])
    faq_section = ""
    if faqs:
        faq_items = ""
        for fq in faqs:
            faq_items += f"""
            <div style="margin-bottom: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px;">
              <strong style="color: #0f172a; font-size: 14px; display: block; margin-bottom: 4px;">Q: {safe_escape(fq['question'])}</strong>
              <span style="color: #475569; font-size: 13.5px; line-height: 1.5; display: block;">Ans: {safe_escape(fq['answer'])}</span>
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

    # 8. Important Action Links Table
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
        elif "notification" in lbl_low or "pdf" in lbl_low:
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
        🔗 Important Official Direct Links
      </h2>
      <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; background: #ffffff;">
          <thead>
            <tr style="background: #0f172a; color: #ffffff;">
              <th style="padding: 10px 14px; border: 1px solid #cbd5e1; text-align: left; font-size: 14px;">Action / Document</th>
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

    # 9. Professional Editorial Disclaimer
    disclaimer = f"""
    <div style="background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 14px; font-size: 12.5px; color: #64748b; line-height: 1.6; margin-top: 30px; border-radius: 6px;">
      <strong>Editorial Disclaimer:</strong> All information published on <em>{SITE_BRAND_NAME}</em> is compiled from official government recruitment notifications, employment circulars, and departmental portals. Candidates are strongly advised to cross-check all terms, qualification criteria, and exam guidelines with the official notification before applying.
    </div>
    """

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 12px; background: #ffffff; color: #0f172a;">
      {banner}
      <h1 style="font-size: 22px; font-weight: 800; color: #0f172a; margin: 16px 0 12px 0; line-height: 1.4;">
        {clean_title}
      </h1>
      <div style="background: #f8fafc; border-left: 4px solid {border_color}; padding: 14px 18px; margin-bottom: 20px; font-size: 14.5px; color: #334155; line-height: 1.7; border-radius: 0 6px 6px 0;">
        {overview_text}
      </div>
      {dates_fees_section}
      {age_box}
      {vacancy_section}
      {selection_section}
      {how_to_section}
      {faq_section}
      {links_section}
      {disclaimer}
    </div>
    """

# ==================== DEDICATED CATEGORY EXTRACTOR ====================

def fetch_category_links(cat_url):
    results = []
    seen = set()
    try:
        r = SESSION.get(cat_url, timeout=15)
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception:
        return results

    # Main content container to avoid sidebars and footers
    main_area = soup.find('div', {'id': 'content'}) or soup.find('main') or soup.find('article') or soup

    for a in main_area.find_all('a', href=True):
        t = clean_text(a.get_text())
        h = a['href'].strip()

        if not h.startswith("http"):
            h = f"https://sarkariresult.com.cm/{h.lstrip('/')}"

        tl = t.lower()

        # Clean Junk Filters
        if len(t) < 14:
            continue
        if re.search(r'[\u0900-\u097F]', t):
            continue  # Drop non-standard Hindi clickbait titles
        if any(bad in tl for bad in ["view more", "click here", "sarkari result", "skip to content", "privacy policy", "disclaimer", "contact us", "about us", "page"]):
            continue
        if any(bad in h.lower() for bad in ["/category/", "/tag/", "/p/", "/tools", "/page/"]):
            continue

        if h not in seen:
            seen.add(h)
            results.append((t, h))

    return results

# ==================== MAIN EXECUTION ====================

def run():
    print(f"Connecting to Blogger API (Blog ID: {BLOG_ID})...")
    service = get_blogger_service()

    posts_res = service.posts().list(blogId=BLOG_ID, status=['LIVE'], maxResults=350).execute()
    existing_titles = {normalize_key(p.get('title', '')) for p in posts_res.get('items', [])}
    print(f"Loaded {len(existing_titles)} existing posts from Blogger.")

    published_cache = load_published_cache()

    sources = [
        {"cat": "Latest Jobs", "url": "https://sarkariresult.com.cm/latest-jobs/", "color": "#0f5132", "limit": 4},
        {"cat": "Admit Card", "url": "https://sarkariresult.com.cm/admit-card/", "color": "#084298", "limit": 3},
        {"cat": "Result", "url": "https://sarkariresult.com.cm/result/", "color": "#842029", "limit": 3},
        {"cat": "Answer Key", "url": "https://sarkariresult.com.cm/answer-key/", "color": "#59359a", "limit": 2},
        {"cat": "Syllabus", "url": "https://sarkariresult.com.cm/syllabus/", "color": "#a55608", "limit": 2}
    ]

    total_published = 0

    for s in sources:
        cat_name = s["cat"]
        print(f"\nScanning: {cat_name} -> {s['url']}")
        items = fetch_category_links(s["url"])
        cat_count = 0

        for title, link in items:
            n_key = normalize_key(title)
            if n_key in existing_titles or link in published_cache:
                continue

            print(f"Publishing -> [{cat_name}] {title}")
            parsed_data = parse_full_job_page(link, title)
            post_html = build_accurate_html(title, cat_name, parsed_data, border_color=s["color"])

            search_desc = f"{title} official notification, eligibility, exam date, syllabus & direct apply online links."[:150]

            body = {
                "title": title,
                "content": post_html,
                "labels": [cat_name],
                "searchDescription": search_desc
            }

            try:
                service.posts().insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
                print("  ✔ Successfully Published!")
                published_cache.add(link)
                existing_titles.add(n_key)
                total_published += 1
                cat_count += 1
                time.sleep(2)

                if cat_count >= s["limit"]:
                    break
            except Exception as e:
                print(f"  ✖ Insert error: {e}")
                continue

    save_published_cache(published_cache)
    print(f"\nFinished! Total fresh posts published: {total_published}")

if __name__ == "__main__":
    run()
