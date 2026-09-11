"""
THRAANSH PERMANENT AUTOMATION WORKER V8.1
SELF-HEALING 3-PLATFORM WORKER

Designed for:
- GitHub Actions every 5 minutes
- Windows Task Scheduler every 5 minutes

Behavior:
- Prepares the next story before the scheduled publication slot.
- Publishes at/after the slot.
- Retries temporary failures.
- Never intentionally republishes a platform already verified PUBLISHED.
- Keeps RIGHTS_PASS + V4 identity safety mandatory.
- Persists state so a Windows/Python crash can resume on the next invocation.
- Uses an OS-backed Windows file lock that is automatically released if Python crashes.
- Applies per-stage timeouts and kills hung child process trees.
- Recovers overdue prepared slots.
- Recovers partially published slots.
- Returns FAILURE when preparation/publication actually fails.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    import msvcrt
except ImportError:
    msvcrt = None


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

QUEUE_FILE = (
    PROJECT_ROOT
    / "data"
    / "article_queue.json"
)

STATE_FILE = (
    PROJECT_ROOT
    / "data"
    / "automation_state_v7.json"
)

LOCK_FILE = (
    PROJECT_ROOT
    / "data"
    / "thraansh_v7.lock"
)

LOG_DIR = (
    PROJECT_ROOT
    / "logs"
)

IST = ZoneInfo(
    "Asia/Kolkata"
)


# ============================================================
# THRAANSH DAILY SCHEDULE
# ============================================================

SCHEDULE_SLOTS = (
    "07:00",
    "09:00",
    "11:00",
    "13:00",
    "15:00",
    "17:00",
    "19:00",
    "21:00",
)

PREPARE_MINUTES_BEFORE = 45

PUBLISH_GRACE_MINUTES = 75


# ============================================================
# RETRIES
# ============================================================

STAGE_ATTEMPTS = 3

STAGE_RETRY_SECONDS = (
    0,
    20,
    60,
)

PLATFORM_ATTEMPTS_PER_INVOCATION = 2

PLATFORM_RETRY_SECONDS = 30


# ============================================================
# HARD TIMEOUTS
# ============================================================

STAGE_TIMEOUT_SECONDS = {

    "NEWS COLLECTION":
        20 * 60,

    "PRODUCTION SELECTION":
        5 * 60,

    "HINDI SCRIPT":
        7 * 60,

    "HINDI VOICE":
        12 * 60,

    "SCENE PLANNING":
        10 * 60,

    "STORY FOOTAGE":
        40 * 60,

    "FINAL VIDEO":
        50 * 60,

    "RIGHTS CHECK":
        10 * 60,

    "YOUTUBE":
        30 * 60,

    "FACEBOOK":
        30 * 60,

    "INSTAGRAM STORAGE":
        30 * 60,

    "INSTAGRAM":
        20 * 60,
}

DEFAULT_STAGE_TIMEOUT_SECONDS = (
    30 * 60
)


# ============================================================
# GLOBAL LOCK HANDLE
# ============================================================

_LOCK_HANDLE = None


# ============================================================
# PIPELINE STAGES
# ============================================================

CONTENT_STAGES = [

    (
        "NEWS COLLECTION",
        PROJECT_ROOT
        / "news"
        / "browser_collector.py"
    ),

    (
        "PRODUCTION SELECTION",
        PROJECT_ROOT
        / "news"
        / "production_selector.py"
    ),

    (
        "HINDI SCRIPT",
        PROJECT_ROOT
        / "scripts"
        / "hindi_presenter.py"
    ),

    (
        "HINDI VOICE",
        PROJECT_ROOT
        / "voice"
        / "generator.py"
    ),

    (
        "SCENE PLANNING",
        PROJECT_ROOT
        / "scripts"
        / "scene_planner.py"
    ),

    (
        "STORY FOOTAGE",
        PROJECT_ROOT
        / "footage"
        / "multi_scene_generator.py"
    ),

    (
        "FINAL VIDEO",
        PROJECT_ROOT
        / "video"
        / "multi_generator.py"
    ),

    (
        "RIGHTS CHECK",
        PROJECT_ROOT
        / "copyright"
        / "rights_checker.py"
    ),
]


# ============================================================
# PLATFORM STAGES
# ============================================================

YOUTUBE = (
    "YOUTUBE",
    PROJECT_ROOT
    / "youtube"
    / "uploader.py"
)

FACEBOOK = (
    "FACEBOOK",
    PROJECT_ROOT
    / "facebook"
    / "publisher.py"
)

IG_STORAGE = (
    "INSTAGRAM STORAGE",
    PROJECT_ROOT
    / "instagram"
    / "storage_uploader.py"
)

INSTAGRAM = (
    "INSTAGRAM",
    PROJECT_ROOT
    / "instagram"
    / "publisher.py"
)


# ============================================================
# LOGGING
# ============================================================

def log(
    msg: str
) -> None:

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    stamp = (
        datetime.now(IST)
        .strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    line = (
        f"[{stamp} IST] "
        f"{msg}"
    )

    print(
        line,
        flush=True
    )

    with (
        LOG_DIR
        / "automation_v7.log"
    ).open(
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            line
            + "\n"
        )


# ============================================================
# JSON HELPERS
# ============================================================

def load_json(
    path: Path,
    default: Any
) -> Any:

    try:

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        return default


def atomic_json(
    path: Path,
    data: Any
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temp = (
        path.with_suffix(
            path.suffix
            + ".tmp"
        )
    )

    temp.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    temp.replace(
        path
    )


# ============================================================
# ARTICLE QUEUE
# ============================================================

def articles() -> list[dict]:

    data = load_json(
        QUEUE_FILE,
        []
    )

    if isinstance(
        data,
        list
    ):

        return [
            item
            for item in data
            if isinstance(
                item,
                dict
            )
        ]

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

                return [
                    item
                    for item in value
                    if isinstance(
                        item,
                        dict
                    )
                ]

    raise RuntimeError(
        "Could not locate article list."
    )


def current_article() -> dict:

    selected = [

        article

        for article
        in articles()

        if article.get(
            "production_selected"
        ) is True
    ]

    if not selected:

        raise RuntimeError(
            "No production_selected article."
        )

    if len(selected) > 1:

        titles = [

            str(
                item.get(
                    "title"
                )
                or "UNTITLED"
            )

            for item
            in selected
        ]

        raise RuntimeError(
            "Multiple production_selected articles exist: "
            + " | ".join(
                titles
            )
        )

    return selected[0]


# ============================================================
# GEMINI QUOTA
# ============================================================

def gemini_quota_wait() -> tuple[
    bool,
    str
]:

    try:

        article = (
            current_article()
        )

    except Exception:

        return (
            False,
            ""
        )

    status = str(
        article.get(
            "status"
        )
        or ""
    ).strip().upper()

    if (
        status
        != "HINDI_SCRIPT_QUOTA_WAIT"
    ):

        return (
            False,
            ""
        )

    raw = str(
        article.get(
            "gemini_retry_not_before"
        )
        or ""
    ).strip()

    if not raw:

        return (
            False,
            ""
        )

    try:

        retry_at = (
            datetime
            .fromisoformat(
                raw
            )
        )

        if (
            retry_at.tzinfo
            is None
        ):

            retry_at = (
                retry_at.replace(
                    tzinfo=IST
                )
            )

        retry_at = (
            retry_at
            .astimezone(
                IST
            )
        )

    except Exception:

        return (
            False,
            ""
        )

    if (
        datetime.now(IST)
        < retry_at
    ):

        return (
            True,
            retry_at.isoformat()
        )

    return (
        False,
        retry_at.isoformat()
    )


# ============================================================
# PATH RESOLUTION
# ============================================================

def resolve_path(
    value: Any
) -> Path | None:

    if not value:

        return None

    path = Path(
        str(
            value
        )
    )

    if not path.is_absolute():

        path = (
            PROJECT_ROOT
            / path
        )

    return path.resolve()


# ============================================================
# IDENTITY SAFETY
# ============================================================

def identity_gate(
    article: dict
) -> tuple[
    bool,
    str
]:

    version = str(
        article.get(
            "media_generator_version"
        )
        or ""
    )

    if (
        version
        !=
        "FAST_MULTI_SOURCE_IDENTITY_SAFE_V4"
    ):

        return (
            False,
            "media_generator_version "
            "is not identity-safe V4."
        )

    scenes = article.get(
        "scene_plan"
    )

    if (
        not isinstance(
            scenes,
            list
        )
        or not scenes
    ):

        return (
            False,
            "No scene_plan."
        )

    for index, scene in enumerate(
        scenes,
        start=1
    ):

        if (
            scene.get(
                "visual_identity_safe"
            )
            is not True
        ):

            return (
                False,
                f"Scene {index}: "
                "visual_identity_safe "
                "is not True."
            )

        mode = str(
            scene.get(
                "visual_usage_mode"
            )
            or ""
        ).strip().upper()

        method = str(
            scene.get(
                "identity_verification_method"
            )
            or ""
        ).strip().upper()

        subject = str(
            scene.get(
                "identity_subject"
            )
            or ""
        ).strip()

        source = str(
            scene.get(
                "media_source"
            )
            or ""
        ).strip().upper()

        if (
            mode
            == "CONTEXTUAL_MEDIA"
        ):

            if (
                method
                != "NOT_IDENTITY_MEDIA"
                or subject
            ):

                return (
                    False,
                    f"Scene {index}: "
                    "invalid contextual "
                    "identity metadata."
                )

        elif (
            mode
            ==
            "EXACT_PERSON_VERIFIED_METADATA"
        ):

            if (
                source
                != "WIKIMEDIA"
                or not subject
                or method
                !=
                "WIKIMEDIA_NAME_METADATA_MATCH"
            ):

                return (
                    False,
                    f"Scene {index}: "
                    "invalid exact-person "
                    "verification metadata."
                )

        else:

            return (
                False,
                f"Scene {index}: "
                "unsupported "
                f"visual_usage_mode "
                f"{mode!r}."
            )

    return (
        True,
        f"{len(scenes)} scenes "
        "identity-safe."
    )


# ============================================================
# RIGHTS GATE
# ============================================================

def rights_gate() -> tuple[
    bool,
    str
]:

    try:

        article = (
            current_article()
        )

    except Exception as error:

        return (
            False,
            str(
                error
            )
        )

    if (
        str(
            article.get(
                "status"
            )
            or ""
        ).upper()
        != "RIGHTS_PASS"
    ):

        return (
            False,
            "Article status "
            "is not RIGHTS_PASS."
        )

    if (
        str(
            article.get(
                "rights_status"
            )
            or ""
        ).upper()
        != "RIGHTS_PASS"
    ):

        return (
            False,
            "rights_status "
            "is not RIGHTS_PASS."
        )

    manifest = resolve_path(
        article.get(
            "rights_manifest_file"
        )
    )

    video = resolve_path(
        article.get(
            "final_video_file"
        )
    )

    if (
        not manifest
        or not manifest.is_file()
    ):

        return (
            False,
            "Rights manifest missing."
        )

    if (
        not video
        or not video.is_file()
        or video.suffix.lower()
        != ".mp4"
        or video.stat().st_size
        <= 0
    ):

        return (
            False,
            "Exact final MP4 "
            "missing/invalid."
        )

    ok, message = (
        identity_gate(
            article
        )
    )

    if not ok:

        return (
            False,
            message
        )

    return (
        True,
        "RIGHTS_PASS + manifest + "
        "exact MP4 + V4 identity "
        "safety confirmed."
    )


# ============================================================
# PLATFORM VERIFIERS
# ============================================================

def youtube_ok(
    article: dict
) -> bool:

    return (

        bool(
            str(
                article.get(
                    "youtube_video_id"
                )
                or ""
            ).strip()
        )

        and

        str(
            article.get(
                "youtube_upload_status"
            )
            or ""
        ).upper()
        == "PUBLISHED"
    )


def facebook_ok(
    article: dict
) -> bool:

    return (

        bool(
            str(
                article.get(
                    "facebook_video_id"
                )
                or ""
            ).strip()
        )

        and

        str(
            article.get(
                "facebook_upload_status"
            )
            or ""
        ).upper()
        == "PUBLISHED"
    )


def instagram_ok(
    article: dict
) -> bool:

    return (

        bool(
            str(
                article.get(
                    "instagram_media_id"
                )
                or ""
            ).strip()
        )

        and

        str(
            article.get(
                "instagram_publish_status"
            )
            or ""
        ).upper()
        == "PUBLISHED"
    )


def instagram_storage_ok(
    article: dict
) -> bool:

    return (

        str(
            article.get(
                "instagram_storage_status"
            )
            or ""
        ).upper()
        == "UPLOADED"

        and

        str(
            article.get(
                "instagram_video_url"
            )
            or ""
        ).startswith(
            "https://"
        )
    )


# ============================================================
# PROCESS TERMINATION
# ============================================================

def _terminate_process_tree(
    proc: subprocess.Popen
) -> None:

    if (
        proc.poll()
        is not None
    ):

        return

    if (
        os.name
        == "nt"
    ):

        try:

            subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(
                        proc.pid
                    ),
                    "/T",
                    "/F",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=30,
            )

            return

        except Exception:

            pass

    try:

        proc.kill()

    except Exception:

        pass


# ============================================================
# RUN ONE STAGE
# ============================================================

def run_once(
    name: str,
    script: Path
) -> bool:

    if not script.is_file():

        log(
            f"{name}: "
            f"script missing: "
            f"{script}"
        )

        return False

    timeout_seconds = (
        STAGE_TIMEOUT_SECONDS
        .get(
            name,
            DEFAULT_STAGE_TIMEOUT_SECONDS
        )
    )

    log(
        f"{name}: START "
        f"(timeout="
        f"{timeout_seconds // 60}m)"
    )

    proc = None

    try:

        creationflags = 0

        if (
            os.name == "nt"
            and hasattr(
                subprocess,
                "CREATE_NEW_PROCESS_GROUP"
            )
        ):

            creationflags = (
                subprocess
                .CREATE_NEW_PROCESS_GROUP
            )

        proc = subprocess.Popen(
            [
                sys.executable,
                str(
                    script
                ),
            ],
            cwd=str(
                PROJECT_ROOT
            ),
            creationflags=creationflags,
            stdin=subprocess.DEVNULL,
        )

        try:

            returncode = (
                proc.wait(
                    timeout=
                    timeout_seconds
                )
            )

        except (
            subprocess
            .TimeoutExpired
        ):

            log(
                f"{name}: TIMEOUT after "
                f"{timeout_seconds // 60}m; "
                "terminating hung "
                "process tree."
            )

            _terminate_process_tree(
                proc
            )

            try:

                proc.wait(
                    timeout=30
                )

            except Exception:

                pass

            return False

        if (
            returncode
            == 0
        ):

            log(
                f"{name}: OK"
            )

            return True

        log(
            f"{name}: FAILED "
            f"exit={returncode}"
        )

        return False

    except KeyboardInterrupt:

        log(
            f"{name}: console interrupt "
            "ignored; preserving child "
            "and re-checking durable state."
        )

        if (
            proc
            is not None
        ):

            try:

                returncode = (
                    proc.wait(
                        timeout=30
                    )
                )

                if (
                    returncode
                    == 0
                ):

                    log(
                        f"{name}: "
                        "OK after interrupt"
                    )

                    return True

            except Exception:

                pass

        return False

    except Exception as error:

        if (
            proc
            is not None
        ):

            _terminate_process_tree(
                proc
            )

        log(
            f"{name}: EXCEPTION "
            f"{error}"
        )

        return False


# ============================================================
# RUN STAGE WITH RETRY
# ============================================================

def run_with_retry(
    name: str,
    script: Path,
    attempts: int =
        STAGE_ATTEMPTS
) -> bool:

    for attempt in range(
        1,
        attempts + 1
    ):

        if (
            attempt > 1
        ):

            delay = (
                STAGE_RETRY_SECONDS[
                    min(
                        attempt - 1,
                        len(
                            STAGE_RETRY_SECONDS
                        )
                        - 1
                    )
                ]
            )

            log(
                f"{name}: retry "
                f"{attempt}/{attempts} "
                f"after {delay}s"
            )

            time.sleep(
                delay
            )

        if (
            run_once(
                name,
                script
            )
        ):

            return True

    return False


# ============================================================
# WORKER LOCK
# ============================================================

def acquire_lock() -> bool:

    global _LOCK_HANDLE

    LOCK_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if (
        msvcrt is not None
        and os.name == "nt"
    ):

        handle = LOCK_FILE.open(
            "a+",
            encoding="utf-8"
        )

        handle.seek(
            0,
            os.SEEK_END
        )

        if (
            handle.tell()
            == 0
        ):

            handle.write(
                " "
            )

            handle.flush()

        handle.seek(
            0
        )

        try:

            msvcrt.locking(
                handle.fileno(),
                msvcrt.LK_NBLCK,
                1
            )

        except OSError:

            handle.close()

            log(
                "Another worker is "
                "genuinely running; "
                "exiting safely."
            )

            return False

        _LOCK_HANDLE = (
            handle
        )

        handle.seek(
            1
        )

        handle.truncate()

        handle.write(
            json.dumps(
                {
                    "pid":
                        os.getpid(),

                    "started":
                        datetime
                        .now(IST)
                        .isoformat(),

                    "lock_type":
                        "WINDOWS_OS_FILE_LOCK",
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        handle.flush()

        try:

            os.fsync(
                handle.fileno()
            )

        except OSError:

            pass

        log(
            "Worker lock acquired "
            f"by PID {os.getpid()}."
        )

        return True

    payload = json.dumps(
        {
            "pid":
                os.getpid(),

            "started":
                datetime
                .now(IST)
                .isoformat(),
        },
        ensure_ascii=False,
        indent=2,
    )

    try:

        fd = os.open(
            str(
                LOCK_FILE
            ),
            os.O_CREAT
            | os.O_EXCL
            | os.O_WRONLY
        )

    except FileExistsError:

        log(
            "Another worker appears "
            "to be running; "
            "exiting safely."
        )

        return False

    with os.fdopen(
        fd,
        "w",
        encoding="utf-8"
    ) as handle:

        handle.write(
            payload
        )

    return True


def release_lock() -> None:

    global _LOCK_HANDLE

    if (
        _LOCK_HANDLE
        is not None
    ):

        try:

            _LOCK_HANDLE.seek(
                0
            )

            msvcrt.locking(
                _LOCK_HANDLE.fileno(),
                msvcrt.LK_UNLCK,
                1
            )

        except Exception:

            pass

        try:

            _LOCK_HANDLE.close()

        except Exception:

            pass

        _LOCK_HANDLE = None

        return

    if (
        msvcrt is None
        or os.name != "nt"
    ):

        try:

            LOCK_FILE.unlink(
                missing_ok=True
            )

        except Exception:

            pass


# ============================================================
# SCHEDULE HELPERS
# ============================================================

def slot_dt(
    day,
    slot: str
) -> datetime:

    hour, minute = map(
        int,
        slot.split(
            ":"
        )
    )

    return datetime(
        day.year,
        day.month,
        day.day,
        hour,
        minute,
        tzinfo=IST
    )


def schedule_context(
    now: datetime
):

    candidates = []

    for day_delta in (
        -1,
        0,
        1
    ):

        day = (
            now
            + timedelta(
                days=day_delta
            )
        ).date()

        for slot in (
            SCHEDULE_SLOTS
        ):

            dt = slot_dt(
                day,
                slot
            )

            candidates.append(
                (
                    dt,
                    slot
                )
            )

    next_dt, next_slot = min(
        (
            item
            for item
            in candidates
            if item[0] > now
        ),
        key=lambda item:
            item[0]
    )

    due = [

        (
            dt,
            slot
        )

        for dt, slot
        in candidates

        if (
            dt <= now
            <= dt
            + timedelta(
                minutes=
                PUBLISH_GRACE_MINUTES
            )
        )
    ]

    due_item = (

        max(
            due,
            key=lambda item:
                item[0]
        )

        if due

        else None
    )

    return (
        next_dt,
        next_slot,
        due_item
    )


def slot_key(
    dt: datetime
) -> str:

    return dt.strftime(
        "%Y-%m-%dT%H:%M"
    )


# ============================================================
# STATE
# ============================================================

def load_state() -> dict:

    return load_json(
        STATE_FILE,
        {}
    )


def save_state(
    state: dict
) -> None:

    state[
        "updated_at_ist"
    ] = (
        datetime
        .now(IST)
        .isoformat()
    )

    atomic_json(
        STATE_FILE,
        state
    )


# ============================================================
# PREPARATION
# ============================================================

def prepare_for(
    slot_time: datetime
) -> bool:

    key = slot_key(
        slot_time
    )

    state = (
        load_state()
    )

    same_slot = (
        state.get(
            "prepared_slot"
        )
        == key
    )

    prepare_status = str(
        state.get(
            "prepare_status"
        )
        or ""
    ).strip().upper()

    # ========================================================
    # EXISTING READY PACKAGE
    # ========================================================

    if (
        same_slot
        and prepare_status
        == "READY"
    ):

        article = (
            current_article()
        )

        prepared_title = str(
            state.get(
                "prepared_title"
            )
            or ""
        ).strip()

        current_title = str(
            article.get(
                "title"
            )
            or ""
        ).strip()

        video_value = (

            article.get(
                "final_video_file"
            )

            or

            state.get(
                "prepared_video"
            )

            or ""
        )

        video_path = (

            Path(
                str(
                    video_value
                )
            )

            if video_value

            else None
        )

        video_exists = bool(

            video_path

            and

            video_path.is_file()

            and

            video_path.stat().st_size
            > 10000
        )

        title_matches = bool(

            prepared_title

            and

            current_title

            and

            prepared_title
            == current_title
        )

        ok, message = (
            rights_gate()
        )

        if (
            ok
            and title_matches
            and video_exists
        ):

            log(
                f"{key}: existing READY "
                "package VERIFIED; "
                f"{message}; "
                f"video={video_path}"
            )

            return True

        log(
            f"{key}: stale READY "
            "state detected. "
            f"title_matches="
            f"{title_matches}, "
            f"video_exists="
            f"{video_exists}, "
            f"rights_ok={ok}. "
            "Rebuilding."
        )

        state.update(
            {
                "prepare_status":
                    "REBUILD_REQUIRED",

                "failed_stage":
                    "READY PACKAGE VALIDATION",
            }
        )

        save_state(
            state
        )

    elif same_slot:

        log(
            f"{key}: previous "
            "preparation state is "
            f"{prepare_status or 'UNKNOWN'}; "
            "it is NOT READY and will "
            "be rebuilt/resumed."
        )

    # ========================================================
    # START PREPARATION
    # ========================================================

    log(
        f"PREPARING story "
        f"for slot {key}"
    )

    state.update(
        {
            "prepared_slot":
                key,

            "prepare_status":
                "PREPARING",

            "failed_stage":
                "",
        }
    )

    save_state(
        state
    )

    for (
        name,
        script
    ) in CONTENT_STAGES:

        # ====================================================
        # GEMINI COOLDOWN
        # ====================================================

        if (
            name
            == "HINDI SCRIPT"
        ):

            waiting, retry_at = (
                gemini_quota_wait()
            )

            if waiting:

                state.update(
                    {
                        "prepared_slot":
                            key,

                        "prepare_status":
                            "GEMINI_QUOTA_WAIT",

                        "failed_stage":
                            "HINDI SCRIPT",

                        "gemini_retry_not_before":
                            retry_at,
                    }
                )

                save_state(
                    state
                )

                log(
                    "HINDI SCRIPT: "
                    "Gemini quota cooldown "
                    "active; no API call made. "
                    f"Retry not before "
                    f"{retry_at}."
                )

                return False

            ok = run_once(
                name,
                script
            )

        else:

            ok = run_with_retry(
                name,
                script
            )

        # ====================================================
        # STAGE FAILURE
        # ====================================================

        if not ok:

            if (
                name
                == "HINDI SCRIPT"
            ):

                waiting, retry_at = (
                    gemini_quota_wait()
                )

                if waiting:

                    state.update(
                        {
                            "prepared_slot":
                                key,

                            "prepare_status":
                                "GEMINI_QUOTA_WAIT",

                            "failed_stage":
                                "HINDI SCRIPT",

                            "gemini_retry_not_before":
                                retry_at,
                        }
                    )

                    save_state(
                        state
                    )

                    log(
                        "PREPARATION PAUSED "
                        "at HINDI SCRIPT: "
                        "Gemini quota cooldown "
                        f"until {retry_at}."
                    )

                    return False

            state.update(
                {
                    "prepared_slot":
                        key,

                    "prepare_status":
                        "FAILED",

                    "failed_stage":
                        name,
                }
            )

            save_state(
                state
            )

            log(
                "PREPARATION FAILED "
                f"at {name}; "
                "publication remains blocked."
            )

            return False

    # ========================================================
    # FINAL VIDEO VALIDATION
    # ========================================================

    article = (
        current_article()
    )

    final_video_value = str(
        article.get(
            "final_video_file"
        )
        or ""
    ).strip()

    if not final_video_value:

        state.update(
            {
                "prepared_slot":
                    key,

                "prepare_status":
                    "FAILED",

                "failed_stage":
                    "FINAL VIDEO VALIDATION",
            }
        )

        save_state(
            state
        )

        log(
            "PREPARATION FAILED: "
            "final_video_file missing "
            "from article state."
        )

        return False

    final_video = Path(
        final_video_value
    )

    if (
        not final_video.is_file()
        or final_video.stat().st_size
        <= 10000
    ):

        state.update(
            {
                "prepared_slot":
                    key,

                "prepare_status":
                    "FAILED",

                "failed_stage":
                    "FINAL VIDEO VALIDATION",
            }
        )

        save_state(
            state
        )

        log(
            "PREPARATION FAILED: "
            "final video does not "
            "exist or is invalid: "
            f"{final_video}"
        )

        return False

    # ========================================================
    # RIGHTS GATE
    # ========================================================

    ok, message = (
        rights_gate()
    )

    if not ok:

        state.update(
            {
                "prepared_slot":
                    key,

                "prepare_status":
                    "RIGHTS_BLOCKED",

                "failed_stage":
                    "RIGHTS GATE",
            }
        )

        save_state(
            state
        )

        log(
            "PREPARATION BLOCKED: "
            f"{message}"
        )

        return False

    # ========================================================
    # READY
    # ========================================================

    article = (
        current_article()
    )

    state.update(
        {
            "prepared_slot":
                key,

            "prepare_status":
                "READY",

            "failed_stage":
                "",

            "prepared_title":
                str(
                    article.get(
                        "title"
                    )
                    or ""
                ),

            "prepared_video":
                str(
                    article.get(
                        "final_video_file"
                    )
                    or ""
                ),

            "prepared_at_ist":
                datetime
                .now(IST)
                .isoformat(),
        }
    )

    save_state(
        state
    )

    log(
        f"READY for {key}: "
        f"{article.get('title')} | "
        f"video="
        f"{article.get('final_video_file')}"
    )

    return True


# ============================================================
# PLATFORM RETRY
# ============================================================

def platform_retry(
    name: str,
    script: Path,
    verifier
) -> bool:

    article = (
        current_article()
    )

    if verifier(
        article
    ):

        log(
            f"{name}: already "
            "PUBLISHED; "
            "skip duplicate."
        )

        return True

    for attempt in range(
        1,
        PLATFORM_ATTEMPTS_PER_INVOCATION
        + 1
    ):

        if (
            attempt > 1
        ):

            log(
                f"{name}: retry "
                f"after "
                f"{PLATFORM_RETRY_SECONDS}s"
            )

            time.sleep(
                PLATFORM_RETRY_SECONDS
            )

        run_once(
            name,
            script
        )

        article = (
            current_article()
        )

        if verifier(
            article
        ):

            log(
                f"{name}: "
                "VERIFIED PUBLISHED"
            )

            return True

    log(
        f"{name}: still not "
        "published; next "
        "worker run will retry."
    )

    return False


# ============================================================
# PUBLISH SLOT
# ============================================================

def publish_slot(
    slot_time: datetime
) -> bool:

    key = slot_key(
        slot_time
    )

    state = (
        load_state()
    )

    if (
        state.get(
            "completed_slot"
        )
        == key
    ):

        log(
            f"{key}: "
            "already COMPLETE."
        )

        return True

    if (
        state.get(
            "prepared_slot"
        )
        != key

        or

        state.get(
            "prepare_status"
        )
        != "READY"
    ):

        log(
            f"{key}: no READY package; "
            "preparing now "
            "(publication may be late)."
        )

        if not prepare_for(
            slot_time
        ):

            return False

        state = (
            load_state()
        )

    ok, message = (
        rights_gate()
    )

    if not ok:

        log(
            "PUBLISH BLOCKED: "
            f"{message}"
        )

        return False

    article = (
        current_article()
    )

    prepared_title = str(
        state.get(
            "prepared_title"
        )
        or ""
    )

    current_title = str(
        article.get(
            "title"
        )
        or ""
    )

    if (
        prepared_title
        and prepared_title
        != current_title
    ):

        log(
            "PUBLISH BLOCKED: "
            "current article differs "
            "from prepared article."
        )

        return False

    # ========================================================
    # YOUTUBE
    # ========================================================

    youtube_result = (
        platform_retry(
            *YOUTUBE,
            youtube_ok
        )
    )

    # ========================================================
    # FACEBOOK
    # ========================================================

    facebook_result = (
        platform_retry(
            *FACEBOOK,
            facebook_ok
        )
    )

    # ========================================================
    # INSTAGRAM STORAGE
    # ========================================================

    article = (
        current_article()
    )

    if not instagram_storage_ok(
        article
    ):

        run_with_retry(
            *IG_STORAGE,
            attempts=2
        )

    # ========================================================
    # INSTAGRAM
    # ========================================================

    instagram_result = (
        platform_retry(
            *INSTAGRAM,
            instagram_ok
        )
    )

    # ========================================================
    # DURABLE FINAL VERIFICATION
    # ========================================================

    final_article = (
        current_article()
    )

    youtube_result = (
        youtube_ok(
            final_article
        )
    )

    facebook_result = (
        facebook_ok(
            final_article
        )
    )

    instagram_result = (
        instagram_ok(
            final_article
        )
    )

    log(
        "FINAL PLATFORM STATE: "
        f"YouTube="
        f"{'PUBLISHED' if youtube_result else 'PENDING'} | "
        f"Facebook="
        f"{'PUBLISHED' if facebook_result else 'PENDING'} | "
        f"Instagram="
        f"{'PUBLISHED' if instagram_result else 'PENDING'}"
    )

    if (
        youtube_result
        and facebook_result
        and instagram_result
    ):

        state.update(
            {
                "completed_slot":
                    key,

                "completed_at_ist":
                    datetime
                    .now(IST)
                    .isoformat(),

                "completion_status":
                    "COMPLETE",

                "active_slot":
                    "",
            }
        )

        save_state(
            state
        )

        log(
            f"{key}: COMPLETE "
            "on YouTube + Facebook "
            "+ Instagram."
        )

        return True

    state.update(
        {
            "completion_status":
                "PARTIAL_RETRY_PENDING",

            "active_slot":
                key,
        }
    )

    save_state(
        state
    )

    log(
        f"{key}: PARTIAL; "
        "automatic retry "
        "remains active."
    )

    return False


# ============================================================
# SLOT PARSER
# ============================================================

def parse_slot_key(
    value: Any
) -> datetime | None:

    if not value:

        return None

    try:

        parsed = (
            datetime.strptime(
                str(
                    value
                ).strip(),
                "%Y-%m-%dT%H:%M",
            )
        )

        return parsed.replace(
            tzinfo=IST
        )

    except Exception:

        return None


# ============================================================
# SCHEDULED WORKER
# ============================================================

def worker() -> int:

    now = (
        datetime.now(
            IST
        )
    )

    (
        next_dt,
        next_slot,
        due
    ) = schedule_context(
        now
    )

    log(
        "Worker check. "
        f"Now="
        f"{now.strftime('%H:%M')} "
        f"next="
        f"{next_dt.strftime('%Y-%m-%d %H:%M')}"
    )

    # ========================================================
    # LOAD STATE
    # ========================================================

    state = (
        load_state()
    )

    prepared_key = str(
        state.get(
            "prepared_slot"
        )
        or ""
    ).strip()

    prepared_status = str(
        state.get(
            "prepare_status"
        )
        or ""
    ).strip().upper()

    completed_key = str(
        state.get(
            "completed_slot"
        )
        or ""
    ).strip()

    # ========================================================
    # OVERDUE SLOT RECOVERY
    # ========================================================

    if (
        prepared_key

        and

        prepared_key
        != completed_key
    ):

        prepared_dt = (
            parse_slot_key(
                prepared_key
            )
        )

        if (
            prepared_dt
            is not None

            and

            prepared_dt
            <= now
        ):

            if (
                prepared_status
                in {
                    "READY",
                    "FAILED",
                    "GEMINI_QUOTA_WAIT",
                    "RIGHTS_BLOCKED",
                    "PREPARING",
                    "REBUILD_REQUIRED",
                }
            ):

                log(
                    "RECOVERY PRIORITY: "
                    "overdue prepared slot "
                    f"{prepared_key} "
                    f"status="
                    f"{prepared_status}"
                )

                result = (
                    publish_slot(
                        prepared_dt
                    )
                )

                if result:

                    log(
                        "RECOVERY SUCCESS: "
                        f"{prepared_key}"
                    )

                    return 0

                log(
                    "RECOVERY FAILED: "
                    f"{prepared_key}"
                )

                return 2

    # ========================================================
    # PARTIAL PLATFORM RECOVERY
    # ========================================================

    state = (
        load_state()
    )

    active_key = str(
        state.get(
            "active_slot"
        )
        or ""
    ).strip()

    completion_status = str(
        state.get(
            "completion_status"
        )
        or ""
    ).strip().upper()

    if (
        active_key

        and

        completion_status
        ==
        "PARTIAL_RETRY_PENDING"
    ):

        active_dt = (
            parse_slot_key(
                active_key
            )
        )

        if (
            active_dt
            is None
        ):

            log(
                "RECOVERY WARNING: "
                "invalid active_slot "
                f"{active_key!r}; "
                "clearing malformed state."
            )

            state[
                "active_slot"
            ] = ""

            save_state(
                state
            )

            return 1

        log(
            "RECOVERY PRIORITY: "
            "unfinished slot "
            f"{active_key}; "
            "retrying failed "
            "platform branches."
        )

        result = (
            publish_slot(
                active_dt
            )
        )

        if result:

            log(
                "PARTIAL RECOVERY "
                "SUCCESS"
            )

            return 0

        log(
            "PARTIAL RECOVERY "
            "FAILED"
        )

        return 2

    # ========================================================
    # PUBLISH DUE SLOT
    # ========================================================

    if due:

        (
            due_dt,
            due_name
        ) = due

        log(
            "PUBLISH SLOT DUE: "
            f"{slot_key(due_dt)}"
        )

        result = (
            publish_slot(
                due_dt
            )
        )

        if result:

            log(
                "SCHEDULED "
                "PUBLICATION SUCCESS"
            )

            return 0

        log(
            "SCHEDULED "
            "PUBLICATION FAILED"
        )

        return 2

    # ========================================================
    # PREPARE NEXT SLOT
    # ========================================================

    prepare_time = (
        next_dt
        - timedelta(
            minutes=
                PREPARE_MINUTES_BEFORE
        )
    )

    if (
        now
        >= prepare_time
    ):

        log(
            "PREPARATION WINDOW OPEN: "
            f"{slot_key(next_dt)}"
        )

        result = (
            prepare_for(
                next_dt
            )
        )

        if result:

            log(
                "PREPARATION SUCCESS: "
                f"{slot_key(next_dt)}"
            )

            return 0

        log(
            "PREPARATION FAILED: "
            f"{slot_key(next_dt)}"
        )

        return 1

    # ========================================================
    # NOTHING DUE
    # ========================================================

    log(
        "Nothing due. "
        "Exit normally."
    )

    return 0


# ============================================================
# MANUAL IMMEDIATE TEST
# ============================================================

def run_now() -> int:

    now = (
        datetime.now(
            IST
        )
    )

    log(
        "RUN-NOW test requested."
    )

    synthetic = (
        now.replace(
            second=0,
            microsecond=0
        )
    )

    if not prepare_for(
        synthetic
    ):

        return 1

    if publish_slot(
        synthetic
    ):

        return 0

    return 2


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    parser = (
        argparse
        .ArgumentParser()
    )

    parser.add_argument(
        "--worker",
        action="store_true",
        help=(
            "Scheduled 5-minute "
            "worker."
        ),
    )

    parser.add_argument(
        "--run-now",
        action="store_true",
        help=(
            "Prepare and publish "
            "one story immediately."
        ),
    )

    args = (
        parser.parse_args()
    )

    if not acquire_lock():

        return 0

    try:

        try:

            if args.run_now:

                return run_now()

            return worker()

        except KeyboardInterrupt:

            log(
                "WORKER: console "
                "interrupt absorbed; "
                "durable state preserved "
                "for automatic recovery."
            )

            return 130

        except BaseException as error:

            log(
                "WORKER: top-level "
                "failure contained: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            return 1

    finally:

        release_lock()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    raise SystemExit(
        main()
    )