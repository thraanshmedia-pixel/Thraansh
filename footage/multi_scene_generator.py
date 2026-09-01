import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import imageio_ffmpeg
import requests
from dotenv import load_dotenv
from PIL import Image


# ============================================================
# THRAANSH FAST MULTI-SOURCE STORY MEDIA GENERATOR
#
# SOURCE ORDER:
#
# 1. Pexels VIDEO
# 2. Pixabay VIDEO
# 3. Wikimedia VIDEO
# 4. Wikimedia IMAGE
#
# IMPORTANT:
#
# - No source can block for hours.
# - Strict short timeouts.
# - Very limited retries.
# - Corrupt files rejected.
# - HTML/error files rejected.
# - Audio-only files rejected.
# - Duplicate media rejected.
# - Story-specific scene queries only.
# - No random presenter/template footage.
#
# INPUT:
# SCENE_PLAN_READY
# SCENE_FOOTAGE_FAILED
# MULTI_MEDIA_FAILED
#
# OUTPUT:
# MULTI_MEDIA_READY
# ============================================================


# ============================================================
# PROJECT
# ============================================================

PROJECT_FOLDER = Path(__file__).resolve().parents[1]

QUEUE_FILE = (
    PROJECT_FOLDER
    / "data"
    / "article_queue.json"
)

OUTPUT_FOLDER = (
    PROJECT_FOLDER
    / "scene_footage"
)

OUTPUT_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv(
    PROJECT_FOLDER
    / ".env",
    override=True
)


PEXELS_API_KEY = os.getenv(
    "PEXELS_API_KEY",
    ""
).strip()


PIXABAY_API_KEY = os.getenv(
    "PIXABAY_API_KEY",
    ""
).strip()


# ============================================================
# FFMPEG
# ============================================================

FFMPEG_EXE = Path(
    imageio_ffmpeg.get_ffmpeg_exe()
)


# ============================================================
# API ENDPOINTS
# ============================================================

PEXELS_VIDEO_API = (
    "https://api.pexels.com/videos/search"
)

PIXABAY_VIDEO_API = (
    "https://pixabay.com/api/videos/"
)

WIKIMEDIA_API = (
    "https://commons.wikimedia.org/w/api.php"
)


# ============================================================
# REQUEST SETTINGS
# ============================================================

# Critical:
# These limits prevent the old 10-hour behaviour.

API_TIMEOUT = 12

DOWNLOAD_TIMEOUT = 40

WIKIMEDIA_MAX_RETRIES = 2

DOWNLOAD_MAX_RETRIES = 2

SEARCH_RESULTS_LIMIT = 10

BETWEEN_REQUESTS_DELAY = 0.25


# ============================================================
# USER AGENT
# ============================================================

USER_AGENT = (
    "THRAANSH-News-Automation/3.0 "
    "(licensed story media retrieval)"
)


BASE_HEADERS = {
    "User-Agent": USER_AGENT,
}


# ============================================================
# FILE EXTENSIONS
# ============================================================

VIDEO_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mov",
    ".mpeg",
    ".mpg",
    ".ogv",
    ".mkv",
}

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}

BLOCKED_EXTENSIONS = {
    ".ogg",
    ".oga",
    ".mp3",
    ".wav",
    ".flac",
    ".opus",
    ".m4a",
    ".aac",
    ".svg",
}


# ============================================================
# WIKIMEDIA LICENSES
# ============================================================

ALLOWED_LICENSE_WORDS = (
    "public domain",
    "cc0",
    "creative commons zero",
    "cc by",
    "cc-by",
    "cc by-sa",
    "cc-by-sa",
    "attribution",
)


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    value = re.sub(
        r"<[^>]+>",
        " ",
        str(value)
    )

    return " ".join(
        value.split()
    ).strip()


def safe_filename(value):

    value = clean_text(
        value
    )

    value = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        value
    )

    value = re.sub(
        r"\s+",
        "_",
        value
    )

    value = value.strip(
        "._"
    )

    if not value:

        value = "THRAANSH_NEWS"

    return value[:75]


def extension_from_url(
    url,
    default_extension
):

    try:

        extension = Path(
            urlparse(
                url
            ).path
        ).suffix.lower()

        if extension:

            return extension

    except Exception:

        pass

    return default_extension


# ============================================================
# QUEUE
# ============================================================

def load_queue():

    if not QUEUE_FILE.exists():

        raise RuntimeError(
            f"Queue file not found: {QUEUE_FILE}"
        )

    with open(
        QUEUE_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(
            file
        )

    if not isinstance(
        data,
        list
    ):

        raise RuntimeError(
            "article_queue.json must contain a list."
        )

    return data


def save_queue(queue):

    with open(
        QUEUE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            queue,
            file,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# ARTICLE SELECTION
# ============================================================

def get_next_article(queue):

    allowed_statuses = {
        "SCENE_PLAN_READY",
        "SCENE_FOOTAGE_FAILED",
        "MULTI_MEDIA_FAILED",
    }

    for article in queue:

        if not article.get(
            "production_selected"
        ):

            continue

        status = clean_text(
            article.get(
                "status"
            )
        ).upper()

        if status not in allowed_statuses:

            continue

        scenes = article.get(
            "scene_plan",
            []
        )

        if not isinstance(
            scenes,
            list
        ):

            continue

        if not scenes:

            continue

        return article

    return None


# ============================================================
# IMAGE VALIDATION
# ============================================================

def validate_image(path):

    try:

        with Image.open(
            path
        ) as image:

            image.verify()

        with Image.open(
            path
        ) as image:

            if (
                image.width < 200
                or image.height < 150
            ):

                raise RuntimeError(
                    f"Image too small: "
                    f"{image.width}x{image.height}"
                )

        return True

    except Exception as error:

        raise RuntimeError(
            f"Invalid image: {error}"
        )


# ============================================================
# VIDEO VALIDATION
# ============================================================

def inspect_media(path):

    process = __import__(
        "subprocess"
    ).run(
        [
            str(FFMPEG_EXE),
            "-hide_banner",
            "-i",
            str(path),
        ],
        stdout=__import__(
            "subprocess"
        ).PIPE,
        stderr=__import__(
            "subprocess"
        ).PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    return (
        process.stdout
        + "\n"
        + process.stderr
    )


def validate_video(path):

    information = inspect_media(
        path
    )

    if not re.search(
        r"Stream\s+#.*Video:",
        information,
        re.IGNORECASE
    ):

        raise RuntimeError(
            "No video stream detected."
        )

    return True


# ============================================================
# DOWNLOAD
# ============================================================

def download_file(
    url,
    destination
):

    last_error = None

    for attempt in range(
        1,
        DOWNLOAD_MAX_RETRIES + 1
    ):

        try:

            response = requests.get(
                url,
                headers=BASE_HEADERS,
                stream=True,
                timeout=DOWNLOAD_TIMEOUT
            )

            if response.status_code == 429:

                raise RuntimeError(
                    "HTTP 429 rate limit"
                )

            response.raise_for_status()

            content_type = (
                response.headers
                .get(
                    "Content-Type",
                    ""
                )
                .lower()
            )

            if (
                "text/html"
                in content_type
            ):

                raise RuntimeError(
                    "HTML returned instead of media."
                )

            if content_type.startswith(
                "audio/"
            ):

                raise RuntimeError(
                    "Audio-only file rejected."
                )

            with open(
                destination,
                "wb"
            ) as file:

                for chunk in response.iter_content(
                    chunk_size=1024 * 512
                ):

                    if chunk:

                        file.write(
                            chunk
                        )

            if (
                not destination.exists()
                or destination.stat().st_size < 3000
            ):

                raise RuntimeError(
                    "Downloaded file is empty "
                    "or too small."
                )

            return True

        except Exception as error:

            last_error = error

            if destination.exists():

                try:
                    destination.unlink()
                except Exception:
                    pass

            if attempt < DOWNLOAD_MAX_RETRIES:

                time.sleep(
                    1
                )

    raise RuntimeError(
        str(
            last_error
        )
    )


# ============================================================
# PEXELS
# ============================================================

PEXELS_AVAILABLE = None


def search_pexels_video(query):

    global PEXELS_AVAILABLE

    if not PEXELS_API_KEY:

        return []

    if PEXELS_AVAILABLE is False:

        return []

    try:

        response = requests.get(
            PEXELS_VIDEO_API,
            headers={
                "Authorization":
                    PEXELS_API_KEY,

                "User-Agent":
                    USER_AGENT,
            },
            params={
                "query":
                    query,

                "per_page":
                    5,

                "orientation":
                    "landscape",
            },
            timeout=API_TIMEOUT
        )

        if response.status_code in {
            401,
            403,
        }:

            PEXELS_AVAILABLE = False

            print(
                "Pexels API unavailable/"
                "invalid key. Skipping Pexels "
                "for this run."
            )

            return []

        response.raise_for_status()

        PEXELS_AVAILABLE = True

        data = response.json()

        results = []

        for video in data.get(
            "videos",
            []
        ):

            files = video.get(
                "video_files",
                []
            )

            files = [
                item
                for item in files
                if item.get(
                    "link"
                )
                and item.get(
                    "file_type"
                )
                == "video/mp4"
            ]

            if not files:

                continue

            # Prefer HD but avoid giant 4K files.

            files.sort(
                key=lambda item:
                    (
                        abs(
                            (
                                item.get(
                                    "width"
                                )
                                or 1280
                            )
                            - 1280
                        )
                    )
            )

            selected_file = files[0]

            results.append(
                {
                    "source":
                        "PEXELS",

                    "title":
                        f"Pexels video {video.get('id')}",

                    "url":
                        selected_file.get(
                            "link"
                        ),

                    "license":
                        "Pexels License",

                    "media_type":
                        "VIDEO",
                }
            )

        return results

    except Exception as error:

        print(
            "Pexels search skipped:",
            error
        )

        return []


# ============================================================
# PIXABAY
# ============================================================

PIXABAY_AVAILABLE = None


def search_pixabay_video(query):

    global PIXABAY_AVAILABLE

    if not PIXABAY_API_KEY:

        return []

    if PIXABAY_AVAILABLE is False:

        return []

    try:

        response = requests.get(
            PIXABAY_VIDEO_API,
            params={
                "key":
                    PIXABAY_API_KEY,

                "q":
                    query,

                "per_page":
                    5,

                "safesearch":
                    "true",
            },
            headers=BASE_HEADERS,
            timeout=API_TIMEOUT
        )

        if response.status_code in {
            400,
            401,
            403,
        }:

            PIXABAY_AVAILABLE = False

            print(
                "Pixabay API unavailable/"
                "invalid key. Skipping Pixabay "
                "for this run."
            )

            return []

        response.raise_for_status()

        PIXABAY_AVAILABLE = True

        data = response.json()

        results = []

        for hit in data.get(
            "hits",
            []
        ):

            videos = hit.get(
                "videos",
                {}
            )

            preferred = (
                videos.get(
                    "medium"
                )
                or videos.get(
                    "small"
                )
                or videos.get(
                    "large"
                )
            )

            if not preferred:

                continue

            url = preferred.get(
                "url"
            )

            if not url:

                continue

            results.append(
                {
                    "source":
                        "PIXABAY",

                    "title":
                        f"Pixabay video {hit.get('id')}",

                    "url":
                        url,

                    "license":
                        "Pixabay Content License",

                    "media_type":
                        "VIDEO",
                }
            )

        return results

    except Exception as error:

        print(
            "Pixabay search skipped:",
            error
        )

        return []


# ============================================================
# WIKIMEDIA REQUEST
# ============================================================

WIKIMEDIA_DISABLED = False


def wikimedia_request(params):

    global WIKIMEDIA_DISABLED

    if WIKIMEDIA_DISABLED:

        return None

    for attempt in range(
        1,
        WIKIMEDIA_MAX_RETRIES + 1
    ):

        try:

            response = requests.get(
                WIKIMEDIA_API,
                params=params,
                headers=BASE_HEADERS,
                timeout=API_TIMEOUT
            )

            if response.status_code == 429:

                print(
                    "Wikimedia rate limited."
                )

                if attempt >= WIKIMEDIA_MAX_RETRIES:

                    print(
                        "Wikimedia disabled for "
                        "remainder of this run."
                    )

                    WIKIMEDIA_DISABLED = True

                    return None

                time.sleep(
                    2
                )

                continue

            response.raise_for_status()

            time.sleep(
                BETWEEN_REQUESTS_DELAY
            )

            return response.json()

        except Exception as error:

            print(
                "Wikimedia request failed:",
                error
            )

            if attempt >= WIKIMEDIA_MAX_RETRIES:

                return None

    return None


# ============================================================
# WIKIMEDIA SEARCH
# ============================================================

def wikimedia_search_titles(query):

    data = wikimedia_request(
        {
            "action":
                "query",

            "format":
                "json",

            "list":
                "search",

            "srnamespace":
                6,

            "srlimit":
                SEARCH_RESULTS_LIMIT,

            "srsearch":
                query,
        }
    )

    if not data:

        return []

    results = (
        data
        .get(
            "query",
            {}
        )
        .get(
            "search",
            []
        )
    )

    return [
        item.get(
            "title"
        )
        for item in results
        if item.get(
            "title"
        )
    ]


# ============================================================
# WIKIMEDIA FILE INFO
# ============================================================

def wikimedia_file_info(title):

    data = wikimedia_request(
        {
            "action":
                "query",

            "format":
                "json",

            "prop":
                "imageinfo",

            "titles":
                title,

            "iiprop":
                "url|mime|mediatype|extmetadata",
        }
    )

    if not data:

        return None

    pages = (
        data
        .get(
            "query",
            {}
        )
        .get(
            "pages",
            {}
        )
    )

    if not pages:

        return None

    page = next(
        iter(
            pages.values()
        )
    )

    imageinfo = page.get(
        "imageinfo",
        []
    )

    if not imageinfo:

        return None

    info = imageinfo[0]

    metadata = info.get(
        "extmetadata",
        {}
    )

    def metadata_value(name):

        value = metadata.get(
            name,
            {}
        )

        if isinstance(
            value,
            dict
        ):

            return clean_text(
                value.get(
                    "value"
                )
            )

        return clean_text(
            value
        )

    return {
        "source":
            "WIKIMEDIA",

        "title":
            title,

        "url":
            info.get(
                "url",
                ""
            ),

        "mime":
            clean_text(
                info.get(
                    "mime"
                )
            ).lower(),

        "mediatype":
            clean_text(
                info.get(
                    "mediatype"
                )
            ).upper(),

        "license":
            metadata_value(
                "LicenseShortName"
            ),

        "license_url":
            metadata_value(
                "LicenseUrl"
            ),

        "artist":
            metadata_value(
                "Artist"
            ),

        "description":
            metadata_value(
                "ImageDescription"
            ),
    }


# ============================================================
# WIKIMEDIA LICENSE
# ============================================================

def valid_wikimedia_license(info):

    combined = (
        clean_text(
            info.get(
                "license"
            )
        )
        + " "
        + clean_text(
            info.get(
                "license_url"
            )
        )
    ).lower()

    return any(
        word in combined
        for word in ALLOWED_LICENSE_WORDS
    )


# ============================================================
# WIKIMEDIA VIDEO SEARCH
# ============================================================

def search_wikimedia_video(query):

    titles = wikimedia_search_titles(
        query
    )

    results = []

    for title in titles[:5]:

        if WIKIMEDIA_DISABLED:

            break

        info = wikimedia_file_info(
            title
        )

        if not info:

            continue

        if not valid_wikimedia_license(
            info
        ):

            continue

        mime = info.get(
            "mime",
            ""
        )

        if not mime.startswith(
            "video/"
        ):

            continue

        info[
            "media_type"
        ] = "VIDEO"

        results.append(
            info
        )

        if len(
            results
        ) >= 2:

            break

    return results


# ============================================================
# WIKIMEDIA IMAGE SEARCH
# ============================================================

def search_wikimedia_image(query):

    titles = wikimedia_search_titles(
        query
    )

    results = []

    for title in titles[:6]:

        if WIKIMEDIA_DISABLED:

            break

        info = wikimedia_file_info(
            title
        )

        if not info:

            continue

        if not valid_wikimedia_license(
            info
        ):

            continue

        mime = info.get(
            "mime",
            ""
        )

        extension = extension_from_url(
            info.get(
                "url",
                ""
            ),
            ""
        )

        if not mime.startswith(
            "image/"
        ):

            continue

        # Pillow cannot directly use SVG.
        if (
            extension == ".svg"
            or mime == "image/svg+xml"
        ):

            continue

        info[
            "media_type"
        ] = "IMAGE"

        results.append(
            info
        )

        if len(
            results
        ) >= 3:

            break

    return results


# ============================================================
# EXISTING MEDIA
# ============================================================

def validate_existing_scene(scene):

    path_value = clean_text(
        scene.get(
            "footage_file"
        )
    )

    media_type = clean_text(
        scene.get(
            "media_type"
        )
    ).upper()

    if not path_value:

        return False

    path = Path(
        path_value
    )

    if not path.exists():

        return False

    try:

        if media_type == "IMAGE":

            validate_image(
                path
            )

            return True

        if media_type == "VIDEO":

            validate_video(
                path
            )

            return True

    except Exception:

        try:
            path.unlink()
        except Exception:
            pass

        scene[
            "footage_file"
        ] = None

        scene[
            "media_type"
        ] = None

        scene[
            "status"
        ] = "PENDING"

    return False



# ============================================================
# VISUAL IDENTITY SAFETY
# ============================================================

GENERIC_PERSON_WORDS = {
    "man", "woman", "person", "people", "male", "female",
    "boy", "girl", "men", "women", "adult", "human",
}


def normalize_identity_text(value):
    value = clean_text(value).lower()
    value = re.sub(r"[^a-z0-9\u0900-\u097f\s-]", " ", value)
    return " ".join(value.split())


def person_tokens(person):
    return [
        token for token in normalize_identity_text(person).split()
        if len(token) >= 3 and token not in GENERIC_PERSON_WORDS
    ]


def wikimedia_candidate_matches_person(candidate, person):
    """Conservative metadata/name match. This is not face recognition."""
    tokens = person_tokens(person)
    if not tokens:
        return False

    haystack = normalize_identity_text(
        " ".join([
            clean_text(candidate.get("title")),
            clean_text(candidate.get("description")),
            clean_text(candidate.get("artist")),
        ])
    )
    return all(token in haystack for token in tokens)


def contextual_queries(article, scene):
    """
    Build context-only searches for scenes involving a named real person.
    Pexels/Pixabay results must never be treated as that named person.
    """
    result = []
    organisation = clean_text(scene.get("organisation"))
    location = clean_text(scene.get("location"))
    country = clean_text(scene.get("country") or article.get("story_country"))
    category = clean_text(
        article.get("story_category_detected")
        or article.get("category_slug")
        or article.get("category")
    )
    person = clean_text(scene.get("person"))
    p_tokens = person_tokens(person)

    if organisation:
        result.append(f"{organisation} {country}".strip() if country else organisation)

    if location:
        result.append(
            f"{location} {country}".strip()
            if country and country.lower() not in location.lower()
            else location
        )

    scene_queries = scene.get("search_queries", [])
    if not isinstance(scene_queries, list):
        scene_queries = []

    for raw_query in scene_queries:
        query = clean_text(raw_query)
        if not query:
            continue
        words = set(normalize_identity_text(query).split())
        if p_tokens and any(token in words for token in p_tokens):
            continue
        result.append(query)

    if country and category:
        result.append(f"{category} {country}".strip())
    if country:
        result.append(country)

    return list(dict.fromkeys(q for q in result if clean_text(q)))[:3]


# ============================================================
# SEARCH QUERIES
# ============================================================

def get_queries(article, scene):
    person = clean_text(scene.get("person"))

    if person:
        return contextual_queries(article, scene)

    result = []
    organisation = clean_text(scene.get("organisation"))
    location = clean_text(scene.get("location"))
    country = clean_text(scene.get("country") or article.get("story_country"))

    if organisation:
        result.append(f"{organisation} {country}".strip() if country else organisation)

    if location:
        result.append(
            f"{location} {country}".strip()
            if country and country.lower() not in location.lower()
            else location
        )

    scene_queries = scene.get("search_queries", [])
    if isinstance(scene_queries, list):
        for query in scene_queries:
            query = clean_text(query)
            if query:
                result.append(query)

    return list(dict.fromkeys(result))[:3]


# ============================================================
# SAVE DOWNLOADED CANDIDATE
# ============================================================

def try_candidate(
    article_title,
    scene_number,
    candidate,
    used_urls
):

    url = clean_text(
        candidate.get(
            "url"
        )
    )

    if not url:

        return None

    if url in used_urls:

        return None

    media_type = clean_text(
        candidate.get(
            "media_type"
        )
    ).upper()

    if media_type == "VIDEO":

        extension = extension_from_url(
            url,
            ".mp4"
        )

        if extension not in VIDEO_EXTENSIONS:

            extension = ".mp4"

        suffix = "_video"

    elif media_type == "IMAGE":

        extension = extension_from_url(
            url,
            ".jpg"
        )

        if extension not in IMAGE_EXTENSIONS:

            extension = ".jpg"

        suffix = "_image"

    else:

        return None

    destination = (
        OUTPUT_FOLDER
        / (
            safe_filename(
                article_title
            )
            + f"_scene_{scene_number:02d}"
            + suffix
            + extension
        )
    )

    try:

        print(
            "Downloading:",
            candidate.get(
                "title"
            )
        )

        download_file(
            url,
            destination
        )

        if media_type == "IMAGE":

            validate_image(
                destination
            )

        else:

            validate_video(
                destination
            )

        print(
            f"{media_type} validated âœ“"
        )

        used_urls.add(
            url
        )

        return {
            "file":
                destination,

            "candidate":
                candidate,
        }

    except Exception as error:

        print(
            "Rejected media:",
            error
        )

        if destination.exists():

            try:
                destination.unlink()
            except Exception:
                pass

        return None


# ============================================================
# FIND MEDIA FOR ONE QUERY
# ============================================================

def mark_contextual(candidate):
    candidate = dict(candidate)
    candidate["visual_identity_safe"] = True
    candidate["visual_usage_mode"] = "CONTEXTUAL_MEDIA"
    candidate["identity_subject"] = ""
    candidate["identity_verification_method"] = "NOT_IDENTITY_MEDIA"
    return candidate


def find_exact_person_wikimedia(
    article_title,
    scene_number,
    person,
    country,
    used_urls
):
    """
    Exact-person media is accepted only from Wikimedia when its title/metadata
    conservatively matches the named person. No face recognition is used.
    """
    person = clean_text(person)

    if not person or WIKIMEDIA_DISABLED:
        return None

    query = f"{person} {country}".strip() if country else person

    print()
    print("Exact-person Wikimedia check:", query)

    candidates = (
        search_wikimedia_video(query)[:2]
        + search_wikimedia_image(query)[:3]
    )

    for candidate in candidates:

        if not wikimedia_candidate_matches_person(candidate, person):
            print(
                "Rejected identity-unverified Wikimedia result:",
                candidate.get("title")
            )
            continue

        candidate = dict(candidate)
        candidate["visual_identity_safe"] = True
        candidate["visual_usage_mode"] = "EXACT_PERSON_VERIFIED_METADATA"
        candidate["identity_subject"] = person
        candidate["identity_verification_method"] = (
            "WIKIMEDIA_NAME_METADATA_MATCH"
        )

        result = try_candidate(
            article_title,
            scene_number,
            candidate,
            used_urls
        )

        if result:
            return result

    return None


def find_for_query(
    article_title,
    scene_number,
    query,
    used_urls
):
    """
    THRAANSH REAL-MEDIA-FIRST SEARCH.

    Priority:
    1. Wikimedia relevant licensed video
    2. Pexels relevant contextual video
    3. Pixabay relevant contextual video
    4. Wikimedia relevant licensed image

    Exact-person media remains handled separately by
    find_exact_person_wikimedia().
    """

    query = clean_text(query)

    if not query:
        return None

    print()
    print("Search:", query)
    print("Media priority: REAL/RELEVANT LICENSED MEDIA FIRST")

    # --------------------------------------------------------
    # 1. WIKIMEDIA VIDEO
    # --------------------------------------------------------

    if not WIKIMEDIA_DISABLED:

        print("Trying Wikimedia relevant video...")

        try:
            candidates = search_wikimedia_video(query)[:3]
        except Exception as error:
            print("Wikimedia video search failed:", error)
            candidates = []

        for candidate in candidates:

            try:
                result = try_candidate(
                    article_title,
                    scene_number,
                    mark_contextual(candidate),
                    used_urls
                )

                if result:
                    print("Selected Wikimedia relevant video.")
                    return result

            except Exception as error:
                print(
                    "Wikimedia video candidate rejected:",
                    error
                )

    # --------------------------------------------------------
    # 2. PEXELS VIDEO
    # --------------------------------------------------------

    print("Trying Pexels contextual video...")

    try:
        candidates = search_pexels_video(query)[:3]
    except Exception as error:
        print("Pexels search failed:", error)
        candidates = []

    for candidate in candidates:

        try:
            result = try_candidate(
                article_title,
                scene_number,
                mark_contextual(candidate),
                used_urls
            )

            if result:
                print("Selected Pexels contextual video.")
                return result

        except Exception as error:
            print(
                "Pexels candidate rejected:",
                error
            )

    # --------------------------------------------------------
    # 3. PIXABAY VIDEO
    # --------------------------------------------------------

    print("Trying Pixabay contextual video...")

    try:
        candidates = search_pixabay_video(query)[:3]
    except Exception as error:
        print("Pixabay search failed:", error)
        candidates = []

    for candidate in candidates:

        try:
            result = try_candidate(
                article_title,
                scene_number,
                mark_contextual(candidate),
                used_urls
            )

            if result:
                print("Selected Pixabay contextual video.")
                return result

        except Exception as error:
            print(
                "Pixabay candidate rejected:",
                error
            )

    # --------------------------------------------------------
    # 4. WIKIMEDIA IMAGE
    # --------------------------------------------------------

    if not WIKIMEDIA_DISABLED:

        print("Trying Wikimedia relevant image...")

        try:
            candidates = search_wikimedia_image(query)[:3]
        except Exception as error:
            print("Wikimedia image search failed:", error)
            candidates = []

        for candidate in candidates:

            try:
                result = try_candidate(
                    article_title,
                    scene_number,
                    mark_contextual(candidate),
                    used_urls
                )

                if result:
                    print("Selected Wikimedia relevant image.")
                    return result

            except Exception as error:
                print(
                    "Wikimedia image candidate rejected:",
                    error
                )

    print(
        "No acceptable media found for query:",
        query
    )

    return None

# ============================================================

def main():

    global WIKIMEDIA_DISABLED

    print()
    print("=" * 78)

    print(
        "THRAANSH FAST MULTI-SOURCE "
        "STORY MEDIA GENERATOR"
    )

    print("=" * 78)

    print()
    print(
        "Pexels video first âœ“"
    )

    print(
        "Pixabay video second âœ“"
    )

    print(
        "Wikimedia limited fallback âœ“"
    )

    print(
        "Corrupt image blocking âœ“"
    )

    print(
        "Broken video blocking âœ“"
    )

    print(
        "HTML blocking âœ“"
    )

    print(
        "Audio blocking âœ“"
    )

    print(
        "Duplicate blocking âœ“"
    )

    print(
        "Named-person stock impersonation blocking âœ“"
    )

    print(
        "Exact-person Wikimedia metadata verification âœ“"
    )

    print(
        "Maximum Wikimedia retries: "
        f"{WIKIMEDIA_MAX_RETRIES}"
    )

    # ========================================================
    # API STATUS
    # ========================================================

    print()
    print(
        "Pexels key:",
        "AVAILABLE"
        if PEXELS_API_KEY
        else "NOT SET"
    )

    print(
        "Pixabay key:",
        "AVAILABLE"
        if PIXABAY_API_KEY
        else "NOT SET"
    )

    # ========================================================
    # LOAD QUEUE
    # ========================================================

    try:

        queue = load_queue()

    except Exception as error:

        print()
        print(
            "QUEUE ERROR:",
            error
        )

        return

    article = get_next_article(
        queue
    )

    if article is None:

        print()
        print(
            "No selected SCENE_PLAN_READY "
            "article is waiting for media."
        )

        return

    title = clean_text(
        article.get(
            "title"
        )
    )

    previous_status = clean_text(
        article.get(
            "status"
        )
    ).upper()

    scenes = article.get(
        "scene_plan",
        []
    )

    print()
    print(
        "ARTICLE:"
    )

    print(
        title
    )

    print()
    print(
        "Country:",
        clean_text(
            article.get(
                "story_country"
            )
        )
        or "Unknown"
    )

    # ========================================================
    # USED MEDIA
    # ========================================================

    used_urls = set()

    ready_video = 0

    ready_image = 0

    failed = 0

    # ========================================================
    # PROCESS SCENES
    # ========================================================

    for index, scene in enumerate(
        scenes,
        start=1
    ):

        print()
        print("=" * 62)

        print(
            f"SCENE {index}"
        )

        print("=" * 62)

        # ====================================================
        # EXISTING VALID MEDIA
        # ====================================================

        if validate_existing_scene(
            scene
        ):

            existing_type = clean_text(
                scene.get(
                    "media_type"
                )
            ).upper()

            existing_url = clean_text(
                scene.get(
                    "media_url"
                )
            )

            if existing_url:

                used_urls.add(
                    existing_url
                )

            print(
                "Existing validated media âœ“"
            )

            if existing_type == "VIDEO":

                ready_video += 1

            elif existing_type == "IMAGE":

                ready_image += 1

            continue

        queries = get_queries(
            article,
            scene
        )

        if not queries:

            print(
                "No usable scene queries."
            )

            scene[
                "status"
            ] = "FAILED"

            scene[
                "last_error"
            ] = (
                "No usable scene queries."
            )

            failed += 1

            continue

        result = None
        query_used = None

        person = clean_text(scene.get("person"))
        country = clean_text(scene.get("country") or article.get("story_country"))

        # Named person: try identity-verifiable Wikimedia media first.
        if person:
            result = find_exact_person_wikimedia(
                title,
                index,
                person,
                country,
                used_urls
            )

            if result:
                query_used = f"{person} {country}".strip()

        # If exact-person media is unavailable, use contextual visuals.
        if not result:
            for query in queries:
                result = find_for_query(
                    title,
                    index,
                    query,
                    used_urls
                )

                if result:
                    query_used = query
                    break

            # If Wikimedia rate limiting triggered,
            # Wikimedia remains disabled and next sources
            # continue without it.

        if not result:

            print()
            print(
                f"Scene {index} FAILED."
            )

            print(
                "Moving to next scene."
            )

            scene[
                "status"
            ] = "FAILED"

            scene[
                "last_error"
            ] = (
                "No validated licensed "
                "media found."
            )

            failed += 1

            continue

        candidate = result[
            "candidate"
        ]

        media_file = result[
            "file"
        ]

        media_type = candidate[
            "media_type"
        ]

        # ====================================================
        # SAVE SCENE
        # ====================================================

        scene[
            "status"
        ] = (
            f"{media_type}_READY"
        )

        scene[
            "media_type"
        ] = media_type

        scene[
            "footage_file"
        ] = str(
            media_file
        )

        scene[
            "media_source"
        ] = candidate.get(
            "source"
        )

        scene[
            "media_title"
        ] = candidate.get(
            "title"
        )

        scene[
            "media_url"
        ] = candidate.get(
            "url"
        )

        scene[
            "license"
        ] = candidate.get(
            "license"
        )

        scene[
            "license_url"
        ] = candidate.get(
            "license_url"
        )

        scene[
            "artist"
        ] = candidate.get(
            "artist"
        )

        scene[
            "search_query_used"
        ] = query_used

        scene["visual_identity_safe"] = bool(
            candidate.get("visual_identity_safe", False)
        )
        scene["visual_usage_mode"] = clean_text(
            candidate.get("visual_usage_mode")
        )
        scene["identity_subject"] = clean_text(
            candidate.get("identity_subject")
        )
        scene["identity_verification_method"] = clean_text(
            candidate.get("identity_verification_method")
        )

        scene[
            "download_validated"
        ] = True

        scene[
            "validated_at"
        ] = datetime.now().isoformat()

        scene[
            "last_error"
        ] = None

        if media_type == "VIDEO":

            ready_video += 1

        else:

            ready_image += 1

        print()
        print(
            f"Scene {index}: "
            f"{media_type}_READY âœ“"
        )

        print(
            "Source:",
            candidate.get(
                "source"
            )
        )

    # ========================================================
    # RESULTS
    # ========================================================

    total_ready = (
        ready_video
        + ready_image
    )

    article[
        "scene_footage_files"
    ] = [
        scene.get(
            "footage_file"
        )
        for scene in scenes
        if scene.get(
            "footage_file"
        )
    ]

    article[
        "scene_video_count"
    ] = ready_video

    article[
        "scene_image_count"
    ] = ready_image

    article[
        "scene_media_ready"
    ] = total_ready

    article[
        "scene_media_failed"
    ] = failed

    article[
        "media_generator_version"
    ] = (
        "FAST_MULTI_SOURCE_IDENTITY_SAFE_V4"
    )

    article[
        "wikimedia_disabled_due_rate_limit"
    ] = WIKIMEDIA_DISABLED

    article[
        "media_generated_at"
    ] = datetime.now().isoformat()

    article[
        "updated_at"
    ] = datetime.now().isoformat()

    print()
    print("=" * 78)

    print(
        "FAST MULTI-SOURCE MEDIA RESULTS"
    )

    print("=" * 78)

    print()
    print(
        "Video scenes:",
        ready_video
    )

    print(
        "Image scenes:",
        ready_image
    )

    print(
        "Total ready:",
        total_ready
    )

    print(
        "Failed:",
        failed
    )

    print(
        "Wikimedia disabled:",
        WIKIMEDIA_DISABLED
    )

    # ========================================================
    # SUCCESS
    # ========================================================

    if total_ready >= 3:

        article[
            "status"
        ] = "MULTI_MEDIA_READY"

        article[
            "last_error"
        ] = None

        save_queue(
            queue
        )

        print()
        print("=" * 78)

        print(
            "MULTI-SOURCE STORY MEDIA READY"
        )

        print("=" * 78)

        print()
        print(
            f"{previous_status} "
            "-> MULTI_MEDIA_READY"
        )

        print()
        print(
            "Next:"
        )

        print(
            "Run video/multi_generator.py"
        )

    else:

        article[
            "status"
        ] = "SCENE_FOOTAGE_FAILED"

        article[
            "last_error"
        ] = (
            f"Only {total_ready} validated "
            f"scenes were available."
        )

        article[
            "footage_retry_count"
        ] = (
            article.get(
                "footage_retry_count",
                0
            )
            + 1
        )

        save_queue(
            queue
        )

        print()
        print("=" * 78)

        print(
            "NOT ENOUGH MEDIA"
        )

        print("=" * 78)

        print()
        print(
            "Pipeline stopped quickly instead "
            "of waiting for hours."
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
