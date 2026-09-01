import json
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# ============================================================
# THRAANSH WORKFLOW CONTROL API
# ============================================================

PROJECT_FOLDER = Path(__file__).resolve().parents[1]

PYTHON_EXE = sys.executable

DATA_FOLDER = PROJECT_FOLDER / "data"
LOG_FOLDER = PROJECT_FOLDER / "logs"
FINAL_VIDEO_FOLDER = PROJECT_FOLDER / "final_videos"
PUBLISHING_FOLDER = PROJECT_FOLDER / "publishing"

QUEUE_FILE = DATA_FOLDER / "article_queue.json"
AUTOMATION_LOG_FILE = LOG_FOLDER / "thraansh_automation.log"
EXECUTION_FILE = LOG_FOLDER / "api_executions.json"
SCHEDULE_FILE = DATA_FOLDER / "dashboard_schedule.json"

LOG_FOLDER.mkdir(parents=True, exist_ok=True)
DATA_FOLDER.mkdir(parents=True, exist_ok=True)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="THRAANSH Workflow Control API",
    version="2.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# GLOBAL EXECUTION LOCK
# ============================================================

automation_lock = threading.Lock()

runtime_state = {
    "running": False,
    "current_node": None,
    "current_execution_id": None,
    "started_at": None,
    "last_error": None,
}


# ============================================================
# NODE MAP
# ============================================================

NODE_MAP = {

    "news": {
        "name": "News Collector",
        "file": PROJECT_FOLDER / "news" / "collector.py",
    },

    "processor": {
        "name": "Content Processor",
        "file": PROJECT_FOLDER / "content" / "processor.py",
    },

    "script": {
        "name": "Script Generator",
        "file": PROJECT_FOLDER / "scripts" / "generator.py",
    },

    "voice": {
        "name": "Voice Generator",
        "file": PROJECT_FOLDER / "voice" / "generator.py",
    },

    "sceneplanner": {
        "name": "Scene Planner",
        "file": PROJECT_FOLDER / "scripts" / "scene_planner.py",
    },

    "footage": {
        "name": "Smart Footage Generator",
        "file": PROJECT_FOLDER / "footage" / "smart_generator.py",
    },

    "renderer": {
        "name": "Video Renderer",
        "file": PROJECT_FOLDER / "video" / "smart_renderer.py",
    },

    "rights": {
        "name": "Rights Checker",
        "file": PROJECT_FOLDER / "rights" / "checker.py",
    },

    "youtube": {
        "name": "YouTube Publisher",
        "file": PROJECT_FOLDER / "publishing" / "youtube_uploader.py",
    },

}


# ============================================================
# DASHBOARD-ONLY NODES
# ============================================================

VIRTUAL_NODES = {

    "scheduler": {
        "name": "Scheduler",
        "type": "trigger",
    },

    "queue": {
        "name": "Article Queue / Data",
        "type": "storage",
    },

    "logs": {
        "name": "Logs",
        "type": "monitoring",
    },

    "pexels": {
        "name": "Pexels API",
        "type": "service",
    },

    "ffmpeg": {
        "name": "FFmpeg Engine",
        "type": "service",
    },

    "publish": {
        "name": "Publishing Hub",
        "type": "router",
    },

    "x": {
        "name": "X",
        "type": "publisher",
    },

    "meta": {
        "name": "Meta API",
        "type": "publisher",
    },

    "facebook": {
        "name": "Facebook",
        "type": "publisher",
    },

    "instagram": {
        "name": "Instagram",
        "type": "publisher",
    },

}


# ============================================================
# Pydantic MODELS
# ============================================================

class ScheduleUpdate(BaseModel):
    times: list[str]


# ============================================================
# JSON HELPERS
# ============================================================

def read_json(file_path, default):

    if not file_path.exists():
        return default

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except Exception:

        return default


def write_json(file_path, data):

    with open(
        file_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# QUEUE
# ============================================================

def load_queue():

    return read_json(
        QUEUE_FILE,
        [],
    )


def save_queue(queue):

    write_json(
        QUEUE_FILE,
        queue,
    )


# ============================================================
# EXECUTIONS
# ============================================================

def load_executions():

    return read_json(
        EXECUTION_FILE,
        [],
    )


def save_executions(executions):

    write_json(
        EXECUTION_FILE,
        executions,
    )


def create_execution(
    execution_type,
    node_id=None,
):

    executions = load_executions()

    execution = {
        "id": str(uuid.uuid4()),
        "type": execution_type,
        "node_id": node_id,
        "status": "RUNNING",
        "started_at": datetime.now().isoformat(),
        "finished_at": None,
        "duration_seconds": None,
        "return_code": None,
        "stdout": [],
        "stderr": [],
        "error": None,
    }

    executions.append(
        execution
    )

    executions = executions[-200:]

    save_executions(
        executions
    )

    return execution


def update_execution(
    execution_id,
    **changes,
):

    executions = load_executions()

    for execution in executions:

        if execution.get("id") == execution_id:

            execution.update(
                changes
            )

            break

    save_executions(
        executions
    )


# ============================================================
# RUN PYTHON SCRIPT
# ============================================================

def execute_script(
    script_path,
    execution_id,
    node_id,
):

    start_time = datetime.now()

    if not script_path.exists():

        message = (
            f"File not found: {script_path}"
        )

        update_execution(
            execution_id,
            status="FAILED",
            finished_at=datetime.now().isoformat(),
            error=message,
        )

        return False

    runtime_state[
        "current_node"
    ] = node_id

    try:

        result = subprocess.run(
            [
                PYTHON_EXE,
                str(script_path),
            ],
            cwd=str(PROJECT_FOLDER),
            capture_output=True,
            text=True,
        )

        stdout_lines = (
            result.stdout.splitlines()
            if result.stdout
            else []
        )

        stderr_lines = (
            result.stderr.splitlines()
            if result.stderr
            else []
        )

        end_time = datetime.now()

        duration = (
            end_time - start_time
        ).total_seconds()

        status = (
            "SUCCESS"
            if result.returncode == 0
            else "FAILED"
        )

        update_execution(
            execution_id,
            status=status,
            finished_at=end_time.isoformat(),
            duration_seconds=round(
                duration,
                2,
            ),
            return_code=result.returncode,
            stdout=stdout_lines[-300:],
            stderr=stderr_lines[-300:],
            error=(
                None
                if result.returncode == 0
                else "\n".join(
                    stderr_lines[-20:]
                )
            ),
        )

        return (
            result.returncode == 0
        )

    except Exception as error:

        end_time = datetime.now()

        update_execution(
            execution_id,
            status="FAILED",
            finished_at=end_time.isoformat(),
            error=str(error),
        )

        return False


# ============================================================
# FULL WORKFLOW BACKGROUND RUN
# ============================================================

def run_full_workflow_background(
    execution_id,
):

    if not automation_lock.acquire(
        blocking=False
    ):

        update_execution(
            execution_id,
            status="FAILED",
            finished_at=datetime.now().isoformat(),
            error=(
                "Another automation "
                "is already running."
            ),
        )

        return

    runtime_state[
        "running"
    ] = True

    runtime_state[
        "current_execution_id"
    ] = execution_id

    runtime_state[
        "started_at"
    ] = datetime.now().isoformat()

    runtime_state[
        "last_error"
    ] = None

    start_time = datetime.now()

    try:

        main_file = (
            PROJECT_FOLDER / "main.py"
        )

        result = subprocess.run(
            [
                PYTHON_EXE,
                str(main_file),
            ],
            cwd=str(PROJECT_FOLDER),
            capture_output=True,
            text=True,
        )

        end_time = datetime.now()

        duration = (
            end_time - start_time
        ).total_seconds()

        stdout_lines = (
            result.stdout.splitlines()
            if result.stdout
            else []
        )

        stderr_lines = (
            result.stderr.splitlines()
            if result.stderr
            else []
        )

        if result.returncode == 0:

            status = "SUCCESS"

        else:

            status = "FAILED"

            runtime_state[
                "last_error"
            ] = "\n".join(
                stderr_lines[-20:]
            )

        update_execution(
            execution_id,
            status=status,
            finished_at=end_time.isoformat(),
            duration_seconds=round(
                duration,
                2,
            ),
            return_code=result.returncode,
            stdout=stdout_lines[-500:],
            stderr=stderr_lines[-500:],
            error=runtime_state[
                "last_error"
            ],
        )

    except Exception as error:

        runtime_state[
            "last_error"
        ] = str(error)

        update_execution(
            execution_id,
            status="FAILED",
            finished_at=datetime.now().isoformat(),
            error=str(error),
        )

    finally:

        runtime_state[
            "running"
        ] = False

        runtime_state[
            "current_node"
        ] = None

        runtime_state[
            "current_execution_id"
        ] = None

        automation_lock.release()


# ============================================================
# NODE BACKGROUND RUN
# ============================================================

def run_node_background(
    node_id,
    execution_id,
):

    node = NODE_MAP[
        node_id
    ]

    runtime_state[
        "running"
    ] = True

    runtime_state[
        "current_node"
    ] = node_id

    try:

        execute_script(
            node["file"],
            execution_id,
            node_id,
        )

    finally:

        runtime_state[
            "running"
        ] = False

        runtime_state[
            "current_node"
        ] = None


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return {
        "name":
            "THRAANSH Workflow Control API",

        "version":
            "2.0.0",

        "status":
            "running",
    }


# ============================================================
# STATUS
# ============================================================

@app.get("/status")
def status():

    queue = load_queue()

    total = len(queue)

    published = 0
    pending = 0
    failed = 0
    video_ready = 0

    failure_statuses = {
        "VOICE_FAILED",
        "MEDIA_FAILED",
        "SCENES_FAILED",
        "FOOTAGE_FAILED",
        "VIDEO_FAILED",
        "YOUTUBE_FAILED",
    }

    for article in queue:

        article_status = article.get(
            "status",
            "UNKNOWN",
        )

        if article.get(
            "youtube_upload_status"
        ) == "PUBLISHED":

            published += 1

        elif article_status in failure_statuses:

            failed += 1

        else:

            pending += 1

        if article_status == "VIDEO_READY":

            video_ready += 1

    return {
        "system_status":
            (
                "RUNNING"
                if runtime_state["running"]
                else "READY"
            ),

        "automation_running":
            runtime_state["running"],

        "current_node":
            runtime_state["current_node"],

        "current_execution_id":
            runtime_state[
                "current_execution_id"
            ],

        "started_at":
            runtime_state["started_at"],

        "last_error":
            runtime_state["last_error"],

        "total_articles":
            total,

        "published_videos":
            published,

        "video_ready":
            video_ready,

        "pending_articles":
            pending,

        "failed_jobs":
            failed,
    }


# ============================================================
# WORKFLOW
# ============================================================

@app.get("/workflow")
def workflow():

    nodes = []

    for node_id, node in NODE_MAP.items():

        nodes.append({
            "id": node_id,
            "name": node["name"],
            "type": "executable",
            "exists": node["file"].exists(),
        })

    for node_id, node in VIRTUAL_NODES.items():

        nodes.append({
            "id": node_id,
            "name": node["name"],
            "type": node["type"],
            "exists": True,
        })

    return {
        "nodes": nodes,
        "running_node":
            runtime_state["current_node"],
    }


# ============================================================
# RUN FULL AUTOMATION
# ============================================================

@app.post("/run")
def run_automation():

    if runtime_state[
        "running"
    ]:

        raise HTTPException(
            status_code=409,
            detail=(
                "Automation is already running."
            ),
        )

    execution = create_execution(
        "FULL_WORKFLOW"
    )

    thread = threading.Thread(
        target=run_full_workflow_background,
        args=(
            execution["id"],
        ),
        daemon=True,
    )

    thread.start()

    return {
        "message":
            "THRAANSH automation started.",

        "execution_id":
            execution["id"],
    }


# ============================================================
# RUN ONE NODE
# ============================================================

@app.post("/run-node/{node_id}")
def run_node(node_id: str):

    if node_id not in NODE_MAP:

        raise HTTPException(
            status_code=404,
            detail=(
                "This node is not directly executable."
            ),
        )

    if runtime_state[
        "running"
    ]:

        raise HTTPException(
            status_code=409,
            detail=(
                "Another automation job is running."
            ),
        )

    execution = create_execution(
        "NODE",
        node_id=node_id,
    )

    thread = threading.Thread(
        target=run_node_background,
        args=(
            node_id,
            execution["id"],
        ),
        daemon=True,
    )

    thread.start()

    return {
        "message":
            f"{NODE_MAP[node_id]['name']} started.",

        "execution_id":
            execution["id"],
    }


# ============================================================
# EXECUTIONS
# ============================================================

@app.get("/executions")
def executions():

    data = load_executions()

    return list(
        reversed(data)
    )


@app.get("/executions/{execution_id}")
def execution_details(
    execution_id: str,
):

    data = load_executions()

    for execution in data:

        if execution.get(
            "id"
        ) == execution_id:

            return execution

    raise HTTPException(
        status_code=404,
        detail="Execution not found.",
    )


# ============================================================
# ARTICLES
# ============================================================

@app.get("/articles")
def articles():

    queue = load_queue()

    results = []

    for index, article in enumerate(
        queue
    ):

        item = dict(article)

        item[
            "queue_index"
        ] = index

        results.append(
            item
        )

    return results


# ============================================================
# RETRY ARTICLE
# ============================================================

@app.post("/retry/{queue_index}")
def retry_article(
    queue_index: int,
):

    queue = load_queue()

    if (
        queue_index < 0
        or queue_index >= len(queue)
    ):

        raise HTTPException(
            status_code=404,
            detail="Article not found.",
        )

    article = queue[
        queue_index
    ]

    article[
        "retry_count"
    ] = 0

    article[
        "last_error"
    ] = None

    status = article.get(
        "status"
    )

    if status and status.endswith(
        "_FAILED"
    ):

        article[
            "status"
        ] = "PENDING"

    article[
        "updated_at"
    ] = datetime.now().isoformat()

    save_queue(
        queue
    )

    return {
        "message":
            "Article reset for retry.",

        "queue_index":
            queue_index,

        "title":
            article.get(
                "title"
            ),
    }


# ============================================================
# VIDEOS
# ============================================================

@app.get("/videos")
def videos():

    queue = load_queue()

    results = []

    for index, article in enumerate(
        queue
    ):

        video_file = article.get(
            "final_video_file"
        )

        if not video_file:

            continue

        results.append({

            "queue_index":
                index,

            "title":
                article.get("title"),

            "status":
                article.get("status"),

            "video_file":
                video_file,

            "video_exists":
                Path(video_file).exists(),

            "rights_status":
                article.get(
                    "rights_status"
                ),

            "youtube_status":
                article.get(
                    "youtube_upload_status"
                ),

            "youtube_video_id":
                article.get(
                    "youtube_video_id"
                ),

            "youtube_url":
                article.get(
                    "youtube_url"
                ),

            "published_at":
                article.get(
                    "youtube_published_at"
                ),
        })

    return results


# ============================================================
# YOUTUBE MANUAL PUBLISH
# ============================================================

@app.post("/publish/youtube")
def publish_youtube():

    if runtime_state[
        "running"
    ]:

        raise HTTPException(
            status_code=409,
            detail=(
                "Another automation job is running."
            ),
        )

    return run_node(
        "youtube"
    )


# ============================================================
# PLATFORM STATUS
# ============================================================

@app.get("/platforms")
def platforms():

    youtube_token = (
        PROJECT_FOLDER
        / "credentials"
        / "youtube_token.json"
    )

    return {

        "youtube": {
            "connected":
                youtube_token.exists(),

            "status":
                (
                    "ACTIVE"
                    if youtube_token.exists()
                    else "NOT_CONNECTED"
                ),
        },

        "x": {
            "connected":
                False,

            "status":
                "NOT_CONNECTED",
        },

        "facebook": {
            "connected":
                False,

            "status":
                "UNDER_REVIEW",
        },

        "instagram": {
            "connected":
                False,

            "status":
                "UNDER_REVIEW",
        },
    }


# ============================================================
# RIGHTS
# ============================================================

@app.get("/rights")
def rights():

    queue = load_queue()

    results = []

    for index, article in enumerate(
        queue
    ):

        rights_status = article.get(
            "rights_status"
        )

        if not rights_status:
            continue

        results.append({

            "queue_index":
                index,

            "title":
                article.get("title"),

            "rights_status":
                rights_status,

            "warnings":
                article.get(
                    "rights_warnings",
                    [],
                ),

            "blocking_issues":
                article.get(
                    "rights_blocking_issues",
                    [],
                ),
        })

    return results


# ============================================================
# LOGS
# ============================================================

@app.get("/logs")
def logs():

    if not AUTOMATION_LOG_FILE.exists():

        return {
            "logs": []
        }

    try:

        lines = (
            AUTOMATION_LOG_FILE
            .read_text(
                encoding="utf-8"
            )
            .splitlines()
        )

        return {
            "logs":
                lines[-500:]
        }

    except Exception as error:

        return {
            "logs": [
                str(error)
            ]
        }


# ============================================================
# SCHEDULE
# ============================================================

DEFAULT_SCHEDULE = {
    "timezone": "Asia/Kolkata",

    "times": [
        "07:00",
        "09:00",
        "11:00",
        "13:00",
        "15:00",
        "17:00",
        "19:00",
        "20:00",
    ],

    "videos_per_run": 1,
}


@app.get("/schedule")
def schedule():

    return read_json(
        SCHEDULE_FILE,
        DEFAULT_SCHEDULE,
    )


@app.put("/schedule")
def update_schedule(
    update: ScheduleUpdate,
):

    schedule_data = read_json(
        SCHEDULE_FILE,
        DEFAULT_SCHEDULE,
    )

    schedule_data[
        "times"
    ] = update.times

    write_json(
        SCHEDULE_FILE,
        schedule_data,
    )

    return {
        "message":
            "Dashboard schedule updated.",

        "schedule":
            schedule_data,

        "important_note":
            (
                "Windows Task Scheduler is still "
                "the system executing the real "
                "scheduled jobs. This API currently "
                "updates the dashboard schedule data."
            ),
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {

        "api":
            "OK",

        "python":
            str(PYTHON_EXE),

        "queue_file":
            QUEUE_FILE.exists(),

        "youtube_credentials":
            (
                PROJECT_FOLDER
                / "credentials"
                / "youtube_token.json"
            ).exists(),

        "main_py":
            (
                PROJECT_FOLDER
                / "main.py"
            ).exists(),
    }