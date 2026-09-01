import os
import requests
from dotenv import load_dotenv

# IMPORTANT:
# override=True forces Python to use the values currently inside .env
# instead of an older Windows/system environment variable.
load_dotenv(override=True)

PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
PAGE_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")

if not PAGE_ID:
    raise RuntimeError("FACEBOOK_PAGE_ID is missing from .env")

if not PAGE_TOKEN:
    raise RuntimeError("FACEBOOK_PAGE_ACCESS_TOKEN is missing from .env")

print("=" * 60)
print("THRAANSH FACEBOOK API TEST")
print("=" * 60)

print(f"Page ID from .env: {PAGE_ID}")
print(f"Token loaded: YES")
print(f"Token length: {len(PAGE_TOKEN)}")
print()


# --------------------------------------------------
# TEST 1 — VERIFY TOKEN IDENTITY
# --------------------------------------------------

print("STEP 1: Checking Page token identity...")

identity_url = "https://graph.facebook.com/v26.0/me"

identity_response = requests.get(
    identity_url,
    params={
        "fields": "id,name",
        "access_token": PAGE_TOKEN,
    },
    timeout=30,
)

print(f"HTTP Status: {identity_response.status_code}")
print(f"Response: {identity_response.text}")
print()

if identity_response.status_code != 200:
    print("❌ TOKEN IDENTITY CHECK FAILED")
    raise SystemExit(1)

identity = identity_response.json()

returned_id = identity.get("id")
returned_name = identity.get("name")

print(f"Returned Page ID: {returned_id}")
print(f"Returned Page Name: {returned_name}")

if str(returned_id) != str(PAGE_ID):
    print()
    print("❌ WRONG PAGE TOKEN")
    print("The token in .env does not belong to the expected Facebook Page.")
    raise SystemExit(1)

print("✅ Correct Facebook Page token detected")
print()


# --------------------------------------------------
# TEST 2 — CHECK PERMISSIONS
# --------------------------------------------------

print("STEP 2: Checking token permissions...")

permissions_url = "https://graph.facebook.com/v26.0/me/permissions"

permissions_response = requests.get(
    permissions_url,
    params={
        "access_token": PAGE_TOKEN,
    },
    timeout=30,
)

print(f"HTTP Status: {permissions_response.status_code}")
print(f"Response: {permissions_response.text}")
print()


# --------------------------------------------------
# TEST 3 — CREATE FACEBOOK PAGE POST
# --------------------------------------------------

print("STEP 3: Publishing Facebook test post...")

publish_url = f"https://graph.facebook.com/v26.0/{PAGE_ID}/feed"

payload = {
    "message": "THRAANSH Facebook API Python connection test",
    "access_token": PAGE_TOKEN,
}

publish_response = requests.post(
    publish_url,
    data=payload,
    timeout=30,
)

print(f"Posting to: {publish_url}")
print(f"HTTP Status: {publish_response.status_code}")
print(f"Response: {publish_response.text}")
print()

if publish_response.status_code == 200:
    result = publish_response.json()

    print("=" * 60)
    print("✅ FACEBOOK POST SUCCESSFUL")
    print("=" * 60)
    print(f"Post ID: {result.get('id')}")

else:
    print("=" * 60)
    print("❌ FACEBOOK POST FAILED")
    print("=" * 60)