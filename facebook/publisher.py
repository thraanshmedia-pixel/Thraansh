from __future__ import annotations

import json
import os
import sys
import subprocess
import hashlib
from pathlib import Path

import requests
from dotenv import load_dotenv


# =============================================================================
# THRAANSH FACEBOOK VIDEO PUBLISHER V2 AUTO-DERIVATIVE
# SYSTEM USER -> PAGE TOKEN -> VIDEO PUBLISH
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUEUE_FILE = PROJECT_ROOT / "data" / "article_queue.json"
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(
    dotenv_path=ENV_FILE,
    override=True,
)


# =============================================================================
# FACEBOOK CONFIG
# =============================================================================

GRAPH_VERSION = os.getenv(
    "FACEBOOK_GRAPH_VERSION",
    "v26.0",
).strip()

PAGE_ID = os.getenv(
    "FACEBOOK_PAGE_ID",
    "1245874881948298",
).strip()

# IMPORTANT:
# This environment variable now contains the NEVER-expiring
# THRAANSH Automation SYSTEM USER TOKEN.
SYSTEM_USER_TOKEN = os.getenv(
    "FACEBOOK_PAGE_ACCESS_TOKEN",
    "",
).strip()


# =============================================================================
# DISPLAY
# =============================================================================

def line():
    print("=" * 70)


def header(text):
    print()
    line()
    print(text)
    line()
    print()


def fail(message):
    print()
    line()
    print("[ERROR]", message)
    line()
    sys.exit(1)


def ok(message):
    print("[OK]", message)


# =============================================================================
# QUEUE
# =============================================================================

def load_queue():

    if not QUEUE_FILE.exists():
        fail(
            f"Queue file not found:\n{QUEUE_FILE}"
        )

    try:

        with QUEUE_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except Exception as error:

        fail(
            f"Could not read queue:\n{error}"
        )


def extract_articles(data):

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        for key in (
            "articles",
            "items",
            "queue",
            "news",
            "data",
        ):

            value = data.get(key)

            if isinstance(value, list):
                return value

    fail(
        "Could not find articles "
        "inside article_queue.json"
    )


def save_queue(data):

    try:

        temp_file = QUEUE_FILE.with_suffix(
            ".json.tmp"
        )

        with temp_file.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )

        temp_file.replace(
            QUEUE_FILE
        )

    except Exception as error:

        fail(
            f"Could not save queue:\n{error}"
        )


def get_current_article(articles):

    selected = [
        article
        for article in articles
        if article.get(
            "production_selected"
        ) is True
    ]

    if not selected:

        fail(
            "No production_selected "
            "article found."
        )

    return selected[-1]


# =============================================================================
# CONFIG CHECK
# =============================================================================

def validate_config():

    header(
        "FACEBOOK CONFIGURATION"
    )

    if not SYSTEM_USER_TOKEN:

        fail(
            "FACEBOOK_PAGE_ACCESS_TOKEN "
            "is missing from .env"
        )

    if not PAGE_ID:

        fail(
            "FACEBOOK_PAGE_ID "
            "is missing."
        )

    print(
        f"Graph version: {GRAPH_VERSION}"
    )

    print(
        f"Facebook Page ID: {PAGE_ID}"
    )

    ok(
        "Facebook configuration loaded"
    )


# =============================================================================
# RIGHTS CHECK
# =============================================================================

def verify_rights(article):

    header(
        "VERIFYING PUBLISHING RIGHTS"
    )

    status = str(
        article.get(
            "status",
            "",
        )
    ).upper()

    rights_status = str(
        article.get(
            "rights_status",
            "",
        )
    ).upper()

    if (
        status != "RIGHTS_PASS"
        or rights_status != "RIGHTS_PASS"
    ):

        fail(
            "Publishing blocked.\n"
            "Article must have RIGHTS_PASS."
        )

    ok(
        "RIGHTS_PASS confirmed"
    )

    manifest_value = str(
        article.get(
            "rights_manifest_file",
            "",
        )
    ).strip()

    if not manifest_value:

        fail(
            "rights_manifest_file missing."
        )

    manifest_path = Path(
        manifest_value
    )

    if not manifest_path.is_absolute():

        manifest_path = (
            PROJECT_ROOT
            / manifest_path
        )

    manifest_path = manifest_path.resolve()

    if not manifest_path.exists():

        fail(
            "Rights manifest not found:\n"
            f"{manifest_path}"
        )

    ok(
        "Rights manifest confirmed"
    )

    video_value = str(
        article.get(
            "final_video_file",
            "",
        )
    ).strip()

    if not video_value:

        fail(
            "final_video_file missing."
        )

    video_path = Path(
        video_value
    )

    if not video_path.is_absolute():

        video_path = (
            PROJECT_ROOT
            / video_path
        )

    video_path = video_path.resolve()

    if not video_path.exists():

        fail(
            "Final video not found:\n"
            f"{video_path}"
        )

    if video_path.suffix.lower() != ".mp4":

        fail(
            "Final video is not MP4."
        )

    ok(
        "Exact final video confirmed"
    )

    print()
    print("Video:")
    print(video_path)

    print()

    print(
        f"Video size: "
        f"{video_path.stat().st_size / 1024 / 1024:.2f} MB"
    )

    return video_path


# =============================================================================
# VERIFY SYSTEM USER TOKEN
# =============================================================================

def verify_system_user_token():

    header(
        "VERIFYING FACEBOOK SYSTEM USER TOKEN"
    )

    url = (
        f"https://graph.facebook.com/"
        f"{GRAPH_VERSION}/me"
    )

    try:

        response = requests.get(
            url,
            params={
                "fields": "id,name",
                "access_token":
                    SYSTEM_USER_TOKEN,
            },
            timeout=30,
        )

    except requests.RequestException as error:

        fail(
            "Facebook System User "
            "verification failed:\n"
            f"{error}"
        )

    try:
        data = response.json()

    except Exception:

        print(
            response.text
        )

        fail(
            "Facebook returned an invalid "
            "System User response."
        )

    print(
        "HTTP Status:",
        response.status_code,
    )

    if response.status_code != 200:

        print(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            )
        )

        fail(
            "System User token is invalid."
        )

    system_user_id = str(
        data.get(
            "id",
            "",
        )
    ).strip()

    system_user_name = str(
        data.get(
            "name",
            "",
        )
    ).strip()

    if not system_user_id:

        fail(
            "Facebook returned no "
            "System User ID."
        )

    print(
        "System User:",
        system_user_name,
    )

    print(
        "System User ID:",
        system_user_id,
    )

    ok(
        "System User token is valid"
    )

    return {
        "id": system_user_id,
        "name": system_user_name,
    }


# =============================================================================
# GET THRAANSH PAGE ACCESS TOKEN
# =============================================================================

def get_page_access_token():

    header(
        "GETTING THRAANSH PAGE ACCESS TOKEN"
    )

    url = (
        f"https://graph.facebook.com/"
        f"{GRAPH_VERSION}/me/accounts"
    )

    try:

        response = requests.get(
            url,
            params={
                "fields":
                    "id,name,access_token",

                "access_token":
                    SYSTEM_USER_TOKEN,
            },
            timeout=30,
        )

    except requests.RequestException as error:

        fail(
            "Could not retrieve Facebook "
            "Page access token:\n"
            f"{error}"
        )

    try:
        data = response.json()

    except Exception:

        print(
            response.text
        )

        fail(
            "Facebook returned an invalid "
            "Page list response."
        )

    print(
        "HTTP Status:",
        response.status_code,
    )

    if response.status_code != 200:

        print(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            )
        )

        fail(
            "Could not retrieve Facebook Pages "
            "for the System User."
        )

    pages = data.get(
        "data",
        [],
    )

    if not isinstance(
        pages,
        list,
    ):

        fail(
            "Facebook returned invalid "
            "Page data."
        )

    for page in pages:

        returned_id = str(
            page.get(
                "id",
                "",
            )
        ).strip()

        if returned_id != PAGE_ID:
            continue

        page_name = str(
            page.get(
                "name",
                "",
            )
        ).strip()

        page_access_token = str(
            page.get(
                "access_token",
                "",
            )
        ).strip()

        if not page_access_token:

            fail(
                "THRAANSH Page was found, "
                "but Meta returned no "
                "Page access token."
            )

        print(
            "Facebook Page:",
            page_name,
        )

        print(
            "Facebook Page ID:",
            returned_id,
        )

        # NEVER print the Page token.
        ok(
            "THRAANSH Page access token retrieved"
        )

        return page_access_token

    fail(
        "THRAANSH Page was not found "
        "in the System User's accounts.\n\n"
        f"Expected Page ID: {PAGE_ID}"
    )


# =============================================================================
# VERIFY PAGE TOKEN
# =============================================================================

def verify_page_access_token(
    page_access_token,
):

    header(
        "VERIFYING THRAANSH PAGE TOKEN"
    )

    url = (
        f"https://graph.facebook.com/"
        f"{GRAPH_VERSION}/{PAGE_ID}"
    )

    try:

        response = requests.get(
            url,
            params={
                "fields": "id,name",
                "access_token":
                    page_access_token,
            },
            timeout=30,
        )

    except requests.RequestException as error:

        fail(
            "Facebook Page verification "
            "request failed:\n"
            f"{error}"
        )

    try:
        data = response.json()

    except Exception:

        print(
            response.text
        )

        fail(
            "Facebook returned an invalid "
            "Page verification response."
        )

    print(
        "HTTP Status:",
        response.status_code,
    )

    if response.status_code != 200:

        print(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            )
        )

        fail(
            "THRAANSH Page token "
            "verification failed."
        )

    returned_id = str(
        data.get(
            "id",
            "",
        )
    ).strip()

    returned_name = str(
        data.get(
            "name",
            "",
        )
    ).strip()

    print(
        "Facebook Page:",
        returned_name,
    )

    print(
        "Facebook Page ID:",
        returned_id,
    )

    if returned_id != PAGE_ID:

        fail(
            "Wrong Facebook Page returned.\n\n"
            f"Expected Page ID: {PAGE_ID}\n"
            f"Returned Page ID: {returned_id}"
        )

    ok(
        "THRAANSH Page token verified"
    )


# =============================================================================
# DUPLICATE CHECK
# =============================================================================

def duplicate_check(article):

    header(
        "FACEBOOK DUPLICATE PROTECTION"
    )

    existing_id = str(
        article.get(
            "facebook_video_id",
            "",
        )
    ).strip()

    existing_page = str(
        article.get(
            "facebook_page_id",
            "",
        )
    ).strip()

    if (
        existing_id
        and existing_page == PAGE_ID
    ):

        ok(
            "Video already published "
            "to this Facebook Page"
        )

        print(
            "Facebook Video ID:",
            existing_id,
        )

        return True

    ok(
        "No existing upload "
        "for this Facebook Page"
    )

    return False


# =============================================================================
# DESCRIPTION
# =============================================================================

def build_description(article):

    title = str(
        article.get(
            "title",
            "",
        )
    ).strip()

    teaser = str(
        article.get(
            "teaser",
            "",
        )
    ).strip()

    article_url = str(
        article.get(
            "url",
            "",
        )
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

    if article_url:

        parts.append(
            f"Read more: {article_url}"
        )

    parts.append(
        "#THRAANSH"
    )

    return "\n\n".join(
        parts
    )


# =============================================================================
# FACEBOOK PLATFORM DERIVATIVE
# =============================================================================

FACEBOOK_DERIVATIVE_FOLDER = PROJECT_ROOT / "platform_derivatives" / "facebook"
FACEBOOK_DERIVATIVE_FOLDER.mkdir(parents=True, exist_ok=True)

# Single-request Graph uploads have already returned HTTP 413 for large masters
# in this workflow. Keep the delivery derivative comfortably small.
FACEBOOK_DERIVATIVE_TRIGGER_MB = 70.0
FACEBOOK_DERIVATIVE_HARD_MAX_MB = 49.0


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while True:
            chunk = file.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def get_ffmpeg_executable():
    try:
        import imageio_ffmpeg
        executable = imageio_ffmpeg.get_ffmpeg_exe()
        if executable:
            return executable
    except Exception:
        pass
    return "ffmpeg"


def create_facebook_derivative(queue_data, article, master_path):
    size_mb = master_path.stat().st_size / 1024 / 1024
    master_hash = sha256_file(master_path)

    article["facebook_master_video_file"] = str(master_path)
    article["facebook_derivative_source_sha256"] = master_hash

    if size_mb <= FACEBOOK_DERIVATIVE_TRIGGER_MB:
        article["facebook_video_derivative_file"] = ""
        article["facebook_derivative_status"] = "MASTER_USED"
        save_queue(queue_data)
        print()
        ok(f"Facebook delivery: master is {size_mb:.2f} MB; derivative not required.")
        return master_path

    output_path = FACEBOOK_DERIVATIVE_FOLDER / (
        master_path.stem + "_FACEBOOK.mp4"
    )

    existing_ok = False
    if output_path.exists() and output_path.is_file():
        existing_size = output_path.stat().st_size / 1024 / 1024
        if (
            0 < existing_size <= FACEBOOK_DERIVATIVE_HARD_MAX_MB
            and article.get("facebook_derivative_source_sha256") == master_hash
        ):
            existing_ok = True

    if not existing_ok:
        header("CREATING FACEBOOK DELIVERY DERIVATIVE")
        print(f"Approved master size: {size_mb:.2f} MB")
        print("The approved master remains unchanged.")
        print("Creating a smaller Facebook delivery derivative...")

        ffmpeg = get_ffmpeg_executable()
        command = [
            ffmpeg, "-y",
            "-i", str(master_path),
            "-vf", "scale=-2:720",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "29",
            "-maxrate", "1800k",
            "-bufsize", "3600k",
            "-c:a", "aac",
            "-b:a", "96k",
            "-movflags", "+faststart",
            str(output_path),
        ]

        result = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            check=False,
        )
        if result.returncode != 0:
            fail("Automatic Facebook derivative compression failed.")

    if (
        not output_path.exists()
        or not output_path.is_file()
        or output_path.stat().st_size <= 0
    ):
        fail("Facebook derivative was not created correctly.")

    derivative_size_mb = output_path.stat().st_size / 1024 / 1024
    if derivative_size_mb > FACEBOOK_DERIVATIVE_HARD_MAX_MB:
        fail(
            "Compressed Facebook derivative is still too large: "
            f"{derivative_size_mb:.2f} MB"
        )

    article["facebook_video_derivative_file"] = str(output_path)
    article["facebook_derivative_status"] = "READY"
    article["facebook_derivative_source_sha256"] = master_hash
    article["facebook_derivative_sha256"] = sha256_file(output_path)
    article["facebook_derivative_size_mb"] = round(derivative_size_mb, 2)
    save_queue(queue_data)

    print()
    ok("Facebook derivative created and linked to approved master")
    print("Derivative:")
    print(output_path)
    print(f"Derivative size: {derivative_size_mb:.2f} MB")

    return output_path


# =============================================================================
# UPLOAD VIDEO
# =============================================================================

def upload_video(
    article,
    video_path,
    page_access_token,
):

    header(
        "UPLOADING VIDEO TO THRAANSH"
    )

    title = str(
        article.get(
            "title",
            "THRAANSH",
        )
    ).strip()

    description = build_description(
        article
    )

    print(
        "Facebook Page ID:",
        PAGE_ID,
    )

    print()

    print(
        "Title:"
    )

    print(
        title
    )

    print()

    print(
        "Video:"
    )

    print(
        video_path
    )

    print()

    print(
        "Uploading..."
    )

    url = (
        f"https://graph-video.facebook.com/"
        f"{GRAPH_VERSION}/"
        f"{PAGE_ID}/videos"
    )

    data = {

        # IMPORTANT:
        # Video upload uses the derived PAGE token,
        # NOT the System User token.
        "access_token":
            page_access_token,

        "title":
            title[:255],

        "description":
            description,

        "published":
            "true",
    }

    try:

        with video_path.open(
            "rb"
        ) as video_file:

            files = {

                "source": (
                    video_path.name,
                    video_file,
                    "video/mp4",
                )
            }

            response = requests.post(
                url,
                data=data,
                files=files,
                timeout=900,
            )

    except requests.Timeout:

        fail(
            "Facebook upload timed out."
        )

    except requests.RequestException as error:

        fail(
            "Facebook upload failed:\n"
            f"{error}"
        )

    print()

    print(
        "HTTP Status:",
        response.status_code,
    )

    try:
        result = response.json()

    except Exception:

        print(
            response.text
        )

        fail(
            "Facebook returned an invalid "
            "video-upload response."
        )

    if response.status_code not in (
        200,
        201,
    ):

        print()

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
        )

        fail(
            "Facebook video upload failed."
        )

    video_id = str(
        result.get(
            "id",
            "",
        )
    ).strip()

    if not video_id:

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
        )

        fail(
            "Facebook returned no video ID."
        )

    ok(
        "Facebook accepted the video"
    )

    print(
        "Facebook Video ID:",
        video_id,
    )

    return video_id


# =============================================================================
# SAVE RESULT
# =============================================================================

def save_success(
    queue_data,
    article,
    video_id,
    video_path,
):

    article[
        "facebook_video_id"
    ] = video_id

    article[
        "facebook_upload_status"
    ] = "PUBLISHED"

    article[
        "facebook_page_id"
    ] = PAGE_ID

    article[
        "facebook_page_name"
    ] = "Thraansh"

    article[
        "facebook_video_file"
    ] = str(
        video_path
    )

    article[
        "facebook_publish_url"
    ] = (
        f"https://www.facebook.com/"
        f"{PAGE_ID}/videos/"
        f"{video_id}"
    )

    save_queue(
        queue_data
    )

    ok(
        "Facebook publication saved "
        "to article_queue.json"
    )


# =============================================================================
# MAIN
# =============================================================================

def main():

    header(
        "THRAANSH FACEBOOK VIDEO PUBLISHER V2 AUTO-DERIVATIVE"
    )

    validate_config()

    queue_data = load_queue()

    articles = extract_articles(
        queue_data
    )

    article = get_current_article(
        articles
    )

    print(
        "Selected story:"
    )

    print(
        article.get(
            "title",
            "Untitled",
        )
    )

    # -------------------------------------------------------------------------
    # RIGHTS GATE
    # -------------------------------------------------------------------------

    video_path = verify_rights(
        article
    )

    # -------------------------------------------------------------------------
    # SYSTEM USER TOKEN
    # -------------------------------------------------------------------------

    identity = verify_system_user_token()

    print()

    print(
        "Publishing identity:",
        identity.get(
            "name",
            "Unknown",
        )
    )

    # -------------------------------------------------------------------------
    # GET PAGE TOKEN AUTOMATICALLY
    # -------------------------------------------------------------------------

    page_access_token = (
        get_page_access_token()
    )

    # -------------------------------------------------------------------------
    # VERIFY EXACT PAGE
    # -------------------------------------------------------------------------

    verify_page_access_token(
        page_access_token
    )

    # -------------------------------------------------------------------------
    # DUPLICATE PROTECTION
    # -------------------------------------------------------------------------

    if duplicate_check(
        article
    ):

        header(
            "FACEBOOK PUBLISHER COMPLETE"
        )

        print(
            "No duplicate upload created."
        )

        return

    # -------------------------------------------------------------------------
    # PUBLISH
    # -------------------------------------------------------------------------

    delivery_video_path = create_facebook_derivative(
        queue_data,
        article,
        video_path,
    )

    video_id = upload_video(
        article,
        delivery_video_path,
        page_access_token,
    )

    # -------------------------------------------------------------------------
    # SAVE
    # -------------------------------------------------------------------------

    save_success(
        queue_data,
        article,
        video_id,
        delivery_video_path,
    )

    header(
        "THRAANSH FACEBOOK PUBLISHING COMPLETE"
    )

    print(
        "Facebook Page: Thraansh"
    )

    print(
        "Page ID:",
        PAGE_ID,
    )

    print(
        "Video ID:",
        video_id,
    )

    print(
        "Status: PUBLISHED"
    )


if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        fail(
            "Facebook publisher "
            "stopped by user."
        )
