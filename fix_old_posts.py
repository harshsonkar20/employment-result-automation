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
    extract_homepage_categories,
    SESSION,
    clean_text,
    safe_escape,
    sanitize_brand_text,
    normalize_key,
    is_old_post
)

BLOG_ID = os.environ.get("BLOG_ID", "").strip()

def upgrade_and_clean_posts():
    if not BLOG_ID:
        print("ERROR: BLOG_ID environment variable is not set.")
        return

    service = get_blogger_service()

    # 1. Fetch current active homepage data
    print("Fetching active posts catalog from sarkariresult.com.cm...")
    homepage_data = extract_homepage_categories()

    # Build Title -> (URL, Category) map
    title_to_meta = {}
    for cat, items in homepage_data.items():
        for t, h in items:
            title_to_meta[normalize_key(t)] = (h, cat)

    print(f"Mapped {len(title_to_meta)} active posts directly from source homepage.")

    # 2. Fetch all Blogger Posts
    posts = []
    page_token = None
    print("Fetching existing posts from Blogger...")
    try:
        while True:
            res = service.posts().list(blogId=BLOG_ID, status=['LIVE'], maxResults=100, pageToken=page_token).execute()
            posts.extend(res.get('items', []))
            page_token = res.get('nextPageToken')
            if not page_token:
                break
    except Exception as e:
        err_text = str(e)
        if "invalid_grant" in err_text or "expired or revoked" in err_text.lower():
            print(f"\n{'='*70}")
            print("[CRITICAL AUTH ERROR] Google Refresh Token is EXPIRED or REVOKED!")
            print("Why: Google expires refresh tokens after 7 days if the OAuth consent")
            print("screen in Google Cloud Console is left in 'Testing' mode.")
            print("\nHOW TO FIX PERMANENTLY:")
            print("1. In Google Cloud Console -> APIs & Services -> OAuth consent screen:")
            print("   Click 'PUBLISH APP' to change Publishing Status to 'In production'.")
            print("2. Run 'python get_refresh_token.py' locally to generate a new token.")
            print("3. Update 'GOOGLE_REFRESH_TOKEN' in GitHub Secrets:")
            print("   Settings -> Secrets and variables -> Actions")
            print(f"{'='*70}\n")
        raise

    print(f"Scanning {len(posts)} live Blogger posts...")
    reverted_old_count = 0
    reverted_duplicate_count = 0
    updated_count = 0
    relabelled_syllabus_count = 0
    seen_normalized_keys = set()

    for p in posts:
        post_id = p['id']
        title = p.get('title', '')
        content = p.get('content', '')
        published = p.get('published', '')
        labels = p.get('labels', ['Latest Jobs'])
        category_name = labels[0] if labels else "Latest Jobs"

        # A. Check if this is an outdated / historical post (older than August 2026 or past cycle)
        if is_old_post(title, published):
            print(f"--> [REVERTING OLD POST TO DRAFT] {title} (Published: {published[:10]})")
            try:
                service.posts().revert(blogId=BLOG_ID, postId=post_id).execute()
                reverted_old_count += 1
                time.sleep(1)
                continue
            except Exception as e:
                print(f"    ✖ Revert error: {e}")

        # B. Check for duplicate posts (keep only 1 unique live copy)
        n_key = normalize_key(title)
        if n_key in seen_normalized_keys:
            print(f"--> [REVERTING DUPLICATE POST TO DRAFT] {title} (ID: {post_id})")
            try:
                service.posts().revert(blogId=BLOG_ID, postId=post_id).execute()
                reverted_duplicate_count += 1
                time.sleep(0.5)
                continue
            except Exception as e:
                print(f"    ✖ Revert duplicate error: {e}")
        else:
            seen_normalized_keys.add(n_key)

        # C. Check if post is a Syllabus item with wrong label
        if "syllabus" in title.lower() and "Syllabus" not in labels:
            print(f"--> [FIXING SYLLABUS LABEL] {title}")
            labels = ["Syllabus"]
            category_name = "Syllabus"
            relabelled_syllabus_count += 1

        # D. Re-write all posts into 100% original, copyright-free, AdSense-approved format
        meta = title_to_meta.get(n_key)

        if meta:
            source_url, cat_from_source = meta
            effective_cat = cat_from_source if cat_from_source else category_name
            print(f"--> Upgrading post to 100% original AdSense format: {title}")
            parsed = parse_full_job_page(source_url, title)
            new_html = build_accurate_html(title, effective_cat, parsed)

            body = {
                "title": title,
                "content": new_html,
                "labels": [effective_cat],
                "searchDescription": p.get("searchDescription", f"{title} official notification, eligibility & direct apply links.")[:150]
            }
            try:
                service.posts().patch(blogId=BLOG_ID, postId=post_id, body=body).execute()
                print(f"    ✔ [UPDATED & SYSTEMATIZED] {title}")
                updated_count += 1
                time.sleep(1.5)
            except Exception as e:
                print(f"    ✖ [Patch Error] {e}")

    # D. Ensure Syllabus section has active posts
    syllabus_items = homepage_data.get("Syllabus", [])
    print(f"\nChecking Syllabus posts (Found {len(syllabus_items)} on source homepage)...")
    existing_live_titles = {normalize_key(p.get('title', '')) for p in posts if not is_old_post(p.get('title', ''), p.get('published', ''))}

    published_syllabus = 0
    for s_title, s_url in syllabus_items:
        n_key = normalize_key(s_title)
        s_publish_title = s_title
        if "syllabus" not in s_publish_title.lower() and "exam pattern" not in s_publish_title.lower():
            s_publish_title = f"{s_title} Syllabus & Exam Pattern"

        if normalize_key(s_publish_title) in existing_live_titles or n_key in existing_live_titles:
            continue

        print(f"Publishing fresh Syllabus post -> {s_publish_title}")
        parsed_data = parse_full_job_page(s_url, s_publish_title)
        post_html = build_accurate_html(s_publish_title, "Syllabus", parsed_data, border_color="#a55608")

        body = {
            "title": s_publish_title,
            "content": post_html,
            "labels": ["Syllabus"],
            "searchDescription": f"{s_publish_title} official syllabus, exam pattern, subject-wise topics & notification."[:150]
        }
        try:
            service.posts().insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
            print(f"    ✔ Successfully published Syllabus post: {s_publish_title}")
            existing_live_titles.add(normalize_key(s_publish_title))
            published_syllabus += 1
            time.sleep(2)
            if published_syllabus >= 6:
                break
        except Exception as e:
            print(f"    ✖ Insert error: {e}")

    print(f"\n==========================================")
    print(f"MAINTENANCE COMPLETED:")
    print(f" - Outdated/Historical posts reverted to draft: {reverted_old_count}")
    print(f" - Duplicate posts reverted to draft: {reverted_duplicate_count}")
    print(f" - Posts rewritten into 100% unique AdSense content: {updated_count}")
    print(f" - Syllabus posts labelled: {relabelled_syllabus_count}")
    print(f" - Fresh Syllabus posts added: {published_syllabus}")

if __name__ == "__main__":
    upgrade_and_clean_posts()
