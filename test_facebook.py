import os
import requests
from dotenv import load_dotenv

load_dotenv(".env", override=True)

FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
FACEBOOK_PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")

if not FACEBOOK_PAGE_ID:
    print("❌ FACEBOOK_PAGE_ID missing from .env")
    raise SystemExit

if not FACEBOOK_PAGE_ACCESS_TOKEN:
    print("❌ FACEBOOK_PAGE_ACCESS_TOKEN missing from .env")
    raise SystemExit

print("✅ Facebook credentials loaded")
print("Page ID:", FACEBOOK_PAGE_ID)

url = f"https://graph.facebook.com/v26.0/{FACEBOOK_PAGE_ID}"

params = {
    "fields": "id,name",
    "access_token": FACEBOOK_PAGE_ACCESS_TOKEN
}

response = requests.get(url, params=params, timeout=30)

print("Status:", response.status_code)

try:
    result = response.json()
except Exception:
    print("❌ Invalid response from Facebook")
    print(response.text)
    raise SystemExit

if response.status_code == 200 and "id" in result:
    print("✅ FACEBOOK CONNECTION SUCCESSFUL")
    print("Page ID:", result.get("id"))
    print("Page Name:", result.get("name"))
else:
    print("❌ FACEBOOK CONNECTION FAILED")
    print("Response:", result)