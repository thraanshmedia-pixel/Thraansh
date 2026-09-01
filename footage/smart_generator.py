import json
import os
import re
import time
from pathlib import Path
from datetime import datetime

import requests


# ============================================================
# THRAANSH SMART FOOTAGE GENERATOR
# Downloads one relevant Pexels clip for every planned scene
# ============================================================

PROJECT_FOLDER = Path(__file__).resolve().parents[1]

DATA_FOLDER = PROJECT_FOLDER / "data"
QUEUE_FILE = DATA_FOLDER / "article_queue.json"

DOWNLOAD_FOLDER = PROJECT_FOLDER / "scene_footage"
DOWNLOAD_FOLDER.mkdir(exist_ok=True)

ENV_FILE = PROJECT_FOLDER / ".env"


# ============================================================
# LOAD ENV
# ============================================================

def load_env():

    if not ENV_FILE.exists():
        return {}

    env = {}

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():

        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()

    return env


ENV = load_env()

PEXELS_API_KEY = ENV.get("PEXELS_API_KEY")


# ============================================================
# LOAD QUEUE
# ============================================================

def load_queue():

    if not QUEUE_FILE.exists():
        print("article_queue.json not found")
        return []

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# SAVE QUEUE
# ============================================================

def save_queue(queue):

    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)


# ============================================================
# GET ARTICLE
# ============================================================

def get_article(queue):

    for article in queue:

        if article.get("scene_plan") and not article.get("scene_files"):
            return article

        if article.get("status") == "SCENE_PLANNED":
            return article

    return None


# ============================================================
# SAFE NAME
# ============================================================

def safe_name(text):

    text = re.sub(r"[^A-Za-z0-9]+", "_", text)

    return text.strip("_")[:60]


# ============================================================
# SEARCH PEXELS
# ============================================================

def search_video(query):

    url = "https://api.pexels.com/videos/search"

    headers = {
        "Authorization": PEXELS_API_KEY
    }

    params = {
        "query": query,
        "per_page": 10,
        "orientation": "landscape"
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    videos = data.get("videos", [])

    if not videos:
        return None

    return videos[0]


# ============================================================
# CHOOSE VIDEO FILE
# ============================================================

def choose_video(video):

    files = video.get("video_files", [])

    best = None

    for f in files:

        width = f.get("width", 0)

        if width >= 1280:
            return f

        if best is None:
            best = f

    return best


# ============================================================
# DOWNLOAD FILE
# ============================================================

def download_file(url, destination):

    with requests.get(url, stream=True, timeout=60) as r:

        r.raise_for_status()

        with open(destination, "wb") as f:

            for chunk in r.iter_content(chunk_size=8192):

                if chunk:
                    f.write(chunk)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("THRAANSH SMART FOOTAGE GENERATOR")
    print("=" * 70)

    if not PEXELS_API_KEY:

        print()
        print("ERROR: PEXELS_API_KEY missing in .env")

        return

    queue = load_queue()

    article = get_article(queue)

    if article is None:

        print()
        print("No article waiting for smart footage generation.")

        return

    title = article["title"]

    print()
    print("ARTICLE:")
    print(title)

    article_folder = DOWNLOAD_FOLDER / safe_name(title)

    article_folder.mkdir(exist_ok=True)

    scene_files = []

    for scene in article["scene_plan"]:

        number = scene["scene_number"]

        query = scene["search_query"]

        print()
        print(f"Scene {number}")
        print("Searching:", query)

        try:

            video = search_video(query)

            if not video:

                print("No video found")

                continue

            selected = choose_video(video)

            if not selected:

                print("No downloadable file")

                continue

            file_url = selected["link"]

            output = article_folder / f"scene_{number}.mp4"

            print("Downloading...")

            download_file(file_url, output)

            scene_files.append(str(output))

            scene["status"] = "DOWNLOADED"

            scene["video_file"] = str(output)

            scene["pexels_url"] = video.get("url")

            scene["pexels_id"] = video.get("id")

            print("Completed")

            time.sleep(1)

        except Exception as error:

            print("FAILED:", error)

            scene["status"] = "FAILED"

            scene["error"] = str(error)

    if scene_files:

        article["scene_files"] = scene_files

        article["status"] = "SCENES_READY"

        article["updated_at"] = datetime.now().isoformat()

        save_queue(queue)

        print()
        print("=" * 70)
        print("SMART FOOTAGE COMPLETED")
        print("=" * 70)

        print()
        print(f"Scenes downloaded: {len(scene_files)}")

        print("Saved inside:")

        print(article_folder)

    else:

        article["status"] = "FOOTAGE_FAILED"

        article["updated_at"] = datetime.now().isoformat()

        save_queue(queue)

        print()
        print("No footage downloaded.")


if __name__ == "__main__":
    main()