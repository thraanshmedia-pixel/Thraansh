"""
THRAANSH PERMANENT AUTOMATION WORKER V8.0 - SELF-HEALING 3-PLATFORM WORKER

Run this from Windows Task Scheduler every 5 minutes.

Behavior:
- Prepares the next story before the scheduled publication slot.
- Publishes at/after the slot.
- Retries temporary failures.
- Never intentionally republishes a platform already verified PUBLISHED.
- Keeps RIGHTS_PASS + V4 identity safety mandatory.
- Persists state so a Windows/Python crash can resume on the next invocation.
- Uses an OS-backed Windows file lock that is automatically released if Python crashes.
- Applies per-stage timeouts and kills hung child process trees.
- Recovers an overdue prepared slot even after the normal grace window.
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
except ImportError:  # non-Windows fallback
    msvcrt = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUEUE_FILE = PROJECT_ROOT / "data" / "article_queue.json"
STATE_FILE = PROJECT_ROOT / "data" / "automation_state_v7.json"
LOCK_FILE = PROJECT_ROOT / "data" / "thraansh_v7.lock"
LOG_DIR = PROJECT_ROOT / "logs"
IST = ZoneInfo("Asia/Kolkata")

SCHEDULE_SLOTS = ("07:00","09:00","11:00","13:00","15:00","17:00","19:00","21:00")
PREPARE_MINUTES_BEFORE = 45
PUBLISH_GRACE_MINUTES = 75
STAGE_ATTEMPTS = 3
STAGE_RETRY_SECONDS = (0, 20, 60)
PLATFORM_ATTEMPTS_PER_INVOCATION = 2
PLATFORM_RETRY_SECONDS = 30

# Hard upper bounds so one hung external process cannot hold the worker forever.
# Values are intentionally generous for normal production work.
STAGE_TIMEOUT_SECONDS = {
    "NEWS COLLECTION": 20 * 60,
    "PRODUCTION SELECTION": 5 * 60,
    "HINDI SCRIPT": 7 * 60,
    "HINDI VOICE": 12 * 60,
    "SCENE PLANNING": 10 * 60,
    "STORY FOOTAGE": 40 * 60,
    "FINAL VIDEO": 50 * 60,
    "RIGHTS CHECK": 10 * 60,
    "YOUTUBE": 30 * 60,
    "FACEBOOK": 30 * 60,
    "INSTAGRAM STORAGE": 30 * 60,
    "INSTAGRAM": 20 * 60,
}
DEFAULT_STAGE_TIMEOUT_SECONDS = 30 * 60

# Kept open for the lifetime of this worker. On Windows, the OS releases
# this lock automatically if the Python process crashes or is terminated.
_LOCK_HANDLE = None

CONTENT_STAGES = [
    ("NEWS COLLECTION", PROJECT_ROOT / "news" / "browser_collector.py"),
    ("PRODUCTION SELECTION", PROJECT_ROOT / "news" / "production_selector.py"),
    ("HINDI SCRIPT", PROJECT_ROOT / "scripts" / "hindi_presenter.py"),
    ("HINDI VOICE", PROJECT_ROOT / "voice" / "generator.py"),
    ("SCENE PLANNING", PROJECT_ROOT / "scripts" / "scene_planner.py"),
    ("STORY FOOTAGE", PROJECT_ROOT / "footage" / "multi_scene_generator.py"),
    ("FINAL VIDEO", PROJECT_ROOT / "video" / "multi_generator.py"),
    ("RIGHTS CHECK", PROJECT_ROOT / "copyright" / "rights_checker.py"),
]
YOUTUBE = ("YOUTUBE", PROJECT_ROOT / "youtube" / "uploader.py")
FACEBOOK = ("FACEBOOK", PROJECT_ROOT / "facebook" / "publisher.py")
IG_STORAGE = ("INSTAGRAM STORAGE", PROJECT_ROOT / "instagram" / "storage_uploader.py")
INSTAGRAM = ("INSTAGRAM", PROJECT_ROOT / "instagram" / "publisher.py")

def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp} IST] {msg}"
    print(line, flush=True)
    with (LOG_DIR / "automation_v7.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def articles() -> list[dict]:
    data = load_json(QUEUE_FILE, [])
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for k in ("articles","items","queue","news","data"):
            if isinstance(data.get(k), list):
                return [x for x in data[k] if isinstance(x, dict)]
    raise RuntimeError("Could not locate article list.")

def current_article() -> dict:
    selected = [a for a in articles() if a.get("production_selected") is True]
    if not selected:
        raise RuntimeError("No production_selected article.")
    return selected[-1]

def gemini_quota_wait() -> tuple[bool, str]:
    """
    Read the durable quota cooldown written by scripts/hindi_presenter.py.
    When active, the worker must not invoke the Hindi presenter again.
    """
    try:
        a = current_article()
    except Exception:
        return False, ""

    if str(a.get("status") or "").strip().upper() != "HINDI_SCRIPT_QUOTA_WAIT":
        return False, ""

    raw = str(a.get("gemini_retry_not_before") or "").strip()
    if not raw:
        return False, ""

    try:
        retry_at = datetime.fromisoformat(raw)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=IST)
        retry_at = retry_at.astimezone(IST)
    except Exception:
        return False, ""

    if datetime.now(IST) < retry_at:
        return True, retry_at.isoformat()

    return False, retry_at.isoformat()


def resolve_path(v: Any) -> Path | None:
    if not v:
        return None
    p = Path(str(v))
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p.resolve()

def identity_gate(article: dict) -> tuple[bool,str]:
    if str(article.get("media_generator_version") or "") != "FAST_MULTI_SOURCE_IDENTITY_SAFE_V4":
        return False, "media_generator_version is not identity-safe V4."
    scenes = article.get("scene_plan")
    if not isinstance(scenes, list) or not scenes:
        return False, "No scene_plan."
    for i, s in enumerate(scenes, 1):
        if s.get("visual_identity_safe") is not True:
            return False, f"Scene {i}: visual_identity_safe is not True."
        mode = str(s.get("visual_usage_mode") or "").strip().upper()
        method = str(s.get("identity_verification_method") or "").strip().upper()
        subject = str(s.get("identity_subject") or "").strip()
        source = str(s.get("media_source") or "").strip().upper()
        if mode == "CONTEXTUAL_MEDIA":
            if method != "NOT_IDENTITY_MEDIA" or subject:
                return False, f"Scene {i}: invalid contextual identity metadata."
        elif mode == "EXACT_PERSON_VERIFIED_METADATA":
            if source != "WIKIMEDIA" or not subject or method != "WIKIMEDIA_NAME_METADATA_MATCH":
                return False, f"Scene {i}: invalid exact-person verification metadata."
        else:
            return False, f"Scene {i}: unsupported visual_usage_mode {mode!r}."
    return True, f"{len(scenes)} scenes identity-safe."

def rights_gate() -> tuple[bool,str]:
    try:
        a = current_article()
    except Exception as e:
        return False, str(e)
    if str(a.get("status") or "").upper() != "RIGHTS_PASS":
        return False, "Article status is not RIGHTS_PASS."
    if str(a.get("rights_status") or "").upper() != "RIGHTS_PASS":
        return False, "rights_status is not RIGHTS_PASS."
    manifest = resolve_path(a.get("rights_manifest_file"))
    video = resolve_path(a.get("final_video_file"))
    if not manifest or not manifest.is_file():
        return False, "Rights manifest missing."
    if not video or not video.is_file() or video.suffix.lower() != ".mp4" or video.stat().st_size <= 0:
        return False, "Exact final MP4 missing/invalid."
    ok, msg = identity_gate(a)
    if not ok:
        return False, msg
    return True, "RIGHTS_PASS + manifest + exact MP4 + V4 identity safety confirmed."

def youtube_ok(a: dict) -> bool:
    return bool(str(a.get("youtube_video_id") or "").strip()) and str(a.get("youtube_upload_status") or "").upper() == "PUBLISHED"

def facebook_ok(a: dict) -> bool:
    return bool(str(a.get("facebook_video_id") or "").strip()) and str(a.get("facebook_upload_status") or "").upper() == "PUBLISHED"

def instagram_ok(a: dict) -> bool:
    return bool(str(a.get("instagram_media_id") or "").strip()) and str(a.get("instagram_publish_status") or "").upper() == "PUBLISHED"

def instagram_storage_ok(a: dict) -> bool:
    return (str(a.get("instagram_storage_status") or "").upper() == "UPLOADED"
            and str(a.get("instagram_video_url") or "").startswith("https://"))

def _terminate_process_tree(proc: subprocess.Popen) -> None:
    """Best-effort termination of a hung stage and all descendants."""
    if proc.poll() is not None:
        return

    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
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


def run_once(name: str, script: Path) -> bool:
    if not script.is_file():
        log(f"{name}: script missing: {script}")
        return False

    timeout_seconds = STAGE_TIMEOUT_SECONDS.get(
        name,
        DEFAULT_STAGE_TIMEOUT_SECONDS,
    )

    log(f"{name}: START (timeout={timeout_seconds // 60}m)")
    proc = None

    try:
        creationflags = 0
        if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        proc = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(PROJECT_ROOT),
            creationflags=creationflags,
            stdin=subprocess.DEVNULL,
        )

        try:
            returncode = proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            log(
                f"{name}: TIMEOUT after {timeout_seconds // 60}m; "
                "terminating hung process tree."
            )
            _terminate_process_tree(proc)
            try:
                proc.wait(timeout=30)
            except Exception:
                pass
            return False

        if returncode == 0:
            log(f"{name}: OK")
            return True

        log(f"{name}: FAILED exit={returncode}")
        return False

    except KeyboardInterrupt:
        # Never let a console Ctrl+C kill the permanent scheduler worker.
        # The child may already have completed/persisted publication state.
        log(f"{name}: console interrupt ignored; preserving child and re-checking durable state.")
        if proc is not None:
            try:
                returncode = proc.wait(timeout=30)
                if returncode == 0:
                    log(f"{name}: OK after interrupt")
                    return True
            except Exception:
                pass
        return False

    except Exception as e:
        if proc is not None:
            _terminate_process_tree(proc)
        log(f"{name}: EXCEPTION {e}")
        return False

def run_with_retry(name: str, script: Path, attempts: int = STAGE_ATTEMPTS) -> bool:
    for attempt in range(1, attempts + 1):
        if attempt > 1:
            delay = STAGE_RETRY_SECONDS[min(attempt-1, len(STAGE_RETRY_SECONDS)-1)]
            log(f"{name}: retry {attempt}/{attempts} after {delay}s")
            time.sleep(delay)
        if run_once(name, script):
            return True
    return False

def acquire_lock() -> bool:
    """
    Acquire a crash-safe single-worker lock.

    Windows:
      msvcrt locks one byte of the file. The OS releases that lock
      automatically when the process exits/crashes, so a stale JSON file
      can never deadlock future workers.

    Non-Windows fallback:
      exclusive file creation with stale-PID cleanup.
    """
    global _LOCK_HANDLE
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    if msvcrt is not None and os.name == "nt":
        handle = LOCK_FILE.open("a+", encoding="utf-8")

        # msvcrt.locking needs a lockable byte.
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(" ")
            handle.flush()

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            handle.close()
            log("Another V7 worker is genuinely running; exiting safely.")
            return False

        _LOCK_HANDLE = handle

        # Byte 0 remains the lock byte. Metadata starts at byte 1.
        handle.seek(1)
        handle.truncate()
        handle.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "started": datetime.now(IST).isoformat(),
                    "lock_type": "WINDOWS_OS_FILE_LOCK",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass

        log(f"Worker lock acquired by PID {os.getpid()} (crash-safe OS lock).")
        return True

    # Fallback for non-Windows development/testing.
    payload = json.dumps(
        {"pid": os.getpid(), "started": datetime.now(IST).isoformat()},
        ensure_ascii=False,
        indent=2,
    )
    try:
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        log("Another V7 worker appears to be running; exiting safely.")
        return False

    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)

    return True


def release_lock() -> None:
    global _LOCK_HANDLE

    if _LOCK_HANDLE is not None:
        try:
            _LOCK_HANDLE.seek(0)
            msvcrt.locking(_LOCK_HANDLE.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
        try:
            _LOCK_HANDLE.close()
        except Exception:
            pass
        _LOCK_HANDLE = None
        return

    # Non-Windows fallback owns the file itself.
    if msvcrt is None or os.name != "nt":
        try:
            LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            pass

def slot_dt(day, slot: str) -> datetime:
    h,m = map(int, slot.split(":"))
    return datetime(day.year, day.month, day.day, h, m, tzinfo=IST)

def schedule_context(now: datetime):
    candidates = []
    for day_delta in (-1,0,1):
        d = (now + timedelta(days=day_delta)).date()
        for s in SCHEDULE_SLOTS:
            dt = slot_dt(d, s)
            candidates.append((dt, s))
    next_dt, next_s = min((x for x in candidates if x[0] > now), key=lambda x:x[0])
    due = [(dt,s) for dt,s in candidates if dt <= now <= dt + timedelta(minutes=PUBLISH_GRACE_MINUTES)]
    due_item = max(due, key=lambda x:x[0]) if due else None
    return next_dt, next_s, due_item

def slot_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")

def load_state() -> dict:
    return load_json(STATE_FILE, {})

def save_state(s: dict) -> None:
    s["updated_at_ist"] = datetime.now(IST).isoformat()
    atomic_json(STATE_FILE, s)

def prepare_for(slot_time: datetime) -> bool:
    key = slot_key(slot_time)
    state = load_state()
    if state.get("prepared_slot") == key:
        ok,msg = rights_gate()
        if ok:
            log(f"{key}: already prepared; {msg}")
            return True
        log(f"{key}: prior prepared state invalid; rebuilding.")

    log(f"PREPARING story for slot {key}")
    for name, script in CONTENT_STAGES:
        # V7.3 FREE-TIER RULE:
        # The presenter writes HINDI_SCRIPT_QUOTA_WAIT +
        # gemini_retry_not_before after a Gemini quota error.
        # Do not invoke Gemini again every five minutes while that cooldown
        # is active. Other content stages retain the existing retry policy.
        if name == "HINDI SCRIPT":
            waiting, retry_at = gemini_quota_wait()
            if waiting:
                state.update({
                    "prepared_slot": key,
                    "prepare_status": "GEMINI_QUOTA_WAIT",
                    "failed_stage": "HINDI SCRIPT",
                    "gemini_retry_not_before": retry_at,
                })
                save_state(state)
                log(
                    f"HINDI SCRIPT: Gemini free-tier quota cooldown active; "
                    f"no API call made. Retry not before {retry_at}."
                )
                return False

            ok = run_once(name, script)
        else:
            ok = run_with_retry(name, script)

        if not ok:
            # Re-read the queue because the presenter may just have written
            # a new quota cooldown during this invocation.
            if name == "HINDI SCRIPT":
                waiting, retry_at = gemini_quota_wait()
                if waiting:
                    state.update({
                        "prepared_slot": key,
                        "prepare_status": "GEMINI_QUOTA_WAIT",
                        "failed_stage": "HINDI SCRIPT",
                        "gemini_retry_not_before": retry_at,
                    })
                    save_state(state)
                    log(
                        f"PREPARATION PAUSED at HINDI SCRIPT: Gemini free-tier "
                        f"quota cooldown until {retry_at}. "
                        f"Next 5-minute workers will not call Gemini before then."
                    )
                    return False

            state.update({
                "prepared_slot": key,
                "prepare_status": "FAILED",
                "failed_stage": name,
            })
            save_state(state)
            log(
                f"PREPARATION FAILED at {name}; "
                f"next worker invocation will recover."
            )
            return False

    ok,msg = rights_gate()
    if not ok:
        state.update({"prepared_slot": key, "prepare_status":"RIGHTS_BLOCKED", "failed_stage":"RIGHTS GATE"})
        save_state(state)
        log(f"PREPARATION BLOCKED: {msg}")
        return False

    a = current_article()
    state.update({
        "prepared_slot": key,
        "prepare_status":"READY",
        "prepared_title": str(a.get("title") or ""),
        "prepared_video": str(a.get("final_video_file") or ""),
        "prepared_at_ist": datetime.now(IST).isoformat(),
    })
    save_state(state)
    log(f"READY for {key}: {a.get('title')}")
    return True

def platform_retry(name: str, script: Path, verifier) -> bool:
    a = current_article()
    if verifier(a):
        log(f"{name}: already PUBLISHED; skip duplicate.")
        return True
    for attempt in range(1, PLATFORM_ATTEMPTS_PER_INVOCATION + 1):
        if attempt > 1:
            log(f"{name}: retry after {PLATFORM_RETRY_SECONDS}s")
            time.sleep(PLATFORM_RETRY_SECONDS)
        run_once(name, script)
        a = current_article()
        if verifier(a):
            log(f"{name}: VERIFIED PUBLISHED")
            return True
    log(f"{name}: still not published; next 5-minute worker run will retry.")
    return False

def publish_slot(slot_time: datetime) -> bool:
    key = slot_key(slot_time)
    state = load_state()

    if state.get("completed_slot") == key:
        log(f"{key}: already COMPLETE.")
        return True

    if state.get("prepared_slot") != key or state.get("prepare_status") != "READY":
        log(f"{key}: no READY package; preparing now (publication may be late).")
        if not prepare_for(slot_time):
            return False
        state = load_state()

    ok,msg = rights_gate()
    if not ok:
        log(f"PUBLISH BLOCKED: {msg}")
        return False

    a = current_article()
    if state.get("prepared_title") and state.get("prepared_title") != str(a.get("title") or ""):
        log("PUBLISH BLOCKED: current article differs from prepared article.")
        return False

    yt = platform_retry(*YOUTUBE, youtube_ok)
    fb = platform_retry(*FACEBOOK, facebook_ok)

    a = current_article()
    if not instagram_storage_ok(a):
        run_with_retry(*IG_STORAGE, attempts=2)
    ig = platform_retry(*INSTAGRAM, instagram_ok)

    # IMPORTANT:
    # Re-read article_queue.json after every publisher has finished.
    # A publisher can successfully save its PUBLISHED result even when an
    # earlier in-memory return value was false/stale. The queue is the durable
    # source of truth for completion and duplicate protection.
    final_article = current_article()
    yt = youtube_ok(final_article)
    fb = facebook_ok(final_article)
    ig = instagram_ok(final_article)

    log(
        "FINAL PLATFORM STATE: "
        f"YouTube={'PUBLISHED' if yt else 'PENDING'} | "
        f"Facebook={'PUBLISHED' if fb else 'PENDING'} | "
        f"Instagram={'PUBLISHED' if ig else 'PENDING'}"
    )

    if yt and fb and ig:
        state.update({
            "completed_slot": key,
            "completed_at_ist": datetime.now(IST).isoformat(),
            "completion_status":"COMPLETE",
            "active_slot": "",
        })
        save_state(state)
        log(f"{key}: COMPLETE on YouTube + Facebook + Instagram.")
        return True

    state.update({"completion_status":"PARTIAL_RETRY_PENDING", "active_slot":key})
    save_state(state)
    log(f"{key}: PARTIAL; automatic retry remains active.")
    return False

def parse_slot_key(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(
            str(value).strip(),
            "%Y-%m-%dT%H:%M",
        )
        return parsed.replace(tzinfo=IST)
    except Exception:
        return None


def worker() -> int:
    now = datetime.now(IST)
    next_dt, next_s, due = schedule_context(now)
    log(f"Worker check. Now={now.strftime('%H:%M')} next={next_dt.strftime('%Y-%m-%d %H:%M')}")

    # V7.4 OVERDUE PREPARED-SLOT RECOVERY:
    # If Windows skipped task invocations, never abandon a package merely
    # because the 75-minute grace window has passed. Finish the already
    # prepared/paused slot before selecting new work.
    state = load_state()
    prepared_key = str(state.get("prepared_slot") or "").strip()
    prepared_status = str(state.get("prepare_status") or "").strip().upper()
    completed_key = str(state.get("completed_slot") or "").strip()

    if prepared_key and prepared_key != completed_key:
        prepared_dt = parse_slot_key(prepared_key)
        if prepared_dt is not None and prepared_dt <= now:
            if prepared_status in {
                "READY",
                "FAILED",
                "GEMINI_QUOTA_WAIT",
                "RIGHTS_BLOCKED",
            }:
                log(
                    f"RECOVERY PRIORITY: overdue prepared slot {prepared_key} "
                    f"status={prepared_status}; resuming it before new work."
                )
                publish_slot(prepared_dt)
                return 0

    # V7.2 RECOVERY RULE:
    # A PARTIAL slot remains the highest priority even after the normal
    # publication grace window expires. This prevents a temporary external
    # API outage from silently abandoning an already-prepared story.
    state = load_state()
    active_key = str(state.get("active_slot") or "").strip()
    completion_status = str(state.get("completion_status") or "").strip().upper()

    if active_key and completion_status == "PARTIAL_RETRY_PENDING":
        active_dt = parse_slot_key(active_key)

        if active_dt is None:
            log(
                f"RECOVERY WARNING: invalid active_slot {active_key!r}; "
                "clearing malformed recovery state."
            )
            state["active_slot"] = ""
            save_state(state)
        else:
            log(
                f"RECOVERY PRIORITY: unfinished slot {active_key}; "
                "retrying failed platform branches before new work."
            )
            publish_slot(active_dt)
            return 0

    if due:
        due_dt,_ = due
        publish_slot(due_dt)
        return 0

    if now >= next_dt - timedelta(minutes=PREPARE_MINUTES_BEFORE):
        prepare_for(next_dt)
        return 0

    log("Nothing due. Exit normally.")
    return 0

def run_now() -> int:
    now = datetime.now(IST)
    log("RUN-NOW test requested.")
    # Use a synthetic current-time slot so prepare+publish happen immediately.
    synthetic = now.replace(second=0, microsecond=0)
    if not prepare_for(synthetic):
        return 1
    return 0 if publish_slot(synthetic) else 2

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true", help="Scheduled 5-minute worker.")
    parser.add_argument("--run-now", action="store_true", help="Prepare and publish one story immediately.")
    args = parser.parse_args()

    if not acquire_lock():
        return 0
    try:
        try:
            return run_now() if args.run_now else worker()
        except KeyboardInterrupt:
            # Scheduled automation must never die just because an interactive
            # console receives Ctrl+C. Durable queue state remains authoritative;
            # the next invocation resumes only unfinished platform branches.
            log("WORKER: console interrupt absorbed; durable state preserved for automatic recovery.")
            return 0
        except BaseException as exc:
            # Last-resort containment: persist a diagnostic instead of leaving
            # Task Scheduler with a permanently wedged worker. SystemExit is
            # converted to an ordinary task result; OS-level termination cannot
            # be caught and is handled by the crash-safe OS lock next invocation.
            log(f"WORKER: top-level failure contained: {type(exc).__name__}: {exc}")
            return 1
    finally:
        release_lock()

if __name__ == "__main__":
    raise SystemExit(main())
