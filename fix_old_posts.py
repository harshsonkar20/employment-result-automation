import os
import re
import html
import time
import requests
from bs4 import BeautifulSoup
from scraper_bot import (
    get_blogger_service,
    parse_full_job_page,
    build_accurate_html,
    SESSION,
    clean_text,
    safe_escape,
    sanitize_brand_text,
    normalize_key
)

BLOG_ID = os.environ.get("BLOG_ID", "").strip()

def upgrade_all_old_post_links():
    if not BLOG_ID:
        print("ERROR: BLOG_ID environment variable is not set.")
        return

    service = get_blogger_service()

    # 1. Fetch category pages of source to map Normalized Title -> Source URL
    print("Building source URL catalog from sarkariresult.com.cm...")
    title_to_url = {}
    sources = [
        "https://sarkariresult.com.cm/latest-jobs/",
        "https://sarkariresult.com.cm/admit-card/",
        "https://sarkariresult.com.cm/result/",
        "https://sarkariresult.com.cm/answer-key/",
        "https://sarkariresult.com.cm/syllabus/",
        "https://sarkariresult.com.cm/"
    ]

    for cat_url in sources:
        try:
            r = SESSION.get(cat_url, timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    t = clean_text(a.get_text())
                    h = a["href"].strip()
                    if h.startswith("/"):
                        h = f"https://sarkariresult.com.cm{h}"
                    elif not h.startswith("http"):
                        h = f"https://sarkariresult.com.cm/{h}"
                    if len(t) > 12:
                        k = normalize_key(t)
                        if k not in title_to_url:
                            title_to_url[k] = h
        except Exception as e:
            print(f"Warning fetching {cat_url}: {e}")

    print(f"Mapped {len(title_to_url)} active job URLs from source.")

    # 2. Fetch Blogger Posts
    posts = []
    page_token = None
    print("Fetching existing posts from Blogger...")
    while True:
        res = service.posts().list(blogId=BLOG_ID, status=['LIVE'], maxResults=100, pageToken=page_token).execute()
        posts.extend(res.get('items', []))
        page_token = res.get('nextPageToken')
        if not page_token:
            break

    print(f"Scanning {len(posts)} Blogger posts for single-link tables or outdated structures...")
    updated_count = 0

    for p in posts:
        post_id = p['id']
        title = p.get('title', '')
        content = p.get('content', '')
        labels = p.get('labels', ['Latest Jobs'])
        category_name = labels[0] if labels else "Latest Jobs"

        # Check if post has fallback single link or old structure
        needs_update = any(marker in content for marker in [
            "Official Notification &amp; Portal",
            "Official Notification & Portal",
            "Official Notification &amp; Web Portal",
            "Official Notification & Web Portal",
            "Official Notification &amp; Direct Portal",
            "Download SarkariResult App Now",
            "Direct Link In Official Circular"
        ])

        if needs_update:
            n_key = normalize_key(title)
            source_url = title_to_url.get(n_key)

            if source_url:
                print(f"--> Re-parsing full details for: {title}")
                parsed = parse_full_job_page(source_url, title)
                new_html = build_accurate_html(title, category_name, parsed)

                body = {
                    "title": title,
                    "content": new_html,
                    "labels": labels,
                    "searchDescription": p.get("searchDescription", f"{title} official notification, eligibility & direct apply links.")[:150]
                }
                try:
                    service.posts().patch(blogId=BLOG_ID, postId=post_id, body=body).execute()
                    print(f"    ✔ [UPDATED & SYSTEMATIZED] {title}")
                    updated_count += 1
                    time.sleep(2)
                except Exception as e:
                    print(f"    ✖ [Patch Error] {e}")

    print(f"\nCOMPLETED! Upgraded {updated_count} posts to full systematic layouts.")

if __name__ == "__main__":
    upgrade_all_old_post_links()
