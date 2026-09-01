import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests


# ============================================================
# THRAANSH WIKIMEDIA COMMONS FOOTAGE GENERATOR
# NO API KEY REQUIRED
# INDIA-FIRST / STORY-ACCURATE
# ============================================================

PROJECT_FOLDER = Path(__file__).resolve().parents[1]

DATA_FOLDER = PROJECT_FOLDER / "data"
FOOTAGE_FOLDER = PROJECT_FOLDER / "scene_footage"

QUEUE_FILE = DATA_FOLDER / "article_queue.json"

FOOTAGE_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# WIKIMEDIA CONFIG
# ============================================================

COMMONS_API = (
    "https://commons.wikimedia.org/w/api.php"
)

REQUEST_TIMEOUT = 60

SEARCH_HEADERS = {
    "User-Agent": (
        "THRAANSH-Automation/1.0 "
        "(contact: thraansh.media@gmail.com)"
    ),
    "Accept": "application/json",
}

DOWNLOAD_HEADERS = {
    "User-Agent": (
        "THRAANSH-Automation/1.0 "
        "(contact: thraansh.media@gmail.com)"
    ),
    "Referer": "https://commons.wikimedia.org/",
    "Accept": "*/*",
}


# ============================================================
# ALLOWED LICENSES
# ============================================================

ALLOWED_LICENSE_WORDS = [
    "cc0",
    "public domain",
    "cc by",
    "cc-by",
    "cc by-sa",
    "cc-by-sa",
    "creative commons attribution",
    "creative commons attribution-share alike",
]


# ============================================================
# LOAD QUEUE
# ============================================================

def load_queue():

    if not QUEUE_FILE.exists():

        print()
        print(
            "ERROR: article_queue.json not found."
        )

        return []

    try:

        with open(
            QUEUE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, list):

            return data

        return []

    except Exception as error:

        print()
        print(
            "ERROR reading queue:"
        )

        print(error)

        return []


# ============================================================
# SAVE QUEUE
# ============================================================

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
# CLEAN TEXT
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


# ============================================================
# SELECT NEXT ARTICLE
# ============================================================

def get_next_article(queue):

    accepted_statuses = {
        "VOICE_READY",
        "FOOTAGE_FAILED",
        "MEDIA_FAILED",
    }

    for article in queue:

        status = clean_text(
            article.get("status")
        ).upper()

        if status not in accepted_statuses:
            continue

        voice_status = clean_text(
            article.get("voice_status")
        ).upper()

        if voice_status != "READY":
            continue

        audio_file = (
            article.get("voice_file")
            or article.get("audio_file")
        )

        if not audio_file:
            continue

        audio_path = Path(
            audio_file
        )

        if not audio_path.exists():
            continue

        return article

    return None


# ============================================================
# SAFE FILE NAME
# ============================================================

def safe_filename(text):

    text = clean_text(text)

    allowed = []

    for character in text:

        if (
            character.isalnum()
            or character in (
                " ",
                "-",
                "_"
            )
        ):

            allowed.append(
                character
            )

    filename = "".join(
        allowed
    ).strip()

    filename = filename.replace(
        " ",
        "_"
    )

    if not filename:
        filename = "thraansh_media"

    return filename[:60]


# ============================================================
# DETECT INDIA STORY
# ============================================================

def is_india_story(article):

    combined = " ".join(
        [
            clean_text(
                article.get("title")
            ),
            clean_text(
                article.get("teaser")
            ),
            clean_text(
                article.get("description")
            ),
            clean_text(
                article.get("content")
            ),
        ]
    ).lower()

    india_terms = [
        "india",
        "indian",
        "delhi",
        "new delhi",
        "mumbai",
        "bengaluru",
        "bangalore",
        "chennai",
        "hyderabad",
        "kolkata",
        "kerala",
        "karnataka",
        "maharashtra",
        "gujarat",
        "punjab",
        "haryana",
        "uttar pradesh",
        "madhya pradesh",
        "rajasthan",
        "odisha",
        "bihar",
        "assam",
        "goa",
        "parliament",
        "lok sabha",
        "rajya sabha",
        "supreme court of india",
        "ministry of external affairs",
        "mea",
        "rbi",
        "sensex",
        "nifty",
        "rupee",
        "isro",
        "bcci",
        "ipl",
        "team india",
        "shubman",
    ]

    return any(
        term in combined
        for term in india_terms
    )


# ============================================================
# BUILD STORY-ACCURATE SEARCH QUERIES
# ============================================================

def build_search_queries(article):

    title = clean_text(
        article.get("title")
    )

    title_lower = title.lower()

    india_story = is_india_story(
        article
    )

    queries = []

    if india_story and any(
        term in title_lower
        for term in [
            "government",
            "minister",
            "parliament",
            "foreign",
            "mea",
            "uncerd",
            "un committee",
            "united nations",
        ]
    ):

        queries.extend(
            [
                "India Ministry External Affairs New Delhi",
                "Ministry of External Affairs India",
                "New Delhi India government",
                "Indian government New Delhi",
                "India United Nations diplomacy",
                "United Nations India delegation",
                "United Nations meeting",
            ]
        )

    elif india_story and any(
        term in title_lower
        for term in [
            "cricket",
            "shubman",
            "bcci",
            "ipl",
            "team india",
            "match",
        ]
    ):

        queries.extend(
            [
                "India cricket",
                "Indian cricket stadium",
                "India national cricket team",
                "cricket stadium India",
            ]
        )

    elif india_story and any(
        term in title_lower
        for term in [
            "market",
            "stock",
            "business",
            "bank",
            "rbi",
            "sensex",
            "nifty",
            "rupee",
        ]
    ):

        queries.extend(
            [
                "Mumbai India business",
                "Indian financial market",
                "Mumbai financial district",
                "India business office",
            ]
        )

    elif india_story and any(
        term in title_lower
        for term in [
            "technology",
            "ai",
            "startup",
            "software",
            "digital",
        ]
    ):

        queries.extend(
            [
                "Bengaluru India technology",
                "India technology office",
                "Indian startup",
                "Bangalore technology",
            ]
        )

    elif india_story and any(
        term in title_lower
        for term in [
            "hospital",
            "cancer",
            "doctor",
            "medicine",
            "health",
        ]
    ):

        queries.extend(
            [
                "India hospital",
                "Indian doctors",
                "India healthcare",
            ]
        )

    elif india_story:

        queries.extend(
            [
                title,
                "India news",
                "New Delhi India",
                "India city people",
            ]
        )

    else:

        queries.extend(
            [
                title,
                "international news",
                "world news",
            ]
        )

    return queries


# ============================================================
# METADATA HELPER
# ============================================================

def metadata_value(
    metadata,
    field
):

    value = metadata.get(
        field,
        {}
    )

    if isinstance(
        value,
        dict
    ):

        return clean_text(
            value.get("value")
        )

    return clean_text(
        value
    )


# ============================================================
# LICENSE CHECK
# ============================================================

def license_allowed(
    license_name,
    usage_terms
):

    combined = (
        f"{license_name} {usage_terms}"
    ).lower()

    return any(
        allowed in combined
        for allowed in ALLOWED_LICENSE_WORDS
    )


# ============================================================
# VIDEO FILE CHECK
# ============================================================

def is_video_file(
    mime,
    url
):

    mime = clean_text(
        mime
    ).lower()

    url = clean_text(
        url
    ).lower()

    if mime.startswith(
        "video/"
    ):
        return True

    extensions = [
        ".webm",
        ".ogv",
        ".ogg",
        ".mp4",
    ]

    return any(
        extension in url
        for extension in extensions
    )


# ============================================================
# STORY RELEVANCE SCORE
# ============================================================

def relevance_score(
    article,
    media,
    search_query
):

    title = clean_text(
        article.get("title")
    ).lower()

    media_title = clean_text(
        media.get("title")
    ).lower()

    description = clean_text(
        media.get("description")
    ).lower()

    query_lower = clean_text(
        search_query
    ).lower()

    score = 0

    important_terms = [
        "india",
        "indian",
        "new delhi",
        "delhi",
        "ministry",
        "external affairs",
        "united nations",
        "diplomacy",
        "government",
        "parliament",
    ]

    for term in important_terms:

        if term in title:

            if term in media_title:
                score += 5

            if term in description:
                score += 3

        if term in query_lower:

            if term in media_title:
                score += 4

            if term in description:
                score += 2

    bad_terms = [
        "trump",
        "white house",
        "biden",
    ]

    for term in bad_terms:

        if (
            term not in title
            and term in media_title
        ):

            score -= 10

    return score


# ============================================================
# SEARCH COMMONS
# ============================================================

def search_commons(
    article,
    query,
    limit=50
):

    params = {
        "action":
            "query",

        "format":
            "json",

        "generator":
            "search",

        "gsrnamespace":
            6,

        "gsrsearch":
            query,

        "gsrlimit":
            limit,

        "prop":
            "imageinfo",

        "iiprop":
            "url|mime|extmetadata",

        "origin":
            "*",
    }

    response = requests.get(
        COMMONS_API,
        params=params,
        headers=SEARCH_HEADERS,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    payload = response.json()

    pages = (
        payload
        .get("query", {})
        .get("pages", {})
    )

    results = []

    for page in pages.values():

        imageinfo = page.get(
            "imageinfo",
            []
        )

        if not imageinfo:
            continue

        info = imageinfo[0]

        url = clean_text(
            info.get("url")
        )

        mime = clean_text(
            info.get("mime")
        )

        if not url:
            continue

        if not is_video_file(
            mime,
            url
        ):
            continue

        metadata = info.get(
            "extmetadata",
            {}
        )

        license_name = metadata_value(
            metadata,
            "LicenseShortName"
        )

        usage_terms = metadata_value(
            metadata,
            "UsageTerms"
        )

        if not license_allowed(
            license_name,
            usage_terms
        ):
            continue

        media = {
            "title":
                clean_text(
                    page.get("title")
                ),

            "url":
                url,

            "mime":
                mime,

            "license":
                license_name,

            "usage_terms":
                usage_terms,

            "artist":
                metadata_value(
                    metadata,
                    "Artist"
                ),

            "credit":
                metadata_value(
                    metadata,
                    "Credit"
                ),

            "attribution":
                metadata_value(
                    metadata,
                    "Attribution"
                ),

            "description":
                metadata_value(
                    metadata,
                    "ImageDescription"
                ),

            "commons_page":
                (
                    "https://commons.wikimedia.org/wiki/"
                    + str(
                        page.get(
                            "title",
                            ""
                        )
                    ).replace(
                        " ",
                        "_"
                    )
                ),
        }

        media[
            "relevance_score"
        ] = relevance_score(
            article,
            media,
            query
        )

        results.append(
            media
        )

    results.sort(
        key=lambda item:
            item.get(
                "relevance_score",
                0
            ),
        reverse=True
    )

    return results


# ============================================================
# GET FILE EXTENSION
# ============================================================

def extension_from_url(
    url
):

    path = urlparse(
        url
    ).path.lower()

    for extension in [
        ".webm",
        ".ogv",
        ".ogg",
        ".mp4",
    ]:

        if extension in path:
            return extension

    return ".webm"


# ============================================================
# DOWNLOAD MEDIA WITH RETRY/BACKOFF
# ============================================================

def download_media(
    url,
    output_file
):

    print()
    print(
        "Downloading Wikimedia footage..."
    )

    max_attempts = 5

    for attempt in range(
        1,
        max_attempts + 1
    ):

        try:

            with requests.get(
                url,
                headers=DOWNLOAD_HEADERS,
                stream=True,
                timeout=180
            ) as response:

                if response.status_code == 429:

                    retry_after = response.headers.get(
                        "Retry-After"
                    )

                    try:

                        wait_seconds = int(
                            retry_after
                        )

                    except Exception:

                        wait_seconds = (
                            10 * attempt
                        )

                    wait_seconds = min(
                        wait_seconds,
                        60
                    )

                    print()
                    print(
                        f"Wikimedia rate limit hit "
                        f"(attempt {attempt}/{max_attempts})."
                    )

                    print(
                        f"Waiting {wait_seconds} seconds..."
                    )

                    time.sleep(
                        wait_seconds
                    )

                    continue

                response.raise_for_status()

                with open(
                    output_file,
                    "wb"
                ) as file:

                    for chunk in (
                        response.iter_content(
                            chunk_size=1024 * 1024
                        )
                    ):

                        if chunk:

                            file.write(
                                chunk
                            )

                if (
                    output_file.exists()
                    and output_file.stat().st_size > 10_000
                ):

                    return

                raise RuntimeError(
                    "Downloaded media file is too small."
                )

        except requests.RequestException as error:

            if attempt >= max_attempts:

                raise

            wait_seconds = min(
                5 * attempt,
                30
            )

            print()
            print(
                f"Download error: {error}"
            )

            print(
                f"Retrying in "
                f"{wait_seconds} seconds..."
            )

            time.sleep(
                wait_seconds
            )

    raise RuntimeError(
        "Wikimedia download failed "
        "after multiple retries."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)

    print(
        "THRAANSH WIKIMEDIA FOOTAGE GENERATOR"
    )

    print("=" * 70)

    print()
    print(
        "No API key required. ✓"
    )

    queue = load_queue()

    if not queue:

        print()
        print(
            "Article queue is empty."
        )

        return

    article = get_next_article(
        queue
    )

    if article is None:

        print()
        print(
            "No VOICE_READY / FOOTAGE_FAILED / "
            "MEDIA_FAILED article is available."
        )

        return

    title = clean_text(
        article.get(
            "title",
            "THRAANSH News"
        )
    )

    previous_status = clean_text(
        article.get(
            "status"
        )
    ).upper()

    india_story = is_india_story(
        article
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
        "Footage policy:"
    )

    if india_story:

        print(
            "INDIA-FIRST ✓"
        )

    else:

        print(
            "STORY-LOCATION / INTERNATIONAL"
        )

    queries = build_search_queries(
        article
    )

    print()
    print(
        "Search queries:"
    )

    for query in queries:

        print(
            f" - {query}"
        )

    try:

        candidates = []

        for query in queries:

            print()
            print(
                f"Searching Wikimedia: "
                f"{query}"
            )

            results = search_commons(
                article,
                query
            )

            print(
                f"Licensed video results: "
                f"{len(results)}"
            )

            for result in results[:5]:

                result[
                    "search_query"
                ] = query

                candidates.append(
                    result
                )

            time.sleep(
                1
            )

        if not candidates:

            raise RuntimeError(
                "No suitable licensed Wikimedia "
                "video was found."
            )

        candidates.sort(
            key=lambda item:
                item.get(
                    "relevance_score",
                    0
                ),
            reverse=True
        )

        selected = candidates[0]

        print()
        print(
            "Selected media:"
        )

        print(
            selected[
                "title"
            ]
        )

        print()
        print(
            "Relevance score:"
        )

        print(
            selected[
                "relevance_score"
            ]
        )

        print()
        print(
            "Search query:"
        )

        print(
            selected[
                "search_query"
            ]
        )

        print()
        print(
            "License:"
        )

        print(
            selected[
                "license"
            ]
        )

        print()
        print(
            "Artist:"
        )

        print(
            selected[
                "artist"
            ]
        )

        extension = extension_from_url(
            selected[
                "url"
            ]
        )

        filename = safe_filename(
            title
        )

        output_file = (
            FOOTAGE_FOLDER
            / (
                f"{filename}"
                f"_wikimedia_01"
                f"{extension}"
            )
        )

        download_media(
            selected[
                "url"
            ],
            output_file
        )

        if not output_file.exists():

            raise RuntimeError(
                "Downloaded media file was not created."
            )

        if (
            output_file.stat().st_size
            < 10_000
        ):

            raise RuntimeError(
                "Downloaded Wikimedia media is too small."
            )

        # ====================================================
        # SAVE SUCCESS
        # ====================================================

        article[
            "footage_file"
        ] = str(
            output_file
        )

        article[
            "footage_files"
        ] = [
            str(
                output_file
            )
        ]

        article[
            "footage_status"
        ] = "READY"

        article[
            "footage_provider"
        ] = "Wikimedia Commons"

        article[
            "footage_search_query"
        ] = selected[
            "search_query"
        ]

        article[
            "footage_policy"
        ] = (
            "INDIA_FIRST"
            if india_story
            else "STORY_LOCATION"
        )

        article[
            "media_license"
        ] = selected[
            "license"
        ]

        article[
            "media_usage_terms"
        ] = selected[
            "usage_terms"
        ]

        article[
            "media_creator"
        ] = selected[
            "artist"
        ]

        article[
            "media_credit"
        ] = selected[
            "credit"
        ]

        article[
            "media_attribution"
        ] = selected[
            "attribution"
        ]

        article[
            "media_source_url"
        ] = selected[
            "commons_page"
        ]

        article[
            "media_original_url"
        ] = selected[
            "url"
        ]

        article[
            "footage_relevance_score"
        ] = selected[
            "relevance_score"
        ]

        article[
            "footage_generated_at"
        ] = datetime.now().isoformat()

        article[
            "status"
        ] = "MEDIA_READY"

        article[
            "last_error"
        ] = None

        article[
            "updated_at"
        ] = datetime.now().isoformat()

        save_queue(
            queue
        )

        print()
        print("=" * 70)

        print(
            "WIKIMEDIA FOOTAGE READY"
        )

        print("=" * 70)

        print()
        print(
            "File:"
        )

        print(
            output_file
        )

        print()
        print(
            f"Size: "
            f"{output_file.stat().st_size / 1024 / 1024:.2f} MB"
        )

        print()
        print(
            "Source:"
        )

        print(
            selected[
                "commons_page"
            ]
        )

        print()
        print(
            "License:"
        )

        print(
            selected[
                "license"
            ]
        )

        print()
        print(
            "Status:"
        )

        print(
            f"{previous_status} -> MEDIA_READY"
        )

        print()
        print(
            "Next stage:"
        )

        print(
            "Hindi voice + English visuals + "
            "background music video render"
        )

    except Exception as error:

        article[
            "footage_status"
        ] = "FAILED"

        article[
            "status"
        ] = "FOOTAGE_FAILED"

        article[
            "retry_count"
        ] = (
            article.get(
                "retry_count",
                0
            )
            + 1
        )

        article[
            "last_error"
        ] = str(
            error
        )

        article[
            "updated_at"
        ] = datetime.now().isoformat()

        save_queue(
            queue
        )

        print()
        print("=" * 70)

        print(
            "WIKIMEDIA FOOTAGE FAILED"
        )

        print("=" * 70)

        print()
        print(
            "Error:"
        )

        print(
            error
        )

        print()
        print(
            "Retry count:",
            article[
                "retry_count"
            ]
        )


if __name__ == "__main__":

    main()