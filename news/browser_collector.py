from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright


# ============================================================
# THRAANSH NEWS COLLECTOR V2
#
# PURPOSE
# -------
# 1. Read stories from THRAANSH /news.
# 2. Capture headline, publisher, teaser and source URL.
# 3. Visit the linked source page when normally accessible.
# 4. Extract readable article text for INTERNAL summarisation.
# 5. Keep teaser and full source material separate.
# 6. Never bypass login/paywall/access restrictions.
# ============================================================

PROJECT_FOLDER = Path(__file__).resolve().parents[1]

DATA_FOLDER = PROJECT_FOLDER / "data"
QUEUE_FILE = DATA_FOLDER / "article_queue.json"

DATA_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)

NEWS_PAGE_URL = "https://thraansh.com/news"

SOURCE_TIMEOUT_MS = 35000

# We want enough information for a substantive report,
# but this is NOT permission to reproduce an article verbatim.
MIN_GOOD_SOURCE_CHARS = 1200

MAX_SOURCE_CHARS = 18000


# ============================================================
# CLEANING
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = html.unescape(str(value))

    return " ".join(
        value
        .replace("\r", " ")
        .replace("\n", " ")
        .split()
    ).strip()


def normalize_text(value):
    value = clean_text(value).lower()

    value = re.sub(
        r"\W+",
        " ",
        value,
        flags=re.UNICODE
    )

    return value.strip()


# ============================================================
# QUEUE
# ============================================================

def load_queue():
    if not QUEUE_FILE.exists():
        return []

    try:
        with QUEUE_FILE.open(
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


def save_queue(queue):
    temp_file = QUEUE_FILE.with_suffix(
        ".json.tmp"
    )

    with temp_file.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            queue,
            file,
            ensure_ascii=False,
            indent=2
        )

    temp_file.replace(
        QUEUE_FILE
    )


def build_existing_keys(queue):
    keys = set()

    for article in queue:
        title = normalize_text(
            article.get("title")
        )

        url = clean_text(
            article.get("url")
        )

        if title:
            keys.add(
                f"title:{title}"
            )

        if url:
            keys.add(
                f"url:{url}"
            )

    return keys


# ============================================================
# THRAANSH NEWS PAGE EXTRACTION
# ============================================================

def extract_records(page):
    records = []

    page.wait_for_load_state(
        "networkidle"
    )

    page.wait_for_timeout(
        2500
    )

    links = page.locator("a")

    count = links.count()

    print()
    print(
        f"Rendered links found: {count}"
    )

    ignored_exact = {
        "home",
        "news & trends",
        "business & startups",
        "technology & ai",
        "sports",
        "entertainment",
        "fashion & lifestyle",
        "culture",
        "innovation & future",
        "newsletter",
    }

    ignored_domains = [
        "instagram.com",
        "facebook.com",
        "youtube.com",
        "linkedin.com",
        "twitter.com",
        "x.com",
    ]

    for index in range(count):
        link = links.nth(index)

        try:
            href = link.get_attribute(
                "href"
            )

            raw_text = link.inner_text()

        except Exception:
            continue

        if not href or not raw_text:
            continue

        lines = []

        for raw_line in raw_text.splitlines():
            cleaned = clean_text(
                raw_line
            )

            if cleaned:
                lines.append(
                    cleaned
                )

        if not lines:
            continue

        joined_lower = " ".join(
            lines
        ).lower()

        if joined_lower in ignored_exact:
            continue

        full_url = urljoin(
            NEWS_PAGE_URL,
            href
        )

        lower_url = full_url.lower()

        if any(
            domain in lower_url
            for domain in ignored_domains
        ):
            continue

        # --------------------------------------------
        # Time label
        # --------------------------------------------

        time_text = ""

        if lines:
            last_lower = lines[-1].lower()

            if (
                "ago" in last_lower
                or re.fullmatch(
                    r"\d+\s*[mh]",
                    last_lower
                )
            ):
                time_text = lines.pop()

        if not lines:
            continue

        # --------------------------------------------
        # Publisher
        # --------------------------------------------

        publisher = ""

        first = lines[0]

        if (
            len(first) <= 60
            and first.upper() == first
            and any(
                char.isalpha()
                for char in first
            )
        ):
            publisher = lines.pop(0)

        if not lines:
            continue

        # --------------------------------------------
        # Title
        # --------------------------------------------

        title = clean_text(
            lines.pop(0)
        )

        if len(title) < 15:
            continue

        # --------------------------------------------
        # Teaser
        # --------------------------------------------

        teaser = clean_text(
            " ".join(lines)
        )

        if (
            teaser
            and normalize_text(teaser)
            == normalize_text(title)
        ):
            teaser = ""

        if (
            teaser
            and normalize_text(teaser).startswith(
                normalize_text(title)
            )
        ):
            teaser = clean_text(
                teaser[len(title):]
            )

        if not publisher and not teaser:
            continue

        records.append(
            {
                "title": title,
                "teaser": teaser,
                "publisher": publisher,
                "url": full_url,
                "time_text": time_text,
            }
        )

    # --------------------------------------------
    # Deduplicate current page
    # --------------------------------------------

    unique_records = []
    seen = set()

    for record in records:
        key = (
            normalize_text(
                record["title"]
            ),
            record["url"],
        )

        if key in seen:
            continue

        seen.add(key)
        unique_records.append(
            record
        )

    return unique_records


# ============================================================
# SOURCE PAGE SAFETY
# ============================================================

def is_http_url(url):
    try:
        parsed = urlparse(url)

        return (
            parsed.scheme in {
                "http",
                "https",
            }
            and bool(parsed.netloc)
        )

    except Exception:
        return False


def looks_access_restricted(page):
    """
    We do not attempt to bypass access controls.

    This is only a conservative detector for pages that clearly
    present login/subscription/paywall messaging.
    """

    try:
        text = clean_text(
            page.locator("body").inner_text(
                timeout=5000
            )
        ).lower()

    except Exception:
        return False

    indicators = [
        "subscribe to continue",
        "subscription required",
        "sign in to continue",
        "login to continue",
        "log in to continue",
        "register to continue",
        "this content is for subscribers",
        "premium article",
    ]

    return any(
        indicator in text
        for indicator in indicators
    )


# ============================================================
# SOURCE TEXT EXTRACTION
# ============================================================

def extract_json_ld_article(page):
    """
    Many publishers expose articleBody in NewsArticle /
    Article JSON-LD. Use it only when it is normally delivered
    with the accessible page.
    """

    candidates = []

    scripts = page.locator(
        'script[type="application/ld+json"]'
    )

    try:
        count = scripts.count()
    except Exception:
        return ""

    def inspect_object(obj):
        if isinstance(obj, dict):
            article_body = obj.get(
                "articleBody"
            )

            if article_body:
                text = clean_text(
                    article_body
                )

                if len(text) >= 300:
                    candidates.append(
                        text
                    )

            for value in obj.values():
                if isinstance(
                    value,
                    (dict, list)
                ):
                    inspect_object(
                        value
                    )

        elif isinstance(obj, list):
            for value in obj:
                inspect_object(
                    value
                )

    for index in range(
        min(count, 30)
    ):
        try:
            raw = scripts.nth(
                index
            ).text_content()

            if not raw:
                continue

            parsed = json.loads(
                raw
            )

            inspect_object(
                parsed
            )

        except Exception:
            continue

    if not candidates:
        return ""

    return max(
        candidates,
        key=len
    )[:MAX_SOURCE_CHARS]


def extract_article_element(page):
    selectors = [
        "article",
        '[role="article"]',
        ".article-body",
        ".article__body",
        ".story-body",
        ".story__body",
        ".story-content",
        ".article-content",
        ".entry-content",
        ".post-content",
        ".content-body",
    ]

    candidates = []

    for selector in selectors:
        try:
            locator = page.locator(
                selector
            )

            count = min(
                locator.count(),
                5
            )

            for index in range(count):
                text = clean_text(
                    locator.nth(
                        index
                    ).inner_text(
                        timeout=3000
                    )
                )

                if len(text) >= 300:
                    candidates.append(
                        text
                    )

        except Exception:
            continue

    if not candidates:
        return ""

    return max(
        candidates,
        key=len
    )[:MAX_SOURCE_CHARS]


def extract_paragraph_text(page):
    """
    Conservative fallback using visible paragraphs.

    Short navigation/caption/footer fragments are ignored.
    """

    paragraphs = []

    try:
        locator = page.locator(
            "article p"
        )

        if locator.count() < 3:
            locator = page.locator(
                "main p"
            )

        if locator.count() < 3:
            locator = page.locator(
                "p"
            )

        count = min(
            locator.count(),
            150
        )

        seen = set()

        for index in range(count):
            try:
                text = clean_text(
                    locator.nth(
                        index
                    ).inner_text(
                        timeout=1500
                    )
                )

            except Exception:
                continue

            if len(text) < 45:
                continue

            normalized = normalize_text(
                text
            )

            if not normalized:
                continue

            if normalized in seen:
                continue

            seen.add(
                normalized
            )

            paragraphs.append(
                text
            )

    except Exception:
        return ""

    return "\n\n".join(
        paragraphs
    )[:MAX_SOURCE_CHARS]


def clean_extracted_article(
    text,
    title,
    teaser
):
    """
    Remove obvious duplication from extracted source material.
    """

    if not text:
        return ""

    blocks = re.split(
        r"\n+",
        str(text)
    )

    output = []
    seen = set()

    title_norm = normalize_text(
        title
    )

    teaser_norm = normalize_text(
        teaser
    )

    for block in blocks:
        block = clean_text(
            block
        )

        if len(block) < 35:
            continue

        normalized = normalize_text(
            block
        )

        if not normalized:
            continue

        if normalized == title_norm:
            continue

        # The teaser may appear again inside the article.
        if (
            teaser_norm
            and normalized == teaser_norm
        ):
            continue

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        output.append(
            block
        )

    return "\n\n".join(
        output
    )[:MAX_SOURCE_CHARS]


def fetch_source_material(
    context,
    record
):
    """
    Visit the normal public source URL.

    No login automation.
    No subscription bypass.
    No CAPTCHA bypass.
    """

    url = clean_text(
        record.get("url")
    )

    title = clean_text(
        record.get("title")
    )

    teaser = clean_text(
        record.get("teaser")
    )

    result = {
        "source_fetch_status": "NOT_ATTEMPTED",
        "source_text": "",
        "source_text_characters": 0,
        "source_extraction_method": None,
        "source_fetch_error": None,
    }

    if not is_http_url(url):
        result[
            "source_fetch_status"
        ] = "INVALID_URL"

        return result

    page = context.new_page()

    try:
        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=SOURCE_TIMEOUT_MS
        )

        page.wait_for_timeout(
            1800
        )

        if response is not None:
            status_code = response.status

            if status_code >= 400:
                result[
                    "source_fetch_status"
                ] = f"HTTP_{status_code}"

                return result

        if looks_access_restricted(
            page
        ):
            result[
                "source_fetch_status"
            ] = "ACCESS_RESTRICTED"

            return result

        candidates = []

        json_ld = extract_json_ld_article(
            page
        )

        if json_ld:
            candidates.append(
                (
                    "JSON_LD_ARTICLE_BODY",
                    json_ld
                )
            )

        article_element = extract_article_element(
            page
        )

        if article_element:
            candidates.append(
                (
                    "ARTICLE_ELEMENT",
                    article_element
                )
            )

        paragraph_text = extract_paragraph_text(
            page
        )

        if paragraph_text:
            candidates.append(
                (
                    "VISIBLE_PARAGRAPHS",
                    paragraph_text
                )
            )

        if not candidates:
            result[
                "source_fetch_status"
            ] = "NO_ARTICLE_TEXT"

            return result

        method, source_text = max(
            candidates,
            key=lambda item: len(
                item[1]
            )
        )

        source_text = clean_extracted_article(
            source_text,
            title,
            teaser
        )

        if not source_text:
            result[
                "source_fetch_status"
            ] = "NO_ARTICLE_TEXT"

            return result

        result[
            "source_text"
        ] = source_text

        result[
            "source_text_characters"
        ] = len(source_text)

        result[
            "source_extraction_method"
        ] = method

        if (
            len(source_text)
            >= MIN_GOOD_SOURCE_CHARS
        ):
            result[
                "source_fetch_status"
            ] = "FULL_SOURCE_READY"

        else:
            result[
                "source_fetch_status"
            ] = "LIMITED_SOURCE"

        return result

    except Exception as error:
        result[
            "source_fetch_status"
        ] = "FETCH_FAILED"

        result[
            "source_fetch_error"
        ] = clean_text(
            str(error)
        )[:500]

        return result

    finally:
        try:
            page.close()
        except Exception:
            pass


# ============================================================
# QUEUE RECORD
# ============================================================

def build_queue_record(
    record,
    source_result
):
    now = datetime.now(
        timezone.utc
    ).isoformat()

    teaser = clean_text(
        record.get("teaser")
    )

    source_text = clean_text(
        source_result.get(
            "source_text"
        )
    )

    # IMPORTANT:
    # content/article_text now represent extracted source material
    # when available. They are no longer fake copies of teaser.
    usable_content = (
        source_text
        if source_text
        else teaser
    )

    return {
        "id": None,

        "title": clean_text(
            record.get("title")
        ),

        "url": clean_text(
            record.get("url")
        ),

        "publisher": clean_text(
            record.get("publisher")
        ),

        "teaser": teaser,

        "description": teaser,

        "content": usable_content,

        "article_text": usable_content,

        "source_text": source_text,

        "source_text_characters":
            int(
                source_result.get(
                    "source_text_characters"
                )
                or 0
            ),

        "source_fetch_status":
            clean_text(
                source_result.get(
                    "source_fetch_status"
                )
            ),

        "source_extraction_method":
            source_result.get(
                "source_extraction_method"
            ),

        "source_fetch_error":
            source_result.get(
                "source_fetch_error"
            ),

        "long_form_source_ready":
            (
                len(source_text)
                >= MIN_GOOD_SOURCE_CHARS
            ),

        "category_slug": "news",

        "time_text": clean_text(
            record.get("time_text")
        ),

        "source_language": "en",
        "narration_language": "hi",
        "visual_language": "en",
        "caption_language": "en",

        "hindi_script": None,
        "narration_script": None,
        "script_generated_at": None,

        "voice_status": "PENDING",
        "voice_file": None,
        "voice_generated_at": None,

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
        "facebook_upload_status": "PENDING",
        "instagram_publish_status": "PENDING",

        "status": "ARTICLE_READY",

        "retry_count": 0,
        "last_error": None,

        "collected_at": now,
    }


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print("=" * 76)
    print(
        "THRAANSH FULL-SOURCE NEWS COLLECTOR V2"
    )
    print("=" * 76)

    queue = load_queue()

    existing_keys = build_existing_keys(
        queue
    )

    print()
    print(
        f"Existing queue records: {len(queue)}"
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            viewport={
                "width": 1600,
                "height": 1000,
            },
            locale="en-US",
        )

        page = context.new_page()

        print()
        print(
            f"Opening THRAANSH: {NEWS_PAGE_URL}"
        )

        page.goto(
            NEWS_PAGE_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        records = extract_records(
            page
        )

        page.close()

        print()
        print(
            "Possible rendered news records:",
            len(records)
        )

        new_count = 0
        duplicate_count = 0
        missing_teaser_count = 0

        full_source_count = 0
        limited_source_count = 0
        source_failure_count = 0

        for record in records:
            title = clean_text(
                record.get("title")
            )

            url = clean_text(
                record.get("url")
            )

            teaser = clean_text(
                record.get("teaser")
            )

            key_title = (
                f"title:{normalize_text(title)}"
            )

            key_url = (
                f"url:{url}"
                if url
                else ""
            )

            if (
                key_title in existing_keys
                or (
                    key_url
                    and key_url
                    in existing_keys
                )
            ):
                duplicate_count += 1
                continue

            if not teaser:
                missing_teaser_count += 1

                print()
                print(
                    "SKIPPED - teaser missing:"
                )
                print(title)

                continue

            print()
            print("-" * 76)
            print("NEW STORY:")
            print(title)

            print()
            print(
                "Publisher:",
                record.get(
                    "publisher"
                )
            )

            print(
                "Source URL:",
                url
            )

            print(
                "Fetching accessible source material..."
            )

            source_result = fetch_source_material(
                context,
                record
            )

            source_status = source_result.get(
                "source_fetch_status"
            )

            source_chars = int(
                source_result.get(
                    "source_text_characters"
                )
                or 0
            )

            print(
                "Source status:",
                source_status
            )

            print(
                "Source characters:",
                source_chars
            )

            print(
                "Extraction:",
                source_result.get(
                    "source_extraction_method"
                )
                or "NONE"
            )

            if (
                source_status
                == "FULL_SOURCE_READY"
            ):
                full_source_count += 1

                print(
                    "[OK] Long-form source ready"
                )

            elif (
                source_status
                == "LIMITED_SOURCE"
            ):
                limited_source_count += 1

                print(
                    "[WARNING] Source is short. "
                    "Presenter must not pad/repeat."
                )

            else:
                source_failure_count += 1

                print(
                    "[WARNING] Full source unavailable. "
                    "Teaser retained only."
                )

            queue_record = build_queue_record(
                record,
                source_result
            )

            queue.append(
                queue_record
            )

            existing_keys.add(
                key_title
            )

            if key_url:
                existing_keys.add(
                    key_url
                )

            new_count += 1

            print(
                "[ADDED] Story saved to queue"
            )

        browser.close()

    save_queue(
        queue
    )

    print()
    print("=" * 76)
    print(
        "FULL-SOURCE COLLECTOR COMPLETE"
    )
    print("=" * 76)

    print(
        "New records:",
        new_count
    )

    print(
        "Duplicates:",
        duplicate_count
    )

    print(
        "Missing teaser:",
        missing_teaser_count
    )

    print(
        "Long-form sources:",
        full_source_count
    )

    print(
        "Limited sources:",
        limited_source_count
    )

    print(
        "Source unavailable:",
        source_failure_count
    )

    print(
        "Total queue:",
        len(queue)
    )

    print()

    print(
        "Saved to:",
        QUEUE_FILE
    )


if __name__ == "__main__":
    main()