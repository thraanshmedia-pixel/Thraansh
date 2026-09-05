from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


# ============================================================
# THRAANSH PRODUCTION SELECTOR V3
#
# PERMANENT RULES
# ------------------------------------------------------------
# 1. Never clear a current selection before replacement exists.
# 2. Exactly ONE article may be production_selected.
# 3. Incomplete production is recovered before a fresh story.
# 4. Published/uploaded stories are never reused.
# 5. If nothing usable exists, exit non-zero immediately.
# 6. Do not silently leave production_selected count at zero.
# ============================================================


PROJECT_FOLDER = Path(__file__).resolve().parents[1]

QUEUE_FILE = (
    PROJECT_FOLDER
    / "data"
    / "article_queue.json"
)


FULL_MIN_CHARS = 1200
MEDIUM_MIN_CHARS = 600
SHORT_MIN_CHARS = 300


# ============================================================
# TERMINAL / FINISHED STATES
# ============================================================

TERMINAL_STATUSES = {
    "PUBLISHED",
    "UPLOADED",
    "YOUTUBE_PUBLISHED",
    "FACEBOOK_PUBLISHED",
    "INSTAGRAM_PUBLISHED",
    "COMPLETE",
    "COMPLETED",
}


# ============================================================
# PIPELINE PROGRESS
#
# Higher score = further through production.
# This lets us recover interrupted work before starting again.
# ============================================================

RECOVERY_PRIORITY = {
    "RIGHTS_PASS": 100,
    "VIDEO_READY": 95,
    "MULTI_VIDEO_READY": 90,
    "MULTI_MEDIA_READY": 85,
    "SCENE_FOOTAGE_READY": 80,
    "SCENE_PLAN_READY": 75,
    "SCENES_READY": 75,
    "VOICE_READY": 70,
    "SCRIPT_READY": 60,

    # retryable failures
    "MULTI_VIDEO_FAILED": 55,
    "SCENE_FOOTAGE_FAILED": 50,
    "VOICE_FAILED": 45,
    "HINDI_SCRIPT_FAILED": 40,
    "HINDI_SCRIPT_QUOTA_WAIT": 35,

    # fresh-production states
    "ARTICLE_READY": 30,
    "READY_FOR_SCRIPT": 25,
    "PRODUCTION_SELECTED": 20,
    "SELECTED": 20,
    "": 10,
}


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value)
        .replace("\r", " ")
        .replace("\n", " ")
        .split()
    ).strip()


def load_queue() -> list[dict]:
    if not QUEUE_FILE.exists():
        raise RuntimeError(
            f"Queue file not found: {QUEUE_FILE}"
        )

    with QUEUE_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise RuntimeError(
            "article_queue.json must contain a list."
        )

    return [
        item
        for item in data
        if isinstance(item, dict)
    ]


def save_queue(queue: list[dict]) -> None:
    QUEUE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_file = QUEUE_FILE.with_suffix(
        ".json.tmp"
    )

    with temp_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            queue,
            file,
            ensure_ascii=False,
            indent=2,
        )

    temp_file.replace(
        QUEUE_FILE
    )


# ============================================================
# SOURCE TEXT
# ============================================================

def get_body(article: dict) -> str:
    fields = [
        "source_text",
        "article_text",
        "full_text",
        "content",
        "body",
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


def classify_source(
    article: dict,
) -> tuple[str, int]:

    body = get_body(
        article
    )

    char_count = len(
        body
    )

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

    # Explicit full-source metadata is trusted.
    if (
        char_count >= FULL_MIN_CHARS
        or long_form_ready
        or source_status == "FULL_SOURCE_READY"
    ):
        return (
            "FULL",
            char_count,
        )

    if char_count >= MEDIUM_MIN_CHARS:
        return (
            "MEDIUM",
            char_count,
        )

    if char_count >= SHORT_MIN_CHARS:
        return (
            "SHORT",
            char_count,
        )

    return (
        "SKIP",
        char_count,
    )


# ============================================================
# PUBLICATION / FINISHED CHECK
# ============================================================

def is_finished(
    article: dict,
) -> bool:

    status = clean_text(
        article.get("status")
    ).upper()

    if status in TERMINAL_STATUSES:
        return True

    publication_fields = [
        "youtube_video_id",
        "youtube_url",
        "facebook_video_id",
        "facebook_post_id",
        "instagram_media_id",
        "instagram_post_id",
    ]

    for field in publication_fields:
        if clean_text(
            article.get(field)
        ):
            return True

    return False


# ============================================================
# CURRENT SELECTED ARTICLE
# ============================================================

def current_selected_articles(
    queue: list[dict],
) -> list[dict]:

    return [
        article
        for article in queue
        if article.get(
            "production_selected"
        ) is True
    ]


# ============================================================
# RECOVER INTERRUPTED PRODUCTION
# ============================================================

def find_recoverable_article(
    queue: list[dict],
):

    candidates = []

    for position, article in enumerate(
        queue
    ):

        if is_finished(
            article
        ):
            continue

        title = clean_text(
            article.get(
                "title"
            )
        )

        if not title:
            continue

        status = clean_text(
            article.get(
                "status"
            )
        ).upper()

        progress = RECOVERY_PRIORITY.get(
            status,
            0,
        )

        # Unknown states are not automatically recovered.
        if progress <= 0:
            continue

        source_class, char_count = (
            classify_source(
                article
            )
        )

        # A fresh article must have reasonable source text.
        #
        # Advanced articles may be recovered even when source
        # metadata is old because they have already passed
        # script/voice/media stages.
        advanced = status in {
            "SCRIPT_READY",
            "VOICE_READY",
            "SCENE_PLAN_READY",
            "SCENES_READY",
            "SCENE_FOOTAGE_READY",
            "MULTI_MEDIA_READY",
            "MULTI_VIDEO_READY",
            "VIDEO_READY",
            "RIGHTS_PASS",
            "VOICE_FAILED",
            "SCENE_FOOTAGE_FAILED",
            "MULTI_VIDEO_FAILED",
        }

        if (
            source_class == "SKIP"
            and not advanced
        ):
            continue

        source_priority = {
            "FULL": 3,
            "MEDIUM": 2,
            "SHORT": 1,
            "SKIP": 0,
        }[source_class]

        candidates.append(
            {
                "article": article,
                "position": position,
                "status": status,
                "progress": progress,
                "source_class": source_class,
                "source_priority":
                    source_priority,
                "char_count": char_count,
            }
        )

    if not candidates:
        return None

    # --------------------------------------------------------
    # First priority:
    # recover the most advanced interrupted production.
    #
    # Second:
    # better source quality.
    #
    # Third:
    # later queue position = newer appended record.
    # --------------------------------------------------------

    candidates.sort(
        key=lambda item: (
            item["progress"],
            item["source_priority"],
            item["position"],
        ),
        reverse=True,
    )

    return candidates[0]


# ============================================================
# FRESH ARTICLE SELECTION
# ============================================================

def find_fresh_article(
    queue: list[dict],
):

    candidates = []

    for position, article in enumerate(
        queue
    ):

        if is_finished(
            article
        ):
            continue

        title = clean_text(
            article.get(
                "title"
            )
        )

        if not title:
            continue

        status = clean_text(
            article.get(
                "status"
            )
        ).upper()

        # Only fresh/retryable states should start from here.
        if status not in {
            "",
            "ARTICLE_READY",
            "READY_FOR_SCRIPT",
            "SELECTED",
            "PRODUCTION_SELECTED",
            "HINDI_SCRIPT_FAILED",
            "HINDI_SCRIPT_QUOTA_WAIT",
        }:
            continue

        source_class, char_count = (
            classify_source(
                article
            )
        )

        if source_class == "SKIP":
            continue

        source_priority = {
            "FULL": 3,
            "MEDIUM": 2,
            "SHORT": 1,
        }[source_class]

        candidates.append(
            {
                "article": article,
                "position": position,
                "status": status,
                "source_class": source_class,
                "source_priority":
                    source_priority,
                "char_count": char_count,
            }
        )

    if not candidates:
        return None

    # Best source quality first.
    # Within same quality, newest appended record first.
    candidates.sort(
        key=lambda item: (
            item["source_priority"],
            item["position"],
        ),
        reverse=True,
    )

    return candidates[0]


# ============================================================
# DURATION SETTINGS
# ============================================================

def duration_settings(
    source_class: str,
) -> dict:

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
# KEEP EXACTLY ONE SELECTION
# ============================================================

def enforce_single_selection(
    queue: list[dict],
    selected: dict,
) -> int:

    cleared = 0

    for article in queue:

        if article is selected:
            continue

        if article.get(
            "production_selected"
        ) is True:

            article[
                "production_selected"
            ] = False

            cleared += 1

    selected[
        "production_selected"
    ] = True

    return cleared


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    print()
    print("=" * 76)
    print(
        "THRAANSH PRODUCTION SELECTOR V3"
    )
    print("=" * 76)

    print()
    print(
        "Policy:"
    )
    print(
        "Current incomplete production: KEEP"
    )
    print(
        "Interrupted production: RECOVER"
    )
    print(
        "Published content: NEVER REUSE"
    )
    print(
        "Zero selected article: NEVER CONTINUE"
    )

    queue = load_queue()

    print()
    print(
        "Articles in queue:",
        len(queue)
    )

    # ========================================================
    # STEP 1
    # Preserve a genuine current incomplete selection.
    # ========================================================

    current = current_selected_articles(
        queue
    )

    selected_info = None

    if current:

        # More than one selection is invalid, but we can repair
        # it by choosing the strongest incomplete one.
        usable_current = [
            article
            for article in current
            if not is_finished(
                article
            )
        ]

        if usable_current:

            current_candidates = []

            for article in usable_current:

                position = queue.index(
                    article
                )

                source_class, char_count = (
                    classify_source(
                        article
                    )
                )

                status = clean_text(
                    article.get(
                        "status"
                    )
                ).upper()

                progress = RECOVERY_PRIORITY.get(
                    status,
                    1,
                )

                current_candidates.append(
                    {
                        "article": article,
                        "position": position,
                        "status": status,
                        "progress": progress,
                        "source_class":
                            source_class,
                        "char_count":
                            char_count,
                    }
                )

            current_candidates.sort(
                key=lambda item: (
                    item["progress"],
                    item["position"],
                ),
                reverse=True,
            )

            selected_info = (
                current_candidates[0]
            )

            print()
            print(
                "RECOVERING EXISTING SELECTION"
            )

    # ========================================================
    # STEP 2
    # If nothing selected, recover interrupted production.
    # ========================================================

    if selected_info is None:

        recovery = find_recoverable_article(
            queue
        )

        if recovery is not None:

            selected_info = recovery

            print()
            print(
                "RECOVERING INCOMPLETE PRODUCTION"
            )

    # ========================================================
    # STEP 3
    # If nothing to recover, choose fresh news.
    # ========================================================

    if selected_info is None:

        fresh = find_fresh_article(
            queue
        )

        if fresh is not None:

            selected_info = fresh

            print()
            print(
                "SELECTING FRESH STORY"
            )

    # ========================================================
    # STEP 4
    # Absolutely nothing available.
    # STOP THE PIPELINE HERE.
    # ========================================================

    if selected_info is None:

        print()
        print("=" * 76)
        print(
            "NO USABLE STORY AVAILABLE"
        )
        print("=" * 76)

        print()
        print(
            "No production_selected article "
            "will be fabricated."
        )

        print(
            "Pipeline must collect fresh news "
            "before video production."
        )

        return 20

    selected = selected_info[
        "article"
    ]

    position = selected_info[
        "position"
    ]

    source_class = selected_info.get(
        "source_class",
        "SHORT",
    )

    char_count = selected_info.get(
        "char_count",
        len(
            get_body(
                selected
            )
        ),
    )

    title = clean_text(
        selected.get(
            "title"
        )
    )

    previous_status = clean_text(
        selected.get(
            "status"
        )
    ).upper()

    # ========================================================
    # IMPORTANT
    #
    # Only clear other selections AFTER we already have the
    # replacement/current article in hand.
    # ========================================================

    cleared = enforce_single_selection(
        queue,
        selected,
    )

    # ========================================================
    # Preserve advanced pipeline status.
    #
    # Do NOT reset VOICE_READY/VIDEO_READY/etc back to
    # ARTICLE_READY.
    # ========================================================

    if previous_status in {
        "",
        "SELECTED",
        "PRODUCTION_SELECTED",
        "READY_FOR_SCRIPT",
    }:
        selected[
            "status"
        ] = "ARTICLE_READY"

    selected[
        "production_scope"
    ] = "GLOBAL"

    selected[
        "story_region"
    ] = selected.get(
        "story_region"
    ) or "UNCLASSIFIED"

    selected[
        "production_queue_position"
    ] = position

    selected[
        "production_selected_at"
    ] = datetime.now().isoformat()

    selected[
        "source_quality_class"
    ] = (
        source_class
        if source_class != "SKIP"
        else selected.get(
            "source_quality_class"
        )
        or "SHORT"
    )

    selected[
        "production_source_characters"
    ] = char_count

    selected[
        "last_error"
    ] = None

    selected[
        "updated_at"
    ] = datetime.now().isoformat()

    # Duration settings are only refreshed when the source
    # classification is valid.
    if source_class in {
        "FULL",
        "MEDIUM",
        "SHORT",
    }:
        selected.update(
            duration_settings(
                source_class
            )
        )

    save_queue(
        queue
    )

    # ========================================================
    # VERIFY AFTER SAVE
    # ========================================================

    verification_queue = load_queue()

    selected_after_save = [
        article
        for article in verification_queue
        if article.get(
            "production_selected"
        ) is True
    ]

    if len(
        selected_after_save
    ) != 1:

        raise RuntimeError(
            "CRITICAL: production selector "
            "did not persist exactly one "
            "production_selected article."
        )

    persisted = selected_after_save[0]

    print()
    print("=" * 76)
    print(
        "THRAANSH PRODUCTION ARTICLE READY"
    )
    print("=" * 76)

    print()
    print(
        "TITLE:"
    )
    print(
        persisted.get(
            "title"
        )
    )

    print()
    print(
        "STATUS:"
    )
    print(
        persisted.get(
            "status"
        )
    )

    print()
    print(
        "SOURCE QUALITY:",
        persisted.get(
            "source_quality_class"
        )
    )

    print(
        "SOURCE CHARACTERS:",
        persisted.get(
            "production_source_characters"
        )
    )

    print()
    print(
        "Queue position:",
        persisted.get(
            "production_queue_position"
        )
    )

    print(
        "Other old selections cleared:",
        cleared
    )

    print()
    print(
        "production_selected count: 1"
    )

    print(
        "production_selected = True"
    )

    print()
    print(
        "SELECTION PERSISTENCE CHECK: PASS"
    )

    print("=" * 76)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
