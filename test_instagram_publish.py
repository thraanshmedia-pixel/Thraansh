import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(".env", override=True)

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

BUCKET_NAME = "thraansh-publishing"
IMAGE_PATH = Path("test_media/Lion.jpg")

CAPTION = """THRAANSH Automation Test 🚀

Testing automated publishing from the THRAANSH publishing system.

#THRAANSH #Technology #Automation
"""

# --------------------------------------------------
# CHECK ENVIRONMENT
# --------------------------------------------------

required = {
    "INSTAGRAM_ACCESS_TOKEN": INSTAGRAM_ACCESS_TOKEN,
    "INSTAGRAM_ACCOUNT_ID": INSTAGRAM_ACCOUNT_ID,
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_SERVICE_ROLE_KEY": SUPABASE_SERVICE_ROLE_KEY,
}

for name, value in required.items():
    if not value:
        print(f"❌ {name} missing from .env")
        raise SystemExit

if not IMAGE_PATH.exists():
    print(f"❌ Image not found: {IMAGE_PATH}")
    raise SystemExit

print("✅ Environment variables loaded")
print("✅ Test image found")

# --------------------------------------------------
# STEP 1 — UPLOAD IMAGE TO SUPABASE
# --------------------------------------------------

file_name = f"instagram-tests/test-{int(time.time())}.jpg"

upload_url = (
    f"{SUPABASE_URL}/storage/v1/object/"
    f"{BUCKET_NAME}/{file_name}"
)

headers = {
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Content-Type": "image/jpeg",
}

with open(IMAGE_PATH, "rb") as image_file:
    response = requests.post(
        upload_url,
        headers=headers,
        data=image_file,
        timeout=60,
    )

if response.status_code not in (200, 201):
    print("❌ Supabase upload failed")
    print("Status:", response.status_code)
    print(response.text)
    raise SystemExit

print("✅ Image uploaded to Supabase")

# --------------------------------------------------
# STEP 2 — CREATE PUBLIC IMAGE URL
# --------------------------------------------------

public_url = (
    f"{SUPABASE_URL}/storage/v1/object/public/"
    f"{BUCKET_NAME}/{file_name}"
)

print("✅ Public image URL created")

# Verify that Instagram will be able to retrieve it
check = requests.get(public_url, timeout=30)

if check.status_code != 200:
    print("❌ Public image cannot be accessed")
    print("Status:", check.status_code)
    raise SystemExit

print("✅ Public image is accessible")

# --------------------------------------------------
# STEP 3 — CREATE INSTAGRAM MEDIA CONTAINER
# --------------------------------------------------

graph_url = (
    f"https://graph.instagram.com/v24.0/"
    f"{INSTAGRAM_ACCOUNT_ID}/media"
)

payload = {
    "image_url": public_url,
    "caption": CAPTION,
    "access_token": INSTAGRAM_ACCESS_TOKEN,
}

response = requests.post(
    graph_url,
    data=payload,
    timeout=60,
)

result = response.json()

if response.status_code != 200 or "id" not in result:
    print("❌ Instagram container creation failed")
    print("Status:", response.status_code)
    print("Response:", result)
    raise SystemExit

creation_id = result["id"]

print("✅ Instagram media container created")
print("Creation ID:", creation_id)

# --------------------------------------------------
# STEP 4 — PUBLISH
# --------------------------------------------------

publish_url = (
    f"https://graph.instagram.com/v24.0/"
    f"{INSTAGRAM_ACCOUNT_ID}/media_publish"
)

publish_payload = {
    "creation_id": creation_id,
    "access_token": INSTAGRAM_ACCESS_TOKEN,
}

response = requests.post(
    publish_url,
    data=publish_payload,
    timeout=60,
)

publish_result = response.json()

if response.status_code != 200 or "id" not in publish_result:
    print("❌ Instagram publishing failed")
    print("Status:", response.status_code)
    print("Response:", publish_result)
    raise SystemExit

instagram_media_id = publish_result["id"]

print()
print("========================================")
print("🎉 INSTAGRAM PUBLISH SUCCESSFUL")
print("Instagram Media ID:", instagram_media_id)
print("========================================")
