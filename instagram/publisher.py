import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


# ============================================================
# THRAANSH INSTAGRAM VIDEO PUBLISHER V1
#
# PURPOSE:
#
# - Load current production-selected story
# - Require RIGHTS_PASS
# - Require rights manifest
# - Require exact final_video_file
# - Require verified Supabase public video URL
# - Verify Instagram Business account
# - Prevent duplicate Instagram publishing
# - Create Instagram video/Reel container
# - Wait for Instagram processing
# - Publish media
# - Save Instagram media ID/status back to article_queue.json
#
# IMPORTANT:
#
# Uses:
# Instagram API with Instagram Login
#
# Host:
# https://graph.instagram.com
#
# Required permission:
# instagram_business_content_publish
# ============================================================


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

ENV_FILE = PROJECT_ROOT / ".env"

ARTICLE_QUEUE_FILE = (
    PROJECT_ROOT
    / "data"
    / "article_queue.json"
)


# ============================================================
# LOAD ENV
# ============================================================

load_dotenv(
    ENV_FILE,
    override=True
)


INSTAGRAM_ACCESS_TOKEN = (
    os.getenv(
        "INSTAGRAM_ACCESS_TOKEN",
        ""
    )
    .strip()
)


INSTAGRAM_ACCOUNT_ID = (
    os.getenv(
        "INSTAGRAM_ACCOUNT_ID",
        ""
    )
    .strip()
)


INSTAGRAM_GRAPH_VERSION = (
    os.getenv(
        "INSTAGRAM_GRAPH_VERSION",
        "v26.0"
    )
    .strip()
)


# ============================================================
# DISPLAY HELPERS
# ============================================================

def line():
    print("=" * 72)


def success(message):
    print(f"✅ {message}")


def fail(message, code=1):
    print()
    line()
    print(f"❌ {message}")
    line()
    sys.exit(code)


# ============================================================
# STEP 1
# ENVIRONMENT CHECK
# ============================================================

def check_environment():

    print()
    line()

    print(
        "STEP 1: Checking Instagram environment..."
    )

    line()

    if not INSTAGRAM_ACCESS_TOKEN:
        fail(
            "INSTAGRAM_ACCESS_TOKEN is missing from .env"
        )

    if not INSTAGRAM_ACCOUNT_ID:
        fail(
            "INSTAGRAM_ACCOUNT_ID is missing from .env"
        )

    print()
    print(
        "INSTAGRAM_ACCESS_TOKEN: LOADED"
    )

    print(
        "Token length:",
        len(INSTAGRAM_ACCESS_TOKEN)
    )

    print(
        "INSTAGRAM_ACCOUNT_ID:",
        INSTAGRAM_ACCOUNT_ID
    )

    print(
        "INSTAGRAM_GRAPH_VERSION:",
        INSTAGRAM_GRAPH_VERSION
    )

    success(
        "Instagram environment loaded"
    )


# ============================================================
# LOAD QUEUE
# ============================================================

def load_queue():

    if not ARTICLE_QUEUE_FILE.exists():

        fail(
            "article_queue.json not found:\n"
            f"{ARTICLE_QUEUE_FILE}"
        )

    try:

        with open(
            ARTICLE_QUEUE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as error:

        fail(
            "Could not read article_queue.json:\n"
            f"{error}"
        )


# ============================================================
# EXTRACT ARTICLES
# ============================================================

def extract_articles(data):

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        for key in (
            "articles",
            "items",
            "queue",
            "news",
            "data"
        ):

            value = data.get(key)

            if isinstance(value, list):
                return value

    fail(
        "Could not locate article list in article_queue.json"
    )


# ============================================================
# FIND CURRENT ARTICLE
# ============================================================

def find_current_article(articles):

    selected = []

    for article in articles:

        if not isinstance(article, dict):
            continue

        if article.get(
            "production_selected"
        ) is True:

            selected.append(article)

    if not selected:

        fail(
            "No article has production_selected=true"
        )

    article = selected[-1]

    print()
    line()

    print(
        "CURRENT THRAANSH STORY"
    )

    line()

    print()
    print(
        article.get(
            "title",
            "Untitled Story"
        )
    )

    return article


# ============================================================
# STEP 2
# RIGHTS CHECK
# ============================================================

def verify_rights(article):

    print()
    line()

    print(
        "STEP 2: Checking publishing rights..."
    )

    line()

    status = str(
        article.get(
            "status",
            ""
        )
    ).strip()

    rights_status = str(
        article.get(
            "rights_status",
            ""
        )
    ).strip()

    print()
    print(
        "Article status:",
        status
    )

    print(
        "Rights status:",
        rights_status
    )

    if status != "RIGHTS_PASS":

        fail(
            "Article status is not RIGHTS_PASS."
        )

    if rights_status != "RIGHTS_PASS":

        fail(
            "rights_status is not RIGHTS_PASS."
        )

    manifest_value = (
        article.get(
            "rights_manifest_file"
        )
    )

    if not manifest_value:

        fail(
            "rights_manifest_file is missing."
        )

    manifest_path = Path(
        str(manifest_value)
    )

    if not manifest_path.is_absolute():

        manifest_path = (
            PROJECT_ROOT
            / manifest_path
        )

    manifest_path = (
        manifest_path.resolve()
    )

    if not manifest_path.exists():

        fail(
            "Rights manifest does not exist:\n"
            f"{manifest_path}"
        )

    success(
        "RIGHTS_PASS confirmed"
    )

    success(
        "Rights manifest confirmed"
    )

    warnings = (
        article.get(
            "rights_warnings"
        )
        or []
    )

    if warnings:

        print()
        print(
            "Editorial warnings:"
        )

        for warning in warnings:

            print(
                f"⚠️ {warning}"
            )


# ============================================================
# STEP 3
# VERIFY EXACT FINAL VIDEO
# ============================================================

def verify_exact_video(article):

    print()
    line()

    print(
        "STEP 3: Verifying exact final video..."
    )

    line()

    video_value = (
        article.get(
            "final_video_file"
        )
    )

    if not video_value:

        fail(
            "final_video_file is missing."
        )

    video_path = Path(
        str(video_value)
    )

    if not video_path.is_absolute():

        video_path = (
            PROJECT_ROOT
            / video_path
        )

    video_path = video_path.resolve()

    if not video_path.exists():

        fail(
            "Exact final video does not exist:\n"
            f"{video_path}"
        )

    if not video_path.is_file():

        fail(
            "final_video_file is not a file."
        )

    if video_path.suffix.lower() != ".mp4":

        fail(
            "final_video_file is not an MP4."
        )

    size_mb = (
        video_path.stat().st_size
        / 1024
        / 1024
    )

    print()
    print(
        "Exact video:"
    )

    print(
        video_path
    )

    print()
    print(
        f"Video size: {size_mb:.2f} MB"
    )

    success(
        "Exact final_video_file confirmed"
    )

    return video_path


# ============================================================
# STEP 4
# VERIFY SUPABASE VIDEO URL
# ============================================================

def verify_public_video_url(article):

    print()
    line()

    print(
        "STEP 4: Checking Instagram public video URL..."
    )

    line()

    storage_status = str(
        article.get(
            "instagram_storage_status",
            ""
        )
    ).strip()

    public_url = str(
        article.get(
            "instagram_video_url",
            ""
        )
    ).strip()

    if storage_status != "UPLOADED":

        fail(
            "instagram_storage_status is not UPLOADED.\n"
            "Run instagram/storage_uploader.py first."
        )

    if not public_url:

        fail(
            "instagram_video_url is missing."
        )

    if not public_url.startswith(
        "https://"
    ):

        fail(
            "Instagram video URL is not HTTPS."
        )

    print()
    print(
        "Instagram source URL:"
    )

    print(
        public_url
    )

    try:

        response = requests.get(
            public_url,
            headers={
                "Range":
                    "bytes=0-1023"
            },
            stream=True,
            timeout=60
        )

    except requests.RequestException as error:

        fail(
            "Could not reach Instagram source video:\n"
            f"{error}"
        )

    print()
    print(
        "HTTP Status:",
        response.status_code
    )

    content_type = (
        response.headers
        .get(
            "Content-Type",
            ""
        )
        .lower()
    )

    print(
        "Content-Type:",
        content_type
    )

    if response.status_code not in (
        200,
        206
    ):

        response.close()

        fail(
            "Instagram source video URL is not publicly reachable."
        )

    if "video" not in content_type:

        response.close()

        fail(
            "Public source URL did not return a video Content-Type."
        )

    response.close()

    success(
        "Instagram public video URL verified"
    )

    return public_url


# ============================================================
# STEP 5
# VERIFY INSTAGRAM ACCOUNT
# ============================================================

def verify_instagram_account():

    print()
    line()

    print(
        "STEP 5: Verifying Instagram Business account..."
    )

    line()

    url = (
        "https://graph.instagram.com/"
        f"{INSTAGRAM_GRAPH_VERSION}/"
        f"{INSTAGRAM_ACCOUNT_ID}"
    )

    params = {

        "fields":
            "id,username,name,account_type",

        "access_token":
            INSTAGRAM_ACCESS_TOKEN
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=30
        )

    except requests.RequestException as error:

        fail(
            "Instagram account verification failed:\n"
            f"{error}"
        )

    print()
    print(
        "HTTP Status:",
        response.status_code
    )

    try:

        result = response.json()

    except Exception:

        fail(
            "Instagram account endpoint returned non-JSON data."
        )

    if response.status_code != 200:

        print()
        print(
            result
        )

        fail(
            "Instagram account verification failed."
        )

    returned_id = str(
        result.get(
            "id",
            ""
        )
    )

    if returned_id != str(
        INSTAGRAM_ACCOUNT_ID
    ):

        fail(
            "Instagram account ID mismatch."
        )

    username = (
        result.get(
            "username"
        )
        or "Unknown"
    )

    account_type = (
        result.get(
            "account_type"
        )
        or "Unknown"
    )

    print()
    print(
        "Instagram username:",
        username
    )

    print(
        "Account type:",
        account_type
    )

    success(
        "Correct Instagram account confirmed"
    )


# ============================================================
# STEP 6
# DUPLICATE PROTECTION
# ============================================================

def check_duplicate(article):

    print()
    line()

    print(
        "STEP 6: Instagram duplicate protection..."
    )

    line()

    existing_id = (
        article.get(
            "instagram_media_id"
        )
    )

    existing_status = str(
        article.get(
            "instagram_publish_status",
            ""
        )
    ).strip()

    if (
        existing_id
        and existing_status == "PUBLISHED"
    ):

        print()
        print(
            "This story is already published on Instagram."
        )

        print()
        print(
            "Instagram Media ID:"
        )

        print(
            existing_id
        )

        print()
        print(
            "No second upload performed."
        )

        return True

    success(
        "No existing Instagram publication detected"
    )

    return False


# ============================================================
# BUILD CAPTION
# ============================================================

def build_caption(article):

    title = (
        article.get(
            "title"
        )
        or ""
    ).strip()

    teaser = (
        article.get(
            "teaser"
        )
        or article.get(
            "summary"
        )
        or ""
    ).strip()

    source_url = (
        article.get(
            "url"
        )
        or article.get(
            "source_url"
        )
        or ""
    ).strip()

    parts = []

    if title:

        parts.append(
            title
        )

    if teaser:

        parts.append(
            teaser
        )

    parts.append(
        "Follow @thraansh for more updates."
    )

    if source_url:

        parts.append(
            f"Source: {source_url}"
        )

    parts.append(
        "#THRAANSH #News #India #LatestNews"
    )

    caption = (
        "\n\n".join(parts)
    )

    # Instagram caption limit is larger,
    # but keep THRAANSH captions controlled.
    if len(caption) > 2100:

        caption = (
            caption[:2050].rstrip()
            + "..."
        )

    return caption


# ============================================================
# STEP 7
# CREATE INSTAGRAM MEDIA CONTAINER
# ============================================================

def create_media_container(
    public_video_url,
    caption
):

    print()
    line()

    print(
        "STEP 7: Creating Instagram media container..."
    )

    line()

    url = (
        "https://graph.instagram.com/"
        f"{INSTAGRAM_GRAPH_VERSION}/"
        f"{INSTAGRAM_ACCOUNT_ID}/media"
    )

    data = {

        "media_type":
            "REELS",

        "video_url":
            public_video_url,

        "caption":
            caption,

        # ----------------------------------------------------
        # Current THRAANSH video should also appear in Feed.
        # ----------------------------------------------------

        "share_to_feed":
            "true",

        "access_token":
            INSTAGRAM_ACCESS_TOKEN,
    }

    print()
    print(
        "Submitting public video URL to Instagram..."
    )

    try:

        response = requests.post(
            url,
            data=data,
            timeout=60
        )

    except requests.RequestException as error:

        fail(
            "Instagram media-container request failed:\n"
            f"{error}"
        )

    print()
    print(
        "HTTP Status:",
        response.status_code
    )

    try:

        result = response.json()

    except Exception:

        print(
            response.text
        )

        fail(
            "Instagram returned a non-JSON response."
        )

    print()
    print(
        "Instagram response:"
    )

    print(
        result
    )

    if response.status_code not in (
        200,
        201
    ):

        fail(
            "Instagram media container creation failed."
        )

    container_id = (
        result.get(
            "id"
        )
    )

    if not container_id:

        fail(
            "Instagram did not return a container ID."
        )

    success(
        "Instagram media container created"
    )

    print()
    print(
        "Container ID:"
    )

    print(
        container_id
    )

    return container_id


# ============================================================
# STEP 8
# WAIT FOR VIDEO PROCESSING
# ============================================================

def wait_for_container(container_id):

    print()
    line()

    print(
        "STEP 8: Waiting for Instagram video processing..."
    )

    line()

    url = (
        "https://graph.instagram.com/"
        f"{INSTAGRAM_GRAPH_VERSION}/"
        f"{container_id}"
    )

    params = {

        "fields":
            "status_code,status",

        "access_token":
            INSTAGRAM_ACCESS_TOKEN,
    }

    max_attempts = 40
    wait_seconds = 15

    for attempt in range(
        1,
        max_attempts + 1
    ):

        print()
        print(
            f"Processing check {attempt}/{max_attempts}..."
        )

        try:

            response = requests.get(
                url,
                params=params,
                timeout=30
            )

        except requests.RequestException as error:

            print(
                f"Temporary request error: {error}"
            )

            time.sleep(
                wait_seconds
            )

            continue

        try:

            result = response.json()

        except Exception:

            print(
                "Unexpected Instagram response."
            )

            time.sleep(
                wait_seconds
            )

            continue

        print(
            "Processing response:",
            result
        )

        status_code = str(
            result.get(
                "status_code",
                ""
            )
        ).upper()

        if status_code == "FINISHED":

            success(
                "Instagram video processing finished"
            )

            return True

        if status_code in (
            "ERROR",
            "EXPIRED"
        ):

            fail(
                "Instagram container processing failed.\n"
                f"Status: {status_code}\n"
                f"Response: {result}"
            )

        if status_code in (
            "IN_PROGRESS",
            "PUBLISHED"
        ):

            if status_code == "PUBLISHED":

                success(
                    "Instagram container already published"
                )

                return True

        time.sleep(
            wait_seconds
        )

    fail(
        "Instagram video processing timed out."
    )


# ============================================================
# STEP 9
# PUBLISH INSTAGRAM MEDIA
# ============================================================

def publish_media(container_id):

    print()
    line()

    print(
        "STEP 9: Publishing video to Instagram..."
    )

    line()

    url = (
        "https://graph.instagram.com/"
        f"{INSTAGRAM_GRAPH_VERSION}/"
        f"{INSTAGRAM_ACCOUNT_ID}/media_publish"
    )

    data = {

        "creation_id":
            container_id,

        "access_token":
            INSTAGRAM_ACCESS_TOKEN,
    }

    try:

        response = requests.post(
            url,
            data=data,
            timeout=60
        )

    except requests.RequestException as error:

        fail(
            "Instagram publish request failed:\n"
            f"{error}"
        )

    print()
    print(
        "HTTP Status:",
        response.status_code
    )

    try:

        result = response.json()

    except Exception:

        print(
            response.text
        )

        fail(
            "Instagram publish response was not JSON."
        )

    print()
    print(
        "Instagram publish response:"
    )

    print(
        result
    )

    if response.status_code not in (
        200,
        201
    ):

        fail(
            "Instagram publishing failed."
        )

    media_id = (
        result.get(
            "id"
        )
    )

    if not media_id:

        fail(
            "Instagram did not return a published media ID."
        )

    success(
        "Instagram video published"
    )

    return media_id


# ============================================================
# STEP 10
# VERIFY PUBLISHED MEDIA
# ============================================================

def verify_published_media(media_id):

    print()
    line()

    print(
        "STEP 10: Verifying published Instagram media..."
    )

    line()

    url = (
        "https://graph.instagram.com/"
        f"{INSTAGRAM_GRAPH_VERSION}/"
        f"{media_id}"
    )

    params = {

        "fields":
            "id,media_type,media_product_type,"
            "permalink,timestamp,username",

        "access_token":
            INSTAGRAM_ACCESS_TOKEN,
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=30
        )

    except requests.RequestException as error:

        print()
        print(
            "⚠️ Verification request failed:"
        )

        print(
            error
        )

        return {}

    try:

        result = response.json()

    except Exception:

        return {}

    print()
    print(
        "Verification response:"
    )

    print(
        result
    )

    if response.status_code == 200:

        success(
            "Published Instagram media verified"
        )

    else:

        print(
            "⚠️ Instagram publish succeeded, "
            "but verification response was not 200."
        )

    return result


# ============================================================
# SAVE RESULT
# ============================================================

def save_publish_result(
    original_data,
    article,
    container_id,
    media_id,
    verification
):

    print()
    line()

    print(
        "STEP 11: Saving Instagram result..."
    )

    line()

    article[
        "instagram_container_id"
    ] = container_id

    article[
        "instagram_media_id"
    ] = media_id

    article[
        "instagram_publish_status"
    ] = "PUBLISHED"

    if verification.get(
        "permalink"
    ):

        article[
            "instagram_permalink"
        ] = verification[
            "permalink"
        ]

    if verification.get(
        "media_type"
    ):

        article[
            "instagram_media_type"
        ] = verification[
            "media_type"
        ]

    if verification.get(
        "media_product_type"
    ):

        article[
            "instagram_media_product_type"
        ] = verification[
            "media_product_type"
        ]

    try:

        with open(
            ARTICLE_QUEUE_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                original_data,
                file,
                ensure_ascii=False,
                indent=2
            )

    except Exception as error:

        fail(
            "Instagram published successfully, "
            "but article_queue.json could not be updated:\n"
            f"{error}"
        )

    success(
        "Instagram publication saved to article_queue.json"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    line()

    print(
        "THRAANSH INSTAGRAM VIDEO PUBLISHER V1"
    )

    line()

    print()
    print(
        "WARNING:"
    )

    print(
        "This script performs a REAL Instagram publication."
    )

    # ========================================================
    # STEP 1
    # ========================================================

    check_environment()

    # ========================================================
    # LOAD STORY
    # ========================================================

    original_data = (
        load_queue()
    )

    articles = (
        extract_articles(
            original_data
        )
    )

    article = (
        find_current_article(
            articles
        )
    )

    # ========================================================
    # STEP 2
    # ========================================================

    verify_rights(
        article
    )

    # ========================================================
    # STEP 3
    # ========================================================

    verify_exact_video(
        article
    )

    # ========================================================
    # STEP 4
    # ========================================================

    public_video_url = (
        verify_public_video_url(
            article
        )
    )

    # ========================================================
    # STEP 5
    # ========================================================

    verify_instagram_account()

    # ========================================================
    # STEP 6
    # ========================================================

    already_published = (
        check_duplicate(
            article
        )
    )

    if already_published:

        print()
        line()

        print(
            "INSTAGRAM RESULT"
        )

        line()

        print(
            "Status: ALREADY PUBLISHED"
        )

        return

    # ========================================================
    # CAPTION
    # ========================================================

    caption = (
        build_caption(
            article
        )
    )

    print()
    line()

    print(
        "INSTAGRAM CAPTION"
    )

    line()

    print()
    print(
        caption
    )

    # ========================================================
    # STEP 7
    # ========================================================

    container_id = (
        create_media_container(
            public_video_url,
            caption
        )
    )

    # ========================================================
    # STEP 8
    # ========================================================

    wait_for_container(
        container_id
    )

    # ========================================================
    # STEP 9
    # ========================================================

    media_id = (
        publish_media(
            container_id
        )
    )

    # ========================================================
    # STEP 10
    # ========================================================

    verification = (
        verify_published_media(
            media_id
        )
    )

    # ========================================================
    # STEP 11
    # ========================================================

    save_publish_result(
        original_data,
        article,
        container_id,
        media_id,
        verification
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print()
    line()

    print(
        "✅ INSTAGRAM PUBLISHING SUCCESSFUL"
    )

    line()

    print()
    print(
        "Instagram Account:"
    )

    print(
        "@thraansh"
    )

    print()
    print(
        "Container ID:"
    )

    print(
        container_id
    )

    print()
    print(
        "Instagram Media ID:"
    )

    print(
        media_id
    )

    permalink = (
        verification.get(
            "permalink"
        )
    )

    if permalink:

        print()
        print(
            "Instagram URL:"
        )

        print(
            permalink
        )

    print()
    print(
        "Status:"
    )

    print(
        "PUBLISHED"
    )

    line()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print(
            "Instagram publishing stopped by user."
        )

        sys.exit(130)