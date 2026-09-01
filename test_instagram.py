import os
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")

# Check credentials
if not INSTAGRAM_ACCESS_TOKEN:
    print("❌ INSTAGRAM_ACCESS_TOKEN is missing from .env")
    raise SystemExit

if not INSTAGRAM_ACCOUNT_ID:
    print("❌ INSTAGRAM_ACCOUNT_ID is missing from .env")
    raise SystemExit

print("✅ Instagram credentials loaded from .env")
print("Instagram Account ID:", INSTAGRAM_ACCOUNT_ID)

# Instagram API endpoint
url = f"https://graph.instagram.com/v24.0/{INSTAGRAM_ACCOUNT_ID}"

params = {
    "fields": "id,username,account_type",
    "access_token": INSTAGRAM_ACCESS_TOKEN
}

try:
    response = requests.get(url, params=params, timeout=30)

    print("Status:", response.status_code)

    data = response.json()

    if response.status_code == 200:
        print("✅ INSTAGRAM CONNECTION SUCCESSFUL")
        print("Account ID:", data.get("id"))
        print("Username:", data.get("username"))
        print("Account Type:", data.get("account_type"))
    else:
        print("❌ INSTAGRAM CONNECTION FAILED")
        print("Response:", data)

except requests.RequestException as error:
    print("❌ Network/API error:", error)