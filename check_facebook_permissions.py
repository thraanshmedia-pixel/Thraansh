import os
import requests
from dotenv import load_dotenv

load_dotenv(".env", override=True)

PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
PAGE_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")

if not PAGE_ID:
    print("❌ FACEBOOK_PAGE_ID missing")
    raise SystemExit

if not PAGE_TOKEN:
    print("❌ FACEBOOK_PAGE_ACCESS_TOKEN missing")
    raise SystemExit

url = f"https://graph.facebook.com/v26.0/{PAGE_ID}/feed"

payload = {
    "message": "THRAANSH Facebook API test post.",
    "access_token": PAGE_TOKEN
}

print("Posting to Page ID:", PAGE_ID)

response = requests.post(
    url,
    data=payload,
    timeout=30
)

print("Status:", response.status_code)

try:
    result = response.json()
except Exception:
    print(response.text)
    raise SystemExit

print("Response:", result)