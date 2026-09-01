import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# THRAANSH PUBLIC WEBSITE COLLECTOR
# Reads discovery news directly from thraansh.com/news
# ============================================================

PROJECT_FOLDER = Path(__file__).resolve().parents[1]

DATA_FOLDER = PROJECT_FOLDER / "data"
QUEUE_FILE = DATA_FOLDER / "article_queue.json"

DATA_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)

NEWS_PAGE_URL = "https://thraansh.com/news"

REQUEST_TIMEOUT = 30


# ============================================================
# LOAD EXISTING QUEUE
# ============================================================

def load_queue():

    if not QUEUE_FILE.exists():
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

    except Exception as error:
        print(
            f"WARNING: Could not load queue: {error}"
        )

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
            ensure_ascii=False,
            indent=2
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
# EXISTING ARTICLE KEYS
# ============================================================

def build_existing_keys(queue):

    keys = set()

    for article in queue:

        url = clean_text(
            article.get("url")
        )

        title = clean_text(
            article.get("title")
        ).lower()

        if url:
            keys.add(
                f"url:{url}"
            )

        if title:
            keys.add(
                f"title:{title}"
            )

    return keys


# ============================================================
# DOWNLOAD NEWS PAGE
# ============================================================

def fetch_news_page():

    print()
    print(
        f"Reading THRAANSH news page:"
    )

    print(
        NEWS_PAGE_URL
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/130 Safari/537.36"
        )
    }

    response = requests.get(
        NEWS_PAGE_URL,
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    return response.text


# ============================================================
# EXTRACT DISCOVERY RECORDS
# ============================================================

def extract_articles(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    articles = []

    # Look through links on the page.
    # We keep only links that appear to represent news records.
    for link in soup.find_all(
        "a",
        href=True
    ):

        href = clean_text(
            link.get("href")
        )

        text = clean_text(
            link.get_text(
                " ",
                strip=True
            )
        )

        if not href:
            continue

        if not text:
            continue

        # Ignore navigation / social / utility links
        ignored = [
            "/news",
            "/business",
            "/technology",
            "/sports",
            "/entertainment",
            "/culture",
            "/fashion",
            "/lifestyle",
            "/innovation",
            "/",
            "#",
        ]

        if href in ignored:
            continue

        if any(
            social in href.lower()
            for social in [
                "instagram.com",
                "facebook.com",
                "youtube.com",
                "linkedin.com",
                "x.com",
                "twitter.com",
            ]
        ):
            continue

        # External news links or article links are useful
        full_url = urljoin(
            NEWS_PAGE_URL,
            href
        )

        parent = link.parent

        parent_text = ""

        if parent:
            parent_text = clean_text(
                parent.get_text(
                    " ",
                    strip=True
                )
            )

        # Try to find a useful teaser around the title.
        teaser = parent_text

        if teaser.startswith(text):
            teaser = teaser[
                len(text):
            ].strip()

        article = {
            "title": text,
            "url": full_url,
            "teaser": teaser,
        }

        articles.append(
            article
        )

    # Deduplicate
    unique = []

    seen = set()

    for article in articles:

        key = (
            article["url"],
            article["title"].lower()
        )

        if key in seen:
            continue

        seen.add(key)

        unique.append(
            article
        )

    return unique


# ============================================================
# BUILD QUEUE ARTICLE
# ============================================================

def build_queue_article(
    article
):

    title = clean_text(
        article.get("title")
    )

    teaser = clean_text(
        article.get("teaser")
    )

    url = clean_text(
        article.get("url")
    )

    return {
        "id": None,

        "title": title,

        "url": url,

        "teaser": teaser,

        "description": teaser,

        "content": teaser,

        "article_text": teaser,

        "publisher": None,

        "category_slug": "news",

        "source_language": "en",

        "narration_language": "hi",

        "visual_language": "en",

        "caption_language": "en",

        "hindi_script": None,

        "narration_script": None,

        "script_generated_at": None,

        "voice_status": "PENDING",

        "voice_file": None,

        "visual_keywords": [],

        "scene_plan": None,

        "footage_status": "PENDING",

        "footage_files": [],

        "video_status": "PENDING",

        "final_video_file": None,

        "background_music": True,

        "music_volume": 0.10,

        "rights_status": "PENDING",

        "youtube_upload_status": "PENDING",

        "status": "ARTICLE_READY",

        "retry_count": 0,

        "last_error": None,

        "collected_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "THRAANSH WEBSITE NEWS COLLECTOR"
    )
    print("=" * 70)

    queue = load_queue()

    existing_keys = (
        build_existing_keys(
            queue
        )
    )

    try:

        html = fetch_news_page()

    except Exception as error:

        print()
        print(
            "ERROR reading THRAANSH website:"
        )
        print(error)

        return

    discovered = extract_articles(
        html
    )

    print()
    print(
        f"Possible news links found: {len(discovered)}"
    )

    new_count = 0
    duplicate_count = 0
    skipped_count = 0

    for article in discovered:

        title = clean_text(
            article.get("title")
        )

        url = clean_text(
            article.get("url")
        )

        teaser = clean_text(
            article.get("teaser")
        )

        if len(title) < 15:
            skipped_count += 1
            continue

        # Avoid putting menu text into queue
        if title.lower() in {
            "home",
            "newsletter",
            "news & trends",
            "business & startups",
            "technology & ai",
            "sports",
            "entertainment",
            "culture",
        }:
            skipped_count += 1
            continue

        key_url = (
            f"url:{url}"
            if url
            else ""
        )

        key_title = (
            f"title:{title.lower()}"
        )

        if (
            key_url in existing_keys
            or key_title in existing_keys
        ):
            duplicate_count += 1
            continue

        queue_article = (
            build_queue_article(
                article
            )
        )

        queue.append(
            queue_article
        )

        existing_keys.add(
            key_title
        )

        if key_url:
            existing_keys.add(
                key_url
            )

        new_count += 1

        print()
        print("ADDED:")
        print(title)

        print(
            "URL:",
            url
        )

        print(
            "Teaser:",
            teaser[:200]
        )

    save_queue(
        queue
    )

    print()
    print("=" * 70)
    print("COLLECTOR COMPLETE")
    print("=" * 70)

    print(
        f"New records: {new_count}"
    )

    print(
        f"Duplicates: {duplicate_count}"
    )

    print(
        f"Skipped: {skipped_count}"
    )

    print(
        f"Total queue: {len(queue)}"
    )

    print()
    print(
        f"Saved to: {QUEUE_FILE}"
    )


if __name__ == "__main__":
    main()