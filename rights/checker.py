import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime


# ============================================================
# THRAANSH LIMITED AUTOMATION ENGINE
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

# IMPORTANT:
# Maximum videos generated during one automation run
MAX_VIDEOS_PER_RUN = 2

# Safety protection
MAX_WORKFLOW_CYCLES = 10


# ============================================================
# COLLECTOR
# ============================================================

COLLECTOR = {
    "name": "News Collector",
    "file": PROJECT_FOLDER / "news" / "collector.py"
}


# ============================================================
# VIDEO PIPELINE
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
    "VIDEO_FAILED"
}


# ============================================================
# LOG
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
# ARTICLE COMPLETE
# ============================================================

def article_is_complete(article):

    status = article.get("status")

    rights_status = article.get(
        "rights_status"
    )

    video_file = article.get(
        "final_video_file"
    )

    return (
        status == "VIDEO_READY"
        and bool(video_file)
        and rights_status in [
            "REVIEWED",
            "REVIEWED_WITH_WARNINGS"
        ]
    )


# ============================================================
# COUNT COMPLETED VIDEOS
# ============================================================

def count_completed_videos():

    queue = load_queue()

    count = 0

    for article in queue:

        if article_is_complete(article):
            count += 1

    return count


# ============================================================
# COUNT PENDING
# ============================================================

def count_pending_articles():

    queue = load_queue()

    pending = 0

    for article in queue:

        status = article.get(
            "status",
            "UNKNOWN"
        )

        if article_is_complete(article):
            continue

        if status in FAILURE_STATUSES:
            continue

        pending += 1

    return pending


# ============================================================
# RUN ONE SCRIPT
# ============================================================

def run_script(stage):

    stage_name = stage["name"]
    stage_file = stage["file"]

    if not stage_file.exists():

        log(
            f"ERROR: Missing stage file: "
            f"{stage_file}"
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
# RUN WITH RETRIES
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

        if run_script(stage):

            log(
                f"{stage_name} finished."
            )

            return True

        if attempt < MAX_STAGE_RETRIES:

            log(
                f"Retrying in "
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
# RUN ONE VIDEO PIPELINE
# ============================================================

def run_one_video_cycle():

    for stage in PIPELINE_STAGES:

        success = run_stage_with_retry(
            stage
        )

        if not success:

            return False

    return True


# ============================================================
# MAIN
# ============================================================

def main():

    log("")
    log("=" * 70)

    log(
        "THRAANSH AUTOMATION ENGINE STARTED"
    )

    log("=" * 70)

    # --------------------------------------------------------
    # COLLECT NEWS
    # --------------------------------------------------------

    log(
        "Checking latest news..."
    )

    if not run_stage_with_retry(
        COLLECTOR
    ):

        log(
            "News collection failed."
        )

        return


    # --------------------------------------------------------
    # BASELINE COMPLETED COUNT
    # --------------------------------------------------------

    completed_before = (
        count_completed_videos()
    )

    log(
        f"Videos already completed before run: "
        f"{completed_before}"
    )

    generated_this_run = 0


    # --------------------------------------------------------
    # PROCESS MAXIMUM 2 VIDEOS
    # --------------------------------------------------------

    for cycle in range(
        1,
        MAX_WORKFLOW_CYCLES + 1
    ):

        if generated_this_run >= MAX_VIDEOS_PER_RUN:

            log(
                "Maximum videos for this run reached."
            )

            break

        pending = count_pending_articles()

        if pending == 0:

            log(
                "No pending articles remain."
            )

            break

        log(
            "=" * 70
        )

        log(
            f"VIDEO CYCLE {cycle}"
        )

        log(
            f"Pending articles: {pending}"
        )

        log(
            f"Videos generated this run: "
            f"{generated_this_run}/"
            f"{MAX_VIDEOS_PER_RUN}"
        )

        completed_before_cycle = (
            count_completed_videos()
        )

        success = run_one_video_cycle()

        if not success:

            log(
                "Video cycle stopped due "
                "to stage failure."
            )

            break

        completed_after_cycle = (
            count_completed_videos()
        )

        newly_completed = (
            completed_after_cycle
            - completed_before_cycle
        )

        if newly_completed > 0:

            generated_this_run += (
                newly_completed
            )

            log(
                f"New video completed. "
                f"Total this run: "
                f"{generated_this_run}"
            )

        else:

            log(
                "WARNING: No new video was "
                "completed during this cycle."
            )

            log(
                "Stopping to avoid an endless loop."
            )

            break


    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    pending_final = (
        count_pending_articles()
    )

    completed_final = (
        count_completed_videos()
    )

    log("=" * 70)

    log(
        "THRAANSH RUN SUMMARY"
    )

    log(
        f"Videos generated this run: "
        f"{generated_this_run}"
    )

    log(
        f"Total completed videos: "
        f"{completed_final}"
    )

    log(
        f"Pending articles remaining: "
        f"{pending_final}"
    )

    log("=" * 70)

    if generated_this_run == MAX_VIDEOS_PER_RUN:

        log(
            "Daily video limit reached successfully."
        )

    elif pending_final == 0:

        log(
            "Queue completed."
        )

    else:

        log(
            "Automation stopped before "
            "reaching the video limit."
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()