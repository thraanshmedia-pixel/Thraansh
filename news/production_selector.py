import json
from datetime import datetime
from pathlib import Path


# ============================================================
# THRAANSH PRODUCTION SELECTOR V2
#
# RULES
# -----
# 1200+ chars = FULL
# 600-1199   = MEDIUM
# 300-599    = SHORT
# <300       = SKIP
#
# Full stories are preferred first.
# No teaser-only legacy story under 300 characters is selected.
# ============================================================


PROJECT_FOLDER = Path(__file__).resolve().parents[1]

QUEUE_FILE = (
    PROJECT_FOLDER
    / "data"
    / "article_queue.json"
)


PROCESSED_STATUSES = {
    "SCRIPT_READY",
    "VOICE_READY",
    "SCENE_PLAN_READY",
    "SCENE_FOOTAGE_FAILED",
    "MULTI_MEDIA_READY",
    "MULTI_VIDEO_FAILED",
    "VIDEO_READY",
    "RIGHTS_PASS",
    "PUBLISHED",
    "UPLOADED",
}


FULL_MIN_CHARS = 1200
MEDIUM_MIN_CHARS = 600
SHORT_MIN_CHARS = 300


# ============================================================
# TEXT
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


# ============================================================
# LOAD / SAVE
# ============================================================

def load_queue():
    if not QUEUE_FILE.exists():
        print("ERROR: article_queue.json not found.")
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
            "ERROR reading article queue:",
            error
        )

    return []


def save_queue(queue):
    temp = QUEUE_FILE.with_suffix(
        ".json.tmp"
    )

    with temp.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            queue,
            file,
            ensure_ascii=False,
            indent=2
        )

    temp.replace(
        QUEUE_FILE
    )


# ============================================================
# ARTICLE BODY
# ============================================================

def get_body(article):
    """
    Prefer genuine extracted source text.

    Legacy fields are fallback only.
    """

    fields = [
        "source_text",
        "article_text",
        "content",
        "description",
        "teaser",
        "summary",
        "excerpt",
    ]

    best = ""

    for field in fields:
        value = clean_text(
            article.get(field)
        )

        if len(value) > len(best):
            best = value

    return best


# ============================================================
# SOURCE QUALITY
# ============================================================

def classify_source(article):
    body = get_body(
        article
    )

    char_count = len(body)

    source_status = clean_text(
        article.get(
            "source_fetch_status"
        )
    ).upper()

    long_form_ready = bool(
        article.get(
            "long_form_source_ready"
        )
    )

    if (
        char_count >= FULL_MIN_CHARS
        or long_form_ready
        or source_status == "FULL_SOURCE_READY"
    ):
        return (
            "FULL",
            char_count
        )

    if char_count >= MEDIUM_MIN_CHARS:
        return (
            "MEDIUM",
            char_count
        )

    if char_count >= SHORT_MIN_CHARS:
        return (
            "SHORT",
            char_count
        )

    return (
        "SKIP",
        char_count
    )


# ============================================================
# PROCESSED CHECK
# ============================================================

def already_processed(article):
    status = clean_text(
        article.get(
            "status"
        )
    ).upper()

    if status in PROCESSED_STATUSES:
        return True

    if clean_text(
        article.get(
            "hindi_script"
        )
        or article.get(
            "narration_script"
        )
    ):
        return True

    if clean_text(
        article.get(
            "voice_file"
        )
        or article.get(
            "audio_file"
        )
    ):
        return True

    if clean_text(
        article.get(
            "final_video_file"
        )
    ):
        return True

    if clean_text(
        article.get(
            "youtube_video_id"
        )
    ):
        return True

    if clean_text(
        article.get(
            "facebook_video_id"
        )
    ):
        return True

    if clean_text(
        article.get(
            "instagram_media_id"
        )
    ):
        return True

    return False


# ============================================================
# OLD SELECTIONS
# ============================================================

def clear_old_selections(queue):
    count = 0

    for article in queue:
        if article.get(
            "production_selected"
        ):
            article[
                "production_selected"
            ] = False

            count += 1

    return count


# ============================================================
# TIME
# ============================================================

def get_time_value(article):
    for field in [
        "published_at",
        "updated_at",
        "collected_at",
        "created_at",
    ]:
        value = clean_text(
            article.get(field)
        )

        if value:
            return value

    return ""


# ============================================================
# SELECT STORY
# ============================================================

def select_story(queue):
    stats = {
        "total": len(queue),
        "processed": 0,
        "missing_title": 0,
        "skipped_short": 0,
        "full": 0,
        "medium": 0,
        "short": 0,
        "eligible": 0,
    }

    candidates = []

    for position, article in enumerate(
        queue
    ):
        title = clean_text(
            article.get(
                "title"
            )
        )

        if not title:
            stats[
                "missing_title"
            ] += 1
            continue

        if already_processed(
            article
        ):
            stats[
                "processed"
            ] += 1
            continue

        source_class, char_count = (
            classify_source(
                article
            )
        )

        if source_class == "SKIP":
            stats[
                "skipped_short"
            ] += 1
            continue

        stats[
            source_class.lower()
        ] += 1

        stats[
            "eligible"
        ] += 1

        priority = {
            "FULL": 3,
            "MEDIUM": 2,
            "SHORT": 1,
        }[source_class]

        candidates.append(
            {
                "position": position,
                "article": article,
                "source_class":
                    source_class,
                "char_count":
                    char_count,
                "priority":
                    priority,
            }
        )

    if not candidates:
        return (
            None,
            None,
            None,
            stats
        )

    # --------------------------------------------------------
    # Prefer FULL > MEDIUM > SHORT.
    #
    # Within same quality class preserve queue ordering.
    # --------------------------------------------------------

    highest_priority = max(
        item["priority"]
        for item in candidates
    )

    candidates = [
        item
        for item in candidates
        if item["priority"]
        == highest_priority
    ]

    selected = candidates[0]

    return (
        selected["position"],
        selected["article"],
        selected,
        stats
    )


# ============================================================
# DURATION TARGET
# ============================================================

def duration_settings(
    source_class
):
    if source_class == "FULL":
        return {
            "video_duration_class":
                "FULL",
            "target_min_seconds":
                120,
            "target_preferred_seconds":
                150,
            "target_max_seconds":
                180,
        }

    if source_class == "MEDIUM":
        return {
            "video_duration_class":
                "MEDIUM",
            "target_min_seconds":
                60,
            "target_preferred_seconds":
                90,
            "target_max_seconds":
                120,
        }

    return {
        "video_duration_class":
            "SHORT",
        "target_min_seconds":
            30,
        "target_preferred_seconds":
            45,
        "target_max_seconds":
            60,
    }


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print("=" * 76)
    print(
        "THRAANSH PRODUCTION SELECTOR V2"
    )
    print("=" * 76)

    print()
    print(
        "Source policy:"
    )
    print(
        "FULL   : 1200+ characters"
    )
    print(
        "MEDIUM : 600-1199 characters"
    )
    print(
        "SHORT  : 300-599 characters"
    )
    print(
        "SKIP   : below 300 characters"
    )

    queue = load_queue()

    if not queue:
        print()
        print(
            "Article queue is empty."
        )
        return

    print()
    print(
        "Articles in queue:",
        len(queue)
    )

    cleared = clear_old_selections(
        queue
    )

    print(
        "Old selections cleared:",
        cleared
    )

    (
        position,
        selected,
        selection,
        statistics
    ) = select_story(
        queue
    )

    if selected is None:
        save_queue(
            queue
        )

        print()
        print("=" * 76)
        print(
            "NO SUITABLE STORY AVAILABLE"
        )
        print("=" * 76)

        print(
            "Total:",
            statistics["total"]
        )

        print(
            "Already processed:",
            statistics["processed"]
        )

        print(
            "Skipped below 300 chars:",
            statistics[
                "skipped_short"
            ]
        )

        print()
        print(
            "Collect fresh full-source news "
            "before generating another video."
        )

        return

    source_class = selection[
        "source_class"
    ]

    char_count = selection[
        "char_count"
    ]

    settings = duration_settings(
        source_class
    )

    selected[
        "production_selected"
    ] = True

    selected[
        "production_scope"
    ] = "GLOBAL"

    selected[
        "story_region"
    ] = "UNCLASSIFIED"

    selected[
        "production_queue_position"
    ] = position

    selected[
        "production_selected_at"
    ] = datetime.now().isoformat()

    selected[
        "status"
    ] = "ARTICLE_READY"

    selected[
        "last_error"
    ] = None

    selected[
        "updated_at"
    ] = datetime.now().isoformat()

    selected[
        "source_quality_class"
    ] = source_class

    selected[
        "production_source_characters"
    ] = char_count

    selected.update(
        settings
    )

    save_queue(
        queue
    )

    print()
    print("=" * 76)
    print(
        "LATEST SUITABLE STORY SELECTED"
    )
    print("=" * 76)

    print()
    print(
        "TITLE:"
    )
    print(
        selected.get(
            "title"
        )
    )

    print()
    print(
        "Publisher:"
    )
    print(
        clean_text(
            selected.get(
                "publisher"
            )
        )
        or "Unknown"
    )

    print()
    print(
        "Queue position:",
        position
    )

    print()
    print(
        "SOURCE QUALITY:",
        source_class
    )

    print(
        "SOURCE CHARACTERS:",
        char_count
    )

    print()
    print(
        "VIDEO TARGET:"
    )

    print(
        settings[
            "target_min_seconds"
        ],
        "-",
        settings[
            "target_max_seconds"
        ],
        "seconds"
    )

    print()
    print(
        "production_selected = True"
    )

    print(
        "status = ARTICLE_READY"
    )

    print()
    print(
        "Next:"
    )

    print(
        "Run Hindi presenter only after "
        "source quality is confirmed."
    )


if __name__ == "__main__":
    main()