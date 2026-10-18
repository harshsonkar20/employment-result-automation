import os
import re
import html
import time
import requests
from bs4 import BeautifulSoup
from scraper_bot import get_blogger_service, parse_full_job_page, SESSION, clean_text, normalize_key

BLOG_ID = os.environ.get("BLOG_ID", "").strip()

def upgrade_all_old_post_links():
    service = get_blogger_service()

    # 1. Fetch homepage of source to map Post Title -> Source URL
    print("Building source URL map from sarkariresult.com.cm...")
    title_to_url = {}
    try:
        r = SESSION.get("https://sarkariresult.com.cm/", timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                t = clean_text(a.get_text())
                h = a["href"].strip()
                if h.startswith("/"): h = f"https://sarkariresult.com.cm{h}"
                elif not h.startswith("http"): h = f"https://sarkariresult.com.cm/{h}"
                if len(t) > 15:
                    title_to_url[normalize_key(t)] = h
    except Exception as e:
        print(f"Source map warning: {e}")

    print(f"Mapped {len(title_to_url)} active job URLs.")

    # 2. Fetch Blogger Posts
    posts = []
    page_token = None
    while True:
        res = service.posts().list(blogId=BLOG_ID, status=['LIVE'], maxResults=100, pageToken=page_token).execute()
        posts.extend(res.get('items', []))
        page_token = res.get('nextPageToken')
        if not page_token:
            break

    print(f"Scanning {len(posts)} Blogger posts for single-link tables...")
    updated_count = 0

    for p in posts:
        post_id = p['id']
        title = p.get('title', '')
        content = p.get('content', '')

        # Check if post only has the single fallback row
        if any(marker in content for marker in ["Official Notification &amp; Portal", "Official Notification & Portal", "Official Notification &amp; Web Portal", "Official Notification & Web Portal", "Official Notification &amp; Direct Portal"]):
            n_key = normalize_key(title)
            source_url = title_to_url.get(n_key)

            links = []
            if source_url:
                print(f"--> Re-parsing full multi-links for: {title}")
                parsed = parse_full_job_page(source_url)
                links = parsed.get("links", [])

            # Agar source homepage par nahi mila, toh intelligent multi-row links banayein
            if len(links) < 2:
                from urllib.parse import quote_plus
                q_apply = quote_plus(f"{title} apply online")
                q_pdf = quote_plus(f"{title} official notification pdf")
                links = [
                    {"label": "Apply Online / Registration", "url": source_url or f"https://www.google.com/search?q={q_apply}"},
                    {"label": "Download Official Notification PDF", "url": source_url or f"https://www.google.com/search?q={q_pdf}"}
                ]
                # Check if official site URL is already mentioned inside post FAQ text
                faq_match = re.search(r'(https?://[a-zA-Z0-9\.\-]+(?:\.gov\.in|\.nic\.in|\.org\.in|\.com|\.in)/?)', content)
                if faq_match and "blogspot" not in faq_match.group(1) and "w3.org" not in faq_match.group(1):
                    links.append({"label": "Official Website Portal", "url": faq_match.group(1)})

            # Build multi-row HTML
            new_rows = ""
            for lk in links:
                btn_color = "#0056b3" if "official" in lk['label'].lower() else ("#d35400" if "notification" in lk['label'].lower() else "#28a745")
                new_rows += f"<tr><td style='border:1px solid #999; padding:10px; font-weight:bold;'>{lk['label']}</td><td style='border:1px solid #999; padding:10px; text-align:center;'><a href='{lk['url']}' target='_blank' rel='noopener noreferrer' style='background:{btn_color}; color:#fff; padding:7px 16px; font-weight:bold; border-radius:3px; text-decoration:none; display:inline-block;'>Click Here</a></td></tr>"

            # Replace the last table (Important Links table)
            new_content = re.sub(
                r'(<div[^>]*>\s*Important Links\s*</div>\s*<table[^>]*>).*?(</table>)',
                rf'\1{new_rows}\2',
                content,
                flags=re.DOTALL | re.IGNORECASE
            )

            if new_content != content:
                body = {
                    "title": title,
                    "content": new_content,
                    "labels": p.get("labels", []),
                    "searchDescription": p.get("searchDescription", "")
                }
                try:
                    service.posts().patch(blogId=BLOG_ID, postId=post_id, body=body).execute()
                    print(f"    [UPDATED WITH {len(links)} LINKS] {title}")
                    updated_count += 1
                    time.sleep(1.5)
                except Exception as e:
                    print(f"    [Error] {e}")

    print(f"\nCOMPLETED! Upgraded {updated_count} posts to full multi-link tables.")

if __name__ == "__main__":
    upgrade_all_old_post_links()
