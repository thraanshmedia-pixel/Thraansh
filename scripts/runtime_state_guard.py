from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

QUEUE_FILE = (
    PROJECT_ROOT
    / "data"
    / "article_queue.json"
)


def clean(value):
    if value is None:
        return ""

    return " ".join(
        str(value)
        .replace("\r", " ")
        .replace("\n", " ")
        .split()
    ).strip()


def load_queue():
    if not QUEUE_FILE.exists():
        raise RuntimeError(
            f"Queue missing: {QUEUE_FILE}"
        )

    with QUEUE_FILE.open(
        "r",
        encoding="utf-8",
    ) as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise RuntimeError(
            "article_queue.json must be a list"
        )

    return data


def save_queue(queue):
    temp = QUEUE_FILE.with_suffix(
        ".json.tmp"
    )

    with temp.open(
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            queue,
            handle,
            ensure_ascii=False,
            indent=2,
        )

    temp.replace(
        QUEUE_FILE
    )


def valid_file(
    value,
    minimum_size=5000,
):
    """
    Resolve files safely on both Windows development and
    fresh Linux GitHub runners.

    Stored Windows absolute paths are NOT trusted on Linux.
    We also try basename recovery inside known project folders.
    """

    value = clean(value)

    if not value:
        return None

    raw = Path(value)

    candidates = []

    # Relative path from project root.
    if not raw.is_absolute():
        candidates.append(
            PROJECT_ROOT / raw
        )

    # Exact path may work locally.
    candidates.append(
        raw
    )

    # Filename recovery for paths created on another OS.
    name = raw.name

    for folder in [
        "audio",
        "voice",
        "output",
        "outputs",
        "video",
        "videos",
        "rendered",
        "storage",
    ]:
        candidates.append(
            PROJECT_ROOT
            / folder
            / name
        )

    checked = set()

    for candidate in candidates:

        try:
            candidate = candidate.resolve()
        except Exception:
            continue

        key = str(candidate)

        if key in checked:
            continue

        checked.add(key)

        try:
            if (
                candidate.is_file()
                and candidate.stat().st_size
                >= minimum_size
            ):
                return candidate
        except OSError:
            pass

    return None


def script_text(article):
    for key in [
        "hindi_script",
        "hindi_narration",
        "narration_script",
        "presenter_script",
        "script",
    ]:
        value = clean(
            article.get(key)
        )

        if value:
            return value

    return ""


def voice_path(article):
    for key in [
        "voice_file",
        "audio_file",
        "narration_file",
    ]:
        path = valid_file(
            article.get(key),
            minimum_size=5000,
        )

        if path is not None:
            return path

    return None


def video_path(article):
    for key in [
        "final_video_file",
        "video_file",
        "rendered_video_file",
        "output_video_file",
    ]:
        path = valid_file(
            article.get(key),
            minimum_size=10000,
        )

        if path is not None:
            return path

    return None


def clear_voice(article):
    for key in [
        "voice_file",
        "audio_file",
        "narration_file",
        "voice_generated_at",
    ]:
        article[key] = None

    article["voice_status"] = "PENDING"


def clear_downstream(article):
    """
    Remove runtime files which may point to an old ephemeral
    GitHub Actions runner.
    """

    keys = [
        "final_video_file",
        "video_file",
        "rendered_video_file",
        "output_video_file",

        "joined_video",
        "joined_video_file",

        "subtitle_file",

        "scene_video_files",
        "scene_files",
        "prepared_scene_files",

        "footage_files",
        "media_files",

        "final_video_generated_at",
        "video_generated_at",

        "rights_checked_at",
        "rights_status",
        "copyright_status",
    ]

    for key in keys:
        if key in article:
            article[key] = None


def main():

    print()
    print("=" * 76)
    print(
        "THRAANSH CLOUD RUNTIME STATE GUARD"
    )
    print("=" * 76)

    queue = load_queue()

    selected = [
        article
        for article in queue
        if (
            isinstance(article, dict)
            and article.get(
                "production_selected"
            ) is True
        )
    ]

    print(
        "production_selected count:",
        len(selected),
    )

    # Selector stage will handle zero selections.
    if not selected:

        print(
            "No selected article yet."
        )

        print(
            "Production selector will choose one."
        )

        return 0

    if len(selected) > 1:

        raise RuntimeError(
            "Multiple production_selected "
            "articles exist."
        )

    article = selected[0]

    title = clean(
        article.get(
            "title"
        )
    )

    old_status = clean(
        article.get(
            "status"
        )
    ).upper()

    script = script_text(
        article
    )

    voice = voice_path(
        article
    )

    video = video_path(
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
        "Stored status:",
        old_status,
    )

    print(
        "Hindi script:",
        "YES" if script else "NO",
    )

    print(
        "Voice file:",
        voice if voice else "MISSING",
    )

    print(
        "Final video:",
        video if video else "MISSING",
    )

    # ========================================================
    # COMPLETE VIDEO REALLY EXISTS
    # ========================================================

    if video is not None:

        article[
            "final_video_file"
        ] = str(video)

        print()
        print(
            "Runtime state valid."
        )

        print(
            "No downgrade required."
        )

        return 0

    # ========================================================
    # VIDEO MISSING
    #
    # Anything beyond voice stage is unsafe on a fresh runner.
    # ========================================================

    clear_downstream(
        article
    )

    # ========================================================
    # VOICE REALLY EXISTS
    # ========================================================

    if voice is not None:

        article[
            "voice_file"
        ] = str(voice)

        article[
            "audio_file"
        ] = str(voice)

        article[
            "narration_file"
        ] = str(voice)

        article[
            "voice_status"
        ] = "READY"

        article[
            "status"
        ] = "VOICE_READY"

        new_status = "VOICE_READY"

        reason = (
            "Final video/media missing. "
            "Rebuild from verified voice."
        )

    # ========================================================
    # VOICE MISSING BUT SCRIPT EXISTS
    # ========================================================

    elif script:

        clear_voice(
            article
        )

        article[
            "status"
        ] = "SCRIPT_READY"

        new_status = "SCRIPT_READY"

        reason = (
            "Voice MP3 missing on this fresh runner. "
            "Regenerate Hindi voice."
        )

    # ========================================================
    # SCRIPT ALSO MISSING
    # ========================================================

    else:

        clear_voice(
            article
        )

        article[
            "status"
        ] = "ARTICLE_READY"

        new_status = "ARTICLE_READY"

        reason = (
            "Script and voice files unavailable. "
            "Restart preparation from Hindi script."
        )

    article[
        "last_error"
    ] = None

    article[
        "runtime_state_repaired_at"
    ] = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    article[
        "runtime_state_previous_status"
    ] = old_status

    article[
        "runtime_state_repair_reason"
    ] = reason

    article[
        "updated_at"
    ] = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    save_queue(
        queue
    )

    print()
    print("=" * 76)

    print(
        "STALE CLOUD STATE REPAIRED"
    )

    print(
        "Previous:",
        old_status,
    )

    print(
        "New:",
        new_status,
    )

    print(
        "Reason:",
        reason,
    )

    print("=" * 76)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
