import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime


# ============================================================
# THRAANSH AUTOMATION ENGINE
# ============================================================

PROJECT_FOLDER = Path(__file__).resolve().parent

PYTHON_EXE = sys.executable

DATA_FOLDER = PROJECT_FOLDER / "data"
QUEUE_FILE = DATA_FOLDER / "article_queue.json"

LOG_FOLDER = PROJECT_FOLDER / "logs"
LOG_FOLDER.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_FOLDER / "thraansh_automation.log"


# ============================================================
# SETTINGS
# ============================================================

MAX_STAGE_RETRIES = 3
RETRY_DELAY_SECONDS = 10

# One video per scheduled run
MAX_VIDEOS_PER_RUN = 1

# Safety protection against endless loops
MAX_WORKFLOW_CYCLES = 5


# ============================================================
# NEWS COLLECTOR
# ============================================================

COLLECTOR = {
    "name": "News Collector",
    "file": PROJECT_FOLDER / "news" / "collector.py"
}


# ============================================================
# COMPLETE THRAANSH PIPELINE
# ============================================================

PIPELINE_STAGES = [

    {
        "name": "Content Processor",
        "file": PROJECT_FOLDER / "content" / "processor.py"
    },

    {
        "name": "Script Generator",
        "file": PROJECT_FOLDER / "scripts" / "generator.py"
    },

    {
        "name": "Voice Generator",
        "file": PROJECT_FOLDER / "voice" / "generator.py"
    },

    {
        "name": "Scene Planner",
        "file": PROJECT_FOLDER / "scripts" / "scene_planner.py"
    },

    {
        "name": "Smart Footage Generator",
        "file": PROJECT_FOLDER / "footage" / "smart_generator.py"
    },

    {
        "name": "Smart Video Renderer",
        "file": PROJECT_FOLDER / "video" / "smart_renderer.py"
    },

    {
        "name": "Media Rights Checker",
        "file": PROJECT_FOLDER / "rights" / "checker.py"
    },

    {
        "name": "YouTube Publisher",
        "file": PROJECT_FOLDER / "publishing" / "youtube_uploader.py"
    }
]


# ============================================================
# FAILURE STATUSES
# ============================================================

FAILURE_STATUSES = {
    "VOICE_FAILED",
    "MEDIA_FAILED",
    "SCENES_FAILED",
    "FOOTAGE_FAILED",
    "VIDEO_FAILED",
    "YOUTUBE_FAILED"
}


# ============================================================
# LOGGING
# ============================================================

def log(message):

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    text = f"[{timestamp}] {message}"

    print(text)

    with open(
        LOG_FILE,
        "a",
        encoding="utf-8"
    ) as file:

        file.write(text + "\n")


# ============================================================
# LOAD QUEUE
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

            return json.load(file)

    except Exception as error:

        log(
            f"ERROR reading article queue: {error}"
        )

        return []


# ============================================================
# CHECK WHETHER YOUTUBE PUBLISHING IS COMPLETE
# ============================================================

def article_is_published(article):

    return (
        article.get("youtube_upload_status") == "PUBLISHED"
        and bool(article.get("youtube_video_id"))
    )


# ============================================================
# COUNT PUBLISHED VIDEOS
# ============================================================

def count_published_videos():

    queue = load_queue()

    total = 0

    for article in queue:

        if article_is_published(article):
            total += 1

    return total


# ============================================================
# CHECK WHETHER ARTICLE IS STILL PENDING
# ============================================================

def article_is_pending(article):

    if article_is_published(article):
        return False

    status = article.get(
        "status",
        "UNKNOWN"
    )

    if status in FAILURE_STATUSES:
        return False

    return True


# ============================================================
# COUNT PENDING ARTICLES
# ============================================================

def count_pending_articles():

    queue = load_queue()

    total = 0

    for article in queue:

        if article_is_pending(article):
            total += 1

    return total


# ============================================================
# RUN ONE SCRIPT
# ============================================================

def run_script(stage):

    stage_name = stage["name"]
    stage_file = stage["file"]

    if not stage_file.exists():

        log(
            f"ERROR: Missing stage file: {stage_file}"
        )

        return False

    try:

        result = subprocess.run(
            [
                PYTHON_EXE,
                str(stage_file)
            ],

            cwd=str(PROJECT_FOLDER),

            capture_output=True,

            text=True
        )

        if result.stdout:

            for line in result.stdout.splitlines():

                if line.strip():

                    log(
                        f"{stage_name}: {line}"
                    )

        if result.returncode != 0:

            log(
                f"{stage_name} exited with "
                f"code {result.returncode}"
            )

            if result.stderr:

                for line in result.stderr.splitlines():

                    if line.strip():

                        log(
                            f"{stage_name} ERROR: {line}"
                        )

            return False

        return True

    except Exception as error:

        log(
            f"{stage_name} exception: {error}"
        )

        return False


# ============================================================
# RUN STAGE WITH RETRIES
# ============================================================

def run_stage_with_retry(stage):

    stage_name = stage["name"]

    for attempt in range(
        1,
        MAX_STAGE_RETRIES + 1
    ):

        log(
            f"Running {stage_name} "
            f"(attempt {attempt}/{MAX_STAGE_RETRIES})"
        )

        success = run_script(
            stage
        )

        if success:

            log(
                f"{stage_name} finished successfully."
            )

            return True

        if attempt < MAX_STAGE_RETRIES:

            log(
                f"Retrying {stage_name} in "
                f"{RETRY_DELAY_SECONDS} seconds..."
            )

            time.sleep(
                RETRY_DELAY_SECONDS
            )

    log(
        f"{stage_name} failed after "
        f"{MAX_STAGE_RETRIES} attempts."
    )

    return False


# ============================================================
# RUN ONE COMPLETE VIDEO + YOUTUBE CYCLE
# ============================================================

def run_one_cycle():

    for stage in PIPELINE_STAGES:

        success = run_stage_with_retry(
            stage
        )

        if not success:

            log(
                f"Cycle stopped at "
                f"{stage['name']}."
            )

            return False

    return True


# ============================================================
# MAIN AUTOMATION
# ============================================================

def main():

    log("")
    log("=" * 70)

    log(
        "THRAANSH AUTOMATION ENGINE STARTED"
    )

    log("=" * 70)


    # --------------------------------------------------------
    # STEP 1: CHECK LATEST NEWS
    # --------------------------------------------------------

    log(
        "Checking latest news..."
    )

    collector_success = run_stage_with_retry(
        COLLECTOR
    )

    if not collector_success:

        log(
            "News collection failed."
        )

        return


    # --------------------------------------------------------
    # STEP 2: BASELINE YOUTUBE COUNT
    # --------------------------------------------------------

    published_before_run = (
        count_published_videos()
    )

    published_this_run = 0


    # --------------------------------------------------------
    # STEP 3: GENERATE + PUBLISH MAXIMUM ONE VIDEO
    # --------------------------------------------------------

    for cycle in range(
        1,
        MAX_WORKFLOW_CYCLES + 1
    ):

        if published_this_run >= MAX_VIDEOS_PER_RUN:

            log(
                "Maximum videos for this run reached."
            )

            break

        pending = count_pending_articles()

        if pending == 0:

            log(
                "No pending articles available."
            )

            break

        log("=" * 70)

        log(
            f"THRAANSH VIDEO CYCLE {cycle}"
        )

        log(
            f"Pending articles: {pending}"
        )

        published_before_cycle = (
            count_published_videos()
        )

        cycle_success = run_one_cycle()

        if not cycle_success:

            log(
                "Automation cycle stopped "
                "because a stage failed."
            )

            break

        published_after_cycle = (
            count_published_videos()
        )

        newly_published = (
            published_after_cycle
            - published_before_cycle
        )

        if newly_published > 0:

            published_this_run += (
                newly_published
            )

            log(
                f"YouTube video published successfully."
            )

            log(
                f"Videos published this run: "
                f"{published_this_run}"
            )

        else:

            log(
                "WARNING: Pipeline finished but "
                "no new YouTube video was published."
            )

            log(
                "Stopping to prevent an endless loop."
            )

            break


    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    total_published = (
        count_published_videos()
    )

    pending_final = (
        count_pending_articles()
    )

    log("=" * 70)

    log(
        "THRAANSH RUN SUMMARY"
    )

    log(
        f"YouTube videos published this run: "
        f"{published_this_run}"
    )

    log(
        f"Total YouTube videos published: "
        f"{total_published}"
    )

    log(
        f"Pending articles remaining: "
        f"{pending_final}"
    )

    log("=" * 70)

    if published_this_run >= 1:

        log(
            "THRAANSH VIDEO GENERATED "
            "AND PUBLISHED TO YOUTUBE ✓"
        )

    elif pending_final == 0:

        log(
            "No pending content was available."
        )

    else:

        log(
            "Automation ended without "
            "a new YouTube publication."
        )

    log("=" * 70)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()