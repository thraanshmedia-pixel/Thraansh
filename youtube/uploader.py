import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# ============================================================
# THRAANSH YOUTUBE PUBLIC UPLOADER V3
# ============================================================
#
# PURPOSE:
#
# - Find current production-selected THRAANSH story
# - Require RIGHTS_PASS
# - Require rights manifest
# - Require exact final_video_file
# - Prevent duplicate YouTube uploads
# - Upload video directly as PUBLIC
# - Save YouTube Video ID
# - Save status as PUBLISHED
#
# IMPORTANT:
#
# RIGHTS FAILURE = NO YOUTUBE UPLOAD
#
# NO "NEWEST MP4" FALLBACK IS USED.
#
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

ENV_FILE = (
    PROJECT_ROOT
    / ".env"
)

QUEUE_FILE = (
    PROJECT_ROOT
    / "data"
    / "article_queue.json"
)

TOKEN_FILE = (
    PROJECT_ROOT
    / "youtube"
    / "token.json"
)


# ============================================================
# YOUTUBE SETTINGS
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

PRIVACY_STATUS = "public"

DEFAULT_CATEGORY_ID = "25"


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv(
    ENV_FILE,
    override=True
)

YOUTUBE_CLIENT_ID = str(
    os.getenv(
        "YOUTUBE_CLIENT_ID",
        ""
    )
).strip()

YOUTUBE_CLIENT_SECRET = str(
    os.getenv(
        "YOUTUBE_CLIENT_SECRET",
        ""
    )
).strip()


# ============================================================
# DISPLAY HELPERS
# ============================================================

def line():

    print(
        "=" * 72
    )


def header(text):

    print()
    line()
    print(text)
    line()
    print()


def success(message):

    print(
        f"✅ {message}"
    )


def warning(message):

    print(
        f"⚠️ {message}"
    )


def fail(message, code=1):

    print()
    line()

    print(
        f"❌ {message}"
    )

    line()

    sys.exit(code)


# ============================================================
# LOAD ARTICLE QUEUE
# ============================================================

def load_queue():

    if not QUEUE_FILE.exists():

        fail(
            "article_queue.json was not found:\n"
            f"{QUEUE_FILE}"
        )

    try:

        with open(
            QUEUE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

    except Exception as error:

        fail(
            "Could not read article_queue.json:\n"
            f"{error}"
        )

    return data


# ============================================================
# EXTRACT ARTICLE LIST
# ============================================================

def extract_articles(data):

    if isinstance(
        data,
        list
    ):

        return data

    if isinstance(
        data,
        dict
    ):

        for key in (
            "articles",
            "items",
            "queue",
            "news",
            "data",
        ):

            value = data.get(
                key
            )

            if isinstance(
                value,
                list
            ):

                return value

    fail(
        "Could not locate article list "
        "inside article_queue.json."
    )


# ============================================================
# CURRENT PRODUCTION ARTICLE
# ============================================================

def find_current_article(
    articles
):

    selected = []

    for article in articles:

        if not isinstance(
            article,
            dict
        ):

            continue

        if article.get(
            "production_selected"
        ) is True:

            selected.append(
                article
            )

    if not selected:

        fail(
            "No production-selected "
            "article was found."
        )

    article = selected[-1]

    header(
        "CURRENT THRAANSH STORY"
    )

    print(
        article.get(
            "title",
            "Untitled Story"
        )
    )

    return article


# ============================================================
# RIGHTS CHECK
# ============================================================

def verify_rights(
    article
):

    header(
        "STEP 1: VERIFYING PUBLISHING RIGHTS"
    )

    status = str(
        article.get(
            "status",
            ""
        )
    ).strip().upper()

    rights_status = str(
        article.get(
            "rights_status",
            ""
        )
    ).strip().upper()

    print(
        "Article status:",
        status
    )

    print(
        "Rights status:",
        rights_status
    )

    print()

    if status != "RIGHTS_PASS":

        fail(
            "Article status is not RIGHTS_PASS.\n"
            "YouTube publication BLOCKED."
        )

    if rights_status != "RIGHTS_PASS":

        fail(
            "rights_status is not RIGHTS_PASS.\n"
            "YouTube publication BLOCKED."
        )

    manifest_value = (
        article.get(
            "rights_manifest_file"
        )
    )

    if not manifest_value:

        fail(
            "rights_manifest_file is missing.\n"
            "YouTube publication BLOCKED."
        )

    manifest_path = Path(
        str(
            manifest_value
        )
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

    if not manifest_path.is_file():

        fail(
            "Rights manifest path is not a file:\n"
            f"{manifest_path}"
        )

    print(
        "Rights manifest:"
    )

    print(
        manifest_path
    )

    print()

    success(
        "RIGHTS_PASS confirmed"
    )

    success(
        "rights_manifest_file confirmed"
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
            "Rights / editorial warnings:"
        )

        for item in warnings:

            warning(
                str(item)
            )

    return manifest_path


# ============================================================
# EXACT FINAL VIDEO
# ============================================================

def verify_final_video(
    article
):

    header(
        "STEP 2: VERIFYING EXACT FINAL VIDEO"
    )

    video_value = (
        article.get(
            "final_video_file"
        )
    )

    if not video_value:

        fail(
            "final_video_file is missing.\n"
            "YouTube publication BLOCKED."
        )

    video_path = Path(
        str(
            video_value
        )
    )

    if not video_path.is_absolute():

        video_path = (
            PROJECT_ROOT
            / video_path
        )

    video_path = (
        video_path.resolve()
    )

    if not video_path.exists():

        fail(
            "Exact final video does not exist:\n"
            f"{video_path}"
        )

    if not video_path.is_file():

        fail(
            "final_video_file is not a file."
        )

    if (
        video_path.suffix.lower()
        != ".mp4"
    ):

        fail(
            "final_video_file is not MP4."
        )

    size_bytes = (
        video_path
        .stat()
        .st_size
    )

    if size_bytes <= 0:

        fail(
            "Final video file is empty."
        )

    size_mb = (
        size_bytes
        / 1024
        / 1024
    )

    print(
        "Exact video:"
    )

    print(
        video_path
    )

    print()

    print(
        f"Video size: "
        f"{size_mb:.2f} MB"
    )

    print()

    success(
        "Exact final_video_file confirmed"
    )

    return video_path


# ============================================================
# DUPLICATE PROTECTION
# ============================================================

def check_duplicate(
    article
):

    header(
        "STEP 3: YOUTUBE DUPLICATE PROTECTION"
    )

    existing_video_id = str(
        article.get(
            "youtube_video_id",
            ""
        )
    ).strip()

    existing_status = str(
        article.get(
            "youtube_upload_status",
            ""
        )
    ).strip().upper()

    if existing_video_id:

        print(
            "Existing YouTube Video ID:"
        )

        print(
            existing_video_id
        )

        print()

        print(
            "Existing YouTube status:"
        )

        print(
            existing_status
            or "UNKNOWN"
        )

        print()

        warning(
            "This story already has a YouTube video."
        )

        print(
            "No duplicate YouTube upload "
            "will be performed."
        )

        return True

    success(
        "No existing YouTube upload detected"
    )

    return False


# ============================================================
# OAUTH CLIENT CONFIG
# ============================================================

def build_client_config():

    if not YOUTUBE_CLIENT_ID:

        fail(
            "YOUTUBE_CLIENT_ID is missing "
            "from .env"
        )

    if not YOUTUBE_CLIENT_SECRET:

        fail(
            "YOUTUBE_CLIENT_SECRET is missing "
            "from .env"
        )

    return {
        "installed": {
            "client_id":
                YOUTUBE_CLIENT_ID,

            "client_secret":
                YOUTUBE_CLIENT_SECRET,

            "auth_uri":
                "https://accounts.google.com/o/oauth2/auth",

            "token_uri":
                "https://oauth2.googleapis.com/token",

            "auth_provider_x509_cert_url":
                "https://www.googleapis.com/oauth2/v1/certs",

            "redirect_uris": [
                "http://localhost"
            ],
        }
    }


# ============================================================
# YOUTUBE AUTHENTICATION
# ============================================================

def authenticate_youtube():

    header(
        "STEP 4: YOUTUBE AUTHENTICATION"
    )

    credentials = None

    if TOKEN_FILE.exists():

        try:

            credentials = (
                Credentials
                .from_authorized_user_file(
                    str(
                        TOKEN_FILE
                    ),
                    SCOPES
                )
            )

        except Exception as error:

            warning(
                "Existing YouTube token "
                "could not be loaded."
            )

            print(
                error
            )

            credentials = None

    if (
        credentials
        and credentials.expired
        and credentials.refresh_token
    ):

        print(
            "Refreshing YouTube token..."
        )

        try:

            credentials.refresh(
                Request()
            )

        except Exception as error:

            warning(
                "YouTube token refresh failed."
            )

            print(
                error
            )

            credentials = None

    if (
        credentials is None
        or not credentials.valid
    ):

        print(
            "Starting YouTube OAuth..."
        )

        client_config = (
            build_client_config()
        )

        try:

            flow = (
                InstalledAppFlow
                .from_client_config(
                    client_config,
                    SCOPES
                )
            )

            credentials = (
                flow.run_local_server(
                    port=0,
                    prompt="consent",
                    access_type="offline"
                )
            )

        except Exception as error:

            fail(
                "YouTube OAuth failed:\n"
                f"{error}"
            )

    try:

        TOKEN_FILE.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            TOKEN_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(
                credentials.to_json()
            )

    except Exception as error:

        warning(
            "Could not save YouTube token."
        )

        print(
            error
        )

    try:

        youtube = build(
            "youtube",
            "v3",
            credentials=credentials,
            cache_discovery=False
        )

    except Exception as error:

        fail(
            "Could not create YouTube API client:\n"
            f"{error}"
        )

    success(
        "YouTube authentication successful"
    )

    return youtube


# ============================================================
# TITLE
# ============================================================

def build_title(
    article
):

    title = str(
        article.get(
            "title",
            ""
        )
    ).strip()

    if not title:

        title = (
            "THRAANSH News Update"
        )

    # YouTube title maximum is 100 characters.
    if len(title) > 100:

        title = (
            title[:97]
            .rstrip()
            + "..."
        )

    return title


# ============================================================
# DESCRIPTION
# ============================================================

def build_description(
    article
):

    title = str(
        article.get(
            "title",
            ""
        )
    ).strip()

    teaser = str(
        article.get(
            "teaser",
            ""
        )
        or article.get(
            "summary",
            ""
        )
    ).strip()

    publisher = str(
        article.get(
            "publisher",
            ""
        )
    ).strip()

    source_url = str(
        article.get(
            "url",
            ""
        )
        or article.get(
            "source_url",
            ""
        )
    ).strip()

    description_parts = []

    if title:

        description_parts.append(
            title
        )

    if teaser:

        description_parts.append(
            teaser
        )

    description_parts.append(
        "THRAANSH brings you the latest "
        "news and updates from India "
        "and around the world."
    )

    if publisher:

        description_parts.append(
            f"Source: {publisher}"
        )

    if source_url:

        description_parts.append(
            f"Original report: {source_url}"
        )

    description_parts.append(
        "Follow THRAANSH for News, "
        "Business, Technology, Sports, "
        "Entertainment and more."
    )

    description_parts.append(
        "#THRAANSH #News #LatestNews"
    )

    description = (
        "\n\n".join(
            description_parts
        )
    )

    return description


# ============================================================
# TAGS
# ============================================================

def build_tags(
    article
):

    tags = [
        "THRAANSH",
        "news",
        "latest news",
        "India news",
        "world news",
        "Hindi news",
    ]

    category = str(
        article.get(
            "category_slug",
            ""
        )
    ).strip()

    if category:

        cleaned_category = (
            category
            .replace(
                "-",
                " "
            )
            .strip()
        )

        if cleaned_category:

            tags.append(
                cleaned_category
            )

    # Remove duplicates while preserving order.
    unique_tags = []

    seen = set()

    for tag in tags:

        key = tag.lower()

        if key in seen:
            continue

        seen.add(
            key
        )

        unique_tags.append(
            tag
        )

    return unique_tags


# ============================================================
# PUBLIC YOUTUBE UPLOAD
# ============================================================

def upload_video(
    youtube,
    article,
    video_path
):

    header(
        "STEP 5: PUBLISHING VIDEO TO YOUTUBE"
    )

    title = (
        build_title(
            article
        )
    )

    description = (
        build_description(
            article
        )
    )

    tags = (
        build_tags(
            article
        )
    )

    print(
        "YouTube title:"
    )

    print(
        title
    )

    print()

    print(
        "Privacy:"
    )

    print(
        "PUBLIC"
    )

    print()

    print(
        "Video:"
    )

    print(
        video_path
    )

    print()

    # ========================================================
    # YOUTUBE REQUEST BODY
    # ========================================================
    #
    # This block fixes the syntax error around:
    #
    # "selfDeclaredMadeForKids": False
    #
    # ========================================================

    request_body = {

        "snippet": {

            "title":
                title,

            "description":
                description,

            "tags":
                tags,

            "categoryId":
                DEFAULT_CATEGORY_ID,
        },

        "status": {

            "privacyStatus":
                PRIVACY_STATUS,

            "selfDeclaredMadeForKids":
                False,
        },
    }

    try:

        media = MediaFileUpload(
            str(
                video_path
            ),
            mimetype="video/mp4",
            resumable=True,
            chunksize=-1
        )

        request = (
            youtube
            .videos()
            .insert(
                part="snippet,status",
                body=request_body,
                media_body=media
            )
        )

    except Exception as error:

        fail(
            "Could not create YouTube "
            "upload request:\n"
            f"{error}"
        )

    print(
        "Starting YouTube PUBLIC upload..."
    )

    print()

    response = None

    try:

        while response is None:

            upload_status, response = (
                request.next_chunk()
            )

            if upload_status:

                percentage = (
                    int(
                        upload_status.progress()
                        * 100
                    )
                )

                print(
                    f"YouTube upload progress: "
                    f"{percentage}%"
                )

    except Exception as error:

        fail(
            "YouTube upload failed:\n"
            f"{error}"
        )

    if not isinstance(
        response,
        dict
    ):

        fail(
            "YouTube returned an invalid "
            "upload response."
        )

    video_id = str(
        response.get(
            "id",
            ""
        )
    ).strip()

    if not video_id:

        print(
            response
        )

        fail(
            "YouTube upload response "
            "did not contain a Video ID."
        )

    print()

    success(
        "YouTube upload completed"
    )

    print()

    print(
        "YouTube Video ID:"
    )

    print(
        video_id
    )

    return video_id


# ============================================================
# VERIFY YOUTUBE VIDEO
# ============================================================

def verify_youtube_video(
    youtube,
    video_id
):

    header(
        "STEP 6: VERIFYING YOUTUBE PUBLICATION"
    )

    try:

        request = (
            youtube
            .videos()
            .list(
                part="status,snippet",
                id=video_id
            )
        )

        response = (
            request.execute()
        )

    except Exception as error:

        fail(
            "YouTube uploaded the video, "
            "but verification failed:\n"
            f"{error}"
        )

    items = (
        response.get(
            "items",
            []
        )
    )

    if not items:

        fail(
            "YouTube Video ID could not "
            "be verified after upload."
        )

    video = items[0]

    status_data = (
        video.get(
            "status",
            {}
        )
    )

    privacy_status = str(
        status_data.get(
            "privacyStatus",
            ""
        )
    ).strip().lower()

    upload_status = str(
        status_data.get(
            "uploadStatus",
            ""
        )
    ).strip()

    print(
        "YouTube Video ID:"
    )

    print(
        video_id
    )

    print()

    print(
        "Privacy status:"
    )

    print(
        privacy_status
    )

    print()

    print(
        "Upload status:"
    )

    print(
        upload_status
    )

    if (
        privacy_status
        != "public"
    ):

        fail(
            "YouTube video was uploaded, "
            "but it is NOT PUBLIC.\n"
            f"Returned privacy status: "
            f"{privacy_status}"
        )

    success(
        "YouTube PUBLIC status confirmed"
    )

    return video


# ============================================================
# SAVE YOUTUBE RESULT
# ============================================================

def save_result(
    original_data,
    article,
    video_id
):

    header(
        "STEP 7: UPDATING ARTICLE QUEUE"
    )

    article[
        "youtube_video_id"
    ] = video_id

    article[
        "youtube_url"
    ] = (
        "https://www.youtube.com/watch?v="
        f"{video_id}"
    )

    article[
        "youtube_upload_status"
    ] = "PUBLISHED"

    article[
        "youtube_privacy_status"
    ] = "PUBLIC"

    try:

        with open(
            QUEUE_FILE,
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
            "YouTube publication succeeded, "
            "but article_queue.json could "
            "not be updated:\n"
            f"{error}"
        )

    success(
        "article_queue.json updated"
    )


# ============================================================
# ALREADY-PUBLISHED RESULT
# ============================================================

def show_existing_result(
    article
):

    video_id = str(
        article.get(
            "youtube_video_id",
            ""
        )
    ).strip()

    upload_status = str(
        article.get(
            "youtube_upload_status",
            ""
        )
    ).strip()

    header(
        "YOUTUBE RESULT"
    )

    print(
        "Status:"
    )

    print(
        "ALREADY UPLOADED"
    )

    print()

    print(
        "Stored upload status:"
    )

    print(
        upload_status
        or "UNKNOWN"
    )

    print()

    print(
        "YouTube Video ID:"
    )

    print(
        video_id
    )

    print()

    print(
        "YouTube URL:"
    )

    print(
        "https://www.youtube.com/watch?v="
        f"{video_id}"
    )

    print()

    print(
        "No duplicate upload performed."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    header(
        "THRAANSH YOUTUBE PUBLIC UPLOADER V3"
    )

    print(
        "Publishing mode:"
    )

    print(
        "PUBLIC"
    )

    print()

    print(
        "Safety mode:"
    )

    print(
        "FAIL CLOSED"
    )

    # ========================================================
    # LOAD CURRENT ARTICLE
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
    # RIGHTS GATE
    # ========================================================

    verify_rights(
        article
    )

    # ========================================================
    # EXACT VIDEO
    # ========================================================

    video_path = (
        verify_final_video(
            article
        )
    )

    # ========================================================
    # DUPLICATE PROTECTION
    # ========================================================

    already_uploaded = (
        check_duplicate(
            article
        )
    )

    if already_uploaded:

        show_existing_result(
            article
        )

        return

    # ========================================================
    # AUTHENTICATE
    # ========================================================

    youtube = (
        authenticate_youtube()
    )

    # ========================================================
    # REAL PUBLIC UPLOAD
    # ========================================================

    video_id = (
        upload_video(
            youtube,
            article,
            video_path
        )
    )

    # ========================================================
    # VERIFY PUBLIC
    # ========================================================

    verify_youtube_video(
        youtube,
        video_id
    )

    # ========================================================
    # SAVE
    # ========================================================

    save_result(
        original_data,
        article,
        video_id
    )

    # ========================================================
    # COMPLETE
    # ========================================================

    header(
        "✅ YOUTUBE PUBLICATION SUCCESSFUL"
    )

    print(
        "YouTube Video ID:"
    )

    print(
        video_id
    )

    print()

    print(
        "YouTube URL:"
    )

    print(
        "https://www.youtube.com/watch?v="
        f"{video_id}"
    )

    print()

    print(
        "Privacy:"
    )

    print(
        "PUBLIC"
    )

    print()

    print(
        "Queue status:"
    )

    print(
        "PUBLISHED"
    )

    print()

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
            "YouTube publishing stopped "
            "by user."
        )

        sys.exit(130)