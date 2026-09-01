import os
import requests
from dotenv import load_dotenv

load_dotenv(".env", override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL:
    print("❌ SUPABASE_URL missing from .env")
    raise SystemExit

if not SUPABASE_SERVICE_ROLE_KEY:
    print("❌ SUPABASE_SERVICE_ROLE_KEY missing from .env")
    raise SystemExit

print("✅ Supabase credentials loaded")

url = f"{SUPABASE_URL}/storage/v1/bucket"

headers = {
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
}

try:
    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    print("Status:", response.status_code)

    if response.status_code == 200:
        print("✅ SUPABASE CONNECTION SUCCESSFUL")
        print("Buckets:", response.json())
    else:
        print("❌ SUPABASE CONNECTION FAILED")
        print("Response:", response.text)

except requests.RequestException as error:
    print("❌ Network error:", error)