"""
Helper script to generate a fresh Google OAuth 2.0 Refresh Token for Blogger API.
Run this script locally when your token expires:
    python get_refresh_token.py
"""

import os
import sys
import json
import glob
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/blogger'
]

def main():
    print("=" * 65)
    print(" Google Blogger OAuth 2.0 Refresh Token Generator")
    print("=" * 65)

    # 1. Search for client secret JSON files
    search_paths = [
        os.path.join(os.path.dirname(__file__), "client_secret*.json"),
        os.path.expanduser("~/Downloads/client_secret*.json"),
        os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "client_secret*.json"),
    ]

    found_files = []
    for pattern in search_paths:
        found_files.extend(glob.glob(pattern))

    installed_secret = None
    for f in found_files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                if "installed" in data:
                    installed_secret = f
                    break
        except Exception:
            continue

    if not installed_secret:
        print("\n[!] No 'installed' (Desktop) client_secret JSON file found.")
        print("Please place your downloaded client_secret_*.json in this directory or in Downloads.")
        sys.exit(1)

    print(f"\n[+] Found Client Secret: {os.path.basename(installed_secret)}")
    print("[+] Starting local authorization flow...")
    print("[+] A browser window will open. Sign in with your Google account and grant Blogger access.\n")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            installed_secret,
            scopes=SCOPES
        )
        # prompt='consent' and access_type='offline' are REQUIRED to get a refresh token!
        creds = flow.run_local_server(port=0, prompt='consent', access_type='offline')

        print("\n" + "=" * 65)
        print(" SUCCESS! NEW TOKENS GENERATED")
        print("=" * 65)
        print("\n1. Go to your GitHub repository:")
        print("   Settings > Secrets and variables > Actions > Repository secrets")
        print("\n2. Update the following secrets:\n")
        print("-" * 65)
        print(f"GOOGLE_REFRESH_TOKEN:\n{creds.refresh_token}\n")
        print(f"GOOGLE_CLIENT_ID:\n{creds.client_id}\n")
        print(f"GOOGLE_CLIENT_SECRET:\n{creds.client_secret}\n")
        print("-" * 65)
        print("\n[IMPORTANT TIP TO PREVENT EXPIRING EVERY 7 DAYS]:")
        print("In Google Cloud Console -> 'OAuth consent screen', change")
        print("Publishing Status from 'Testing' to 'In production' (Publish App).")
        print("This ensures your Refresh Token NEVER expires again!")
        print("=" * 65 + "\n")

    except Exception as e:
        print(f"\n[!] Authorization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
