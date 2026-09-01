import json
import os
import sys
import subprocess
import hashlib
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv


# ============================================================
# THRAANSH INSTAGRAM STORAGE UPLOADER V4.1 SAFE-KEY AUTO-DERIVATIVE
#
# PURPOSE:
#
# - Load current production-selected article
# - Require RIGHTS_PASS
# - Require existing rights_manifest_file
# - Require exact final_video_file
# - Upload exact MP4 to Supabase Storage
# - Generate public HTTPS URL
# - Verify public URL
# - Save storage details back to article_queue.json
#
# DOES NOT PUBLISH TO INSTAGRAM
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

INSTAGRAM_DERIVATIVE_FOLDER = (
    PROJECT_ROOT
    / "platform_derivatives"
    / "instagram"
)

INSTAGRAM_DERIVATIVE_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)

# Keep comfortably below the current 50 MB storage ceiling.
INSTAGRAM_TARGET_MB = 42.0
INSTAGRAM_HARD_MAX_MB = 49.0


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv(
    ENV_FILE,
    override=True
)


SUPABASE_URL = (
    os.getenv(
        "SUPABASE_URL",
        ""
    )
    .strip()
    .rstrip("/")
)


SUPABASE_SERVICE_ROLE_KEY = (
    os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY",
        ""
    )
    .strip()
)


SUPABASE_STORAGE_BUCKET = (
    os.getenv(
        "SUPABASE_STORAGE_BUCKET",
        ""
    )
    .strip()
)


# ============================================================
# DISPLAY HELPERS
# ============================================================

def line():
    print("=" * 72)


def fail(message, code=1):
    print()
    line()
    print(f"❌ {message}")
    line()
    sys.exit(code)


def success(message):
    print(f"✅ {message}")


# ============================================================
# STEP 1
# ENVIRONMENT CHECK
# ============================================================

def check_environment():

    print()
    print(
        "STEP 1: Checking Supabase environment variables..."
    )

    if not SUPABASE_URL:
        fail(
            "SUPABASE_URL is missing from .env"
        )

    if not SUPABASE_SERVICE_ROLE_KEY:
        fail(
            "SUPABASE_SERVICE_ROLE_KEY is missing from .env"
        )

    if not SUPABASE_STORAGE_BUCKET:
        fail(
            "SUPABASE_STORAGE_BUCKET is missing from .env"
        )

    print()
    print(
        "SUPABASE_URL: LOADED"
    )

    print(
        "SUPABASE_SERVICE_ROLE_KEY: LOADED"
    )

    print(
        "Service role key length:",
        len(SUPABASE_SERVICE_ROLE_KEY)
    )

    print(
        "SUPABASE_STORAGE_BUCKET:",
        SUPABASE_STORAGE_BUCKET
    )

    success(
        "Supabase environment variables loaded"
    )


# ============================================================
# LOAD ARTICLE QUEUE
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
        "Could not find article list inside article_queue.json"
    )


# ============================================================
# FIND CURRENT STORY
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
        "STEP 2: Verifying publishing rights..."
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
            "Article status is not RIGHTS_PASS.\n"
            f"Current status: {status}"
        )

    if rights_status != "RIGHTS_PASS":
        fail(
            "rights_status is not RIGHTS_PASS.\n"
            f"Current rights_status: {rights_status}"
        )

    # ========================================================
    # IMPORTANT:
    # This is the actual field used by THRAANSH rights checker.
    # ========================================================

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

    manifest_path = manifest_path.resolve()

    print()
    print(
        "Rights manifest:"
    )

    print(
        manifest_path
    )

    if not manifest_path.exists():
        fail(
            "Rights manifest file does not exist:\n"
            f"{manifest_path}"
        )

    if not manifest_path.is_file():
        fail(
            "Rights manifest path is not a file:\n"
            f"{manifest_path}"
        )

    success(
        "RIGHTS_PASS confirmed"
    )

    success(
        "rights_manifest_file confirmed"
    )

    # ========================================================
    # OPTIONAL WARNINGS
    # ========================================================

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

        for warning in warnings:
            print(
                f"⚠️ {warning}"
            )


# ============================================================
# STEP 3
# EXACT VIDEO CHECK
# ============================================================

def get_exact_video(article):

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
            "final_video_file is missing from article_queue.json"
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
            "Exact final_video_file does not exist:\n"
            f"{video_path}"
        )

    if not video_path.is_file():
        fail(
            "final_video_file is not a file:\n"
            f"{video_path}"
        )

    if video_path.suffix.lower() != ".mp4":
        fail(
            "final_video_file is not MP4:\n"
            f"{video_path}"
        )

    file_size = (
        video_path
        .stat()
        .st_size
    )

    if file_size <= 0:
        fail(
            "Final video file is empty."
        )

    size_mb = (
        file_size
        / 1024
        / 1024
    )

    print()
    print(
        "Exact video selected:"
    )

    print(
        video_path
    )

    print()

    print(
        f"Video size: {size_mb:.2f} MB"
    )

    success(
        "Exact rights-approved master final_video_file confirmed"
    )

    return video_path



# ============================================================
# INSTAGRAM PLATFORM DERIVATIVE
# ============================================================

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


def save_queue_atomic(data):

    temp_file = ARTICLE_QUEUE_FILE.with_suffix(
        ".json.tmp"
    )

    with temp_file.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

    temp_file.replace(
        ARTICLE_QUEUE_FILE
    )


def create_instagram_derivative(
    original_data,
    article,
    master_path
):

    size_mb = (
        master_path.stat().st_size
        / 1024
        / 1024
    )

    master_hash = sha256_file(
        master_path
    )

    # The approved master remains canonical. We only create a delivery
    # derivative when Instagram/Supabase needs a smaller file.
    if size_mb <= INSTAGRAM_TARGET_MB:

        article[
            "instagram_master_video_file"
        ] = str(master_path)

        article[
            "instagram_video_derivative_file"
        ] = ""

        article[
            "instagram_derivative_status"
        ] = "MASTER_USED"

        article[
            "instagram_derivative_source_sha256"
        ] = master_hash

        save_queue_atomic(
            original_data
        )

        print()
        print(
            "Instagram delivery:"
        )

        print(
            "Master is already below "
            f"{INSTAGRAM_TARGET_MB:.0f} MB; no derivative needed."
        )

        return master_path

    output_path = (
        INSTAGRAM_DERIVATIVE_FOLDER
        / (
            master_path.stem
            + "_INSTAGRAM.mp4"
        )
    )

    existing_ok = False

    if output_path.exists():

        existing_size = (
            output_path.stat().st_size
            / 1024
            / 1024
        )

        if (
            existing_size > 0
            and
            existing_size <= INSTAGRAM_HARD_MAX_MB
            and
            article.get(
                "instagram_derivative_source_sha256"
            ) == master_hash
        ):

            existing_ok = True

    if not existing_ok:

        print()
        print(
            "Master is too large for Instagram storage."
        )

        print(
            "Creating automatic Instagram derivative..."
        )

        ffmpeg = get_ffmpeg_executable()

        # Two-pass-like CRF compression is unnecessary here; CRF 29 with
        # 720p/H.264/AAC is reliable for the short THRAANSH news videos.
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(master_path),
            "-vf",
            "scale=-2:720",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "29",
            "-maxrate",
            "1800k",
            "-bufsize",
            "3600k",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

        result = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            check=False
        )

        if result.returncode != 0:

            fail(
                "Automatic Instagram derivative compression failed."
            )

    if (
        not output_path.exists()
        or
        not output_path.is_file()
        or
        output_path.stat().st_size <= 0
    ):

        fail(
            "Instagram derivative was not created correctly."
        )

    derivative_size_mb = (
        output_path.stat().st_size
        / 1024
        / 1024
    )

    if derivative_size_mb > INSTAGRAM_HARD_MAX_MB:

        fail(
            "Compressed Instagram derivative is still too large: "
            f"{derivative_size_mb:.2f} MB"
        )

    article[
        "instagram_master_video_file"
    ] = str(master_path)

    article[
        "instagram_video_derivative_file"
    ] = str(output_path)

    article[
        "instagram_derivative_status"
    ] = "READY"

    article[
        "instagram_derivative_source_sha256"
    ] = master_hash

    article[
        "instagram_derivative_sha256"
    ] = sha256_file(
        output_path
    )

    article[
        "instagram_derivative_size_mb"
    ] = round(
        derivative_size_mb,
        2
    )

    save_queue_atomic(
        original_data
    )

    print()
    success(
        "Instagram derivative created and linked to approved master"
    )

    print(
        "Derivative:"
    )

    print(
        output_path
    )

    print(
        f"Derivative size: {derivative_size_mb:.2f} MB"
    )

    return output_path


# ============================================================
# CREATE STORAGE OBJECT PATH
# ============================================================

def safe_storage_component(value, fallback="story"):
    """
    Convert a user/source-derived value into a conservative ASCII-only
    Supabase Storage key component.

    This deliberately removes curly quotes and other Unicode punctuation
    rather than relying on URL encoding, because the Storage API can reject
    otherwise valid-looking encoded object keys.
    """
    value = str(value or "").strip()

    # Normalize common punctuation before ASCII conversion.
    value = (
        value
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )

    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")

    # Keep only conservative storage-key characters.
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    value = re.sub(r"_+", "_", value)
    value = value.strip("._-")

    return value or fallback


def create_storage_path(
    article,
    video_path
):

    article_id = (
        article.get("id")
        or article.get("news_id")
        or article.get("article_id")
        or "story"
    )

    safe_id = safe_storage_component(
        article_id,
        fallback="story"
    )

    original_name = video_path.name
    stem = safe_storage_component(
        video_path.stem,
        fallback="thraansh_video"
    )

    # The delivery file is always MP4 at this stage.
    filename = f"{stem}.mp4"

    object_path = (
        f"instagram/"
        f"{safe_id}/"
        f"{filename}"
    )

    print()
    print("Storage-key safety:")
    print("Original filename:")
    print(original_name)
    print("Safe storage filename:")
    print(filename)

    return object_path


# ============================================================
# STEP 4
# UPLOAD VIDEO TO SUPABASE
# ============================================================

def upload_to_supabase(
    video_path,
    object_path
):

    print()
    line()

    print(
        "STEP 4: Uploading video to Supabase Storage..."
    )

    line()

    encoded_object_path = quote(
        object_path,
        safe="/"
    )

    upload_url = (
        f"{SUPABASE_URL}"
        f"/storage/v1/object/"
        f"{SUPABASE_STORAGE_BUCKET}/"
        f"{encoded_object_path}"
    )

    headers = {

        "apikey":
            SUPABASE_SERVICE_ROLE_KEY,

        "Authorization":
            f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",

        "Content-Type":
            "video/mp4",

        "x-upsert":
            "true",
    }

    print()
    print(
        "Bucket:"
    )

    print(
        SUPABASE_STORAGE_BUCKET
    )

    print()
    print(
        "Storage object:"
    )

    print(
        object_path
    )

    print()
    print(
        "Starting upload..."
    )

    try:

        with open(
            video_path,
            "rb"
        ) as video_file:

            response = requests.post(
                upload_url,
                headers=headers,
                data=video_file,
                timeout=900
            )

    except requests.RequestException as error:

        fail(
            "Supabase upload request failed:\n"
            f"{error}"
        )

    print()
    print(
        "Upload HTTP Status:",
        response.status_code
    )

    if response.status_code not in (
        200,
        201
    ):

        print()
        print(
            "Supabase response:"
        )

        try:
            print(
                response.json()
            )

        except Exception:
            print(
                response.text
            )

        fail(
            "Supabase video upload failed."
        )

    print()
    print(
        "Supabase response:"
    )

    try:
        print(
            response.json()
        )

    except Exception:
        print(
            response.text
        )

    success(
        "Video uploaded to Supabase Storage"
    )


# ============================================================
# CREATE PUBLIC VIDEO URL
# ============================================================

def create_public_url(object_path):

    encoded_object_path = quote(
        object_path,
        safe="/"
    )

    return (
        f"{SUPABASE_URL}"
        f"/storage/v1/object/public/"
        f"{SUPABASE_STORAGE_BUCKET}/"
        f"{encoded_object_path}"
    )


# ============================================================
# STEP 5
# VERIFY PUBLIC VIDEO URL
# ============================================================

def verify_public_url(public_url):

    print()
    line()

    print(
        "STEP 5: Verifying public video URL..."
    )

    line()

    print()
    print(
        "Public URL:"
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
            "Could not reach public Supabase URL:\n"
            f"{error}"
        )

    print()
    print(
        "Public URL HTTP Status:",
        response.status_code
    )

    if response.status_code not in (
        200,
        206
    ):

        response.close()

        fail(
            "Public Supabase video URL is not reachable."
        )

    content_type = (
        response.headers
        .get(
            "Content-Type",
            ""
        )
        .lower()
    )

    print()
    print(
        "Content-Type:",
        content_type
    )

    if (
        "video" not in content_type
        and
        "octet-stream" not in content_type
    ):

        print()
        print(
            "⚠️ Unexpected Content-Type returned."
        )

    response.close()

    success(
        "Public video URL is reachable"
    )


# ============================================================
# STEP 6
# SAVE QUEUE
# ============================================================

def save_queue(
    original_data,
    article,
    object_path,
    public_url
):

    print()
    line()

    print(
        "STEP 6: Updating article_queue.json..."
    )

    line()

    article[
        "instagram_storage_bucket"
    ] = SUPABASE_STORAGE_BUCKET

    article[
        "instagram_storage_object"
    ] = object_path

    article[
        "instagram_video_url"
    ] = public_url

    article[
        "instagram_storage_status"
    ] = "UPLOADED"

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
            "Video uploaded successfully, "
            "but article_queue.json could not be updated:\n"
            f"{error}"
        )

    success(
        "article_queue.json updated"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    line()

    print(
        "THRAANSH INSTAGRAM STORAGE UPLOADER V4.1 SAFE-KEY AUTO-DERIVATIVE"
    )

    line()

    print()
    print(
        "This script uploads the exact rights-approved "
        "final video to Supabase Storage."
    )

    print(
        "It does NOT publish anything to Instagram."
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

    video_path = (
        get_exact_video(
            article
        )
    )

    delivery_video_path = (
        create_instagram_derivative(
            original_data,
            article,
            video_path
        )
    )

    # ========================================================
    # STORAGE PATH
    # ========================================================

    object_path = (
        create_storage_path(
            article,
            delivery_video_path
        )
    )

    # ========================================================
    # STEP 4
    # ========================================================

    upload_to_supabase(
        delivery_video_path,
        object_path
    )

    # ========================================================
    # PUBLIC URL
    # ========================================================

    public_url = (
        create_public_url(
            object_path
        )
    )

    # ========================================================
    # STEP 5
    # ========================================================

    verify_public_url(
        public_url
    )

    # ========================================================
    # STEP 6
    # ========================================================

    save_queue(
        original_data,
        article,
        object_path,
        public_url
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print()
    line()

    print(
        "✅ INSTAGRAM STORAGE PREPARATION SUCCESSFUL"
    )

    line()

    print()
    print(
        "Rights check:"
    )

    print(
        "PASS"
    )

    print()
    print(
        "Supabase bucket:"
    )

    print(
        SUPABASE_STORAGE_BUCKET
    )

    print()
    print(
        "Storage object:"
    )

    print(
        object_path
    )

    print()
    print(
        "Public Instagram video URL:"
    )

    print(
        public_url
    )

    print()
    print(
        "Storage status:"
    )

    print(
        "UPLOADED"
    )

    print()
    print(
        "Instagram publishing:"
    )

    print(
        "NOT RUN YET"
    )

    print()
    print(
        "NEXT:"
    )

    print(
        "instagram/publisher.py"
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
            "Instagram storage upload stopped by user."
        )

        sys.exit(130)
