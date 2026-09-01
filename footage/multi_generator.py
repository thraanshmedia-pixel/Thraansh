import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

PROJECT = Path(__file__).resolve().parents[1]
QUEUE = PROJECT / "data" / "article_queue.json"
OUT = PROJECT / "scene_footage"
OUT.mkdir(exist_ok=True)

API = "https://commons.wikimedia.org/w/api.php"

HEADERS = {
    "User-Agent": "THRAANSH-Automation/1.0"
}


def load():
    return json.load(open(QUEUE, encoding="utf-8"))


def save(q):
    json.dump(q, open(QUEUE, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)


def search(query):
    p = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": 6,
        "gsrsearch": query,
        "gsrlimit": 20,
        "prop": "imageinfo",
        "iiprop": "url|mime"
    }

    r = requests.get(API, params=p, headers=HEADERS)
    r.raise_for_status()

    pages = r.json().get("query", {}).get("pages", {})

    for page in pages.values():

        info = page.get("imageinfo", [])

        if not info:
            continue

        info = info[0]

        mime = info.get("mime", "")

        if mime.startswith("video/"):

            return info["url"]

    return None


def download(url, path):

    for attempt in range(5):

        r = requests.get(
            url,
            headers=HEADERS,
            stream=True
        )

        if r.status_code == 429:

            time.sleep(10 * (attempt + 1))
            continue

        r.raise_for_status()

        with open(path, "wb") as f:

            for c in r.iter_content(1024 * 1024):

                if c:
                    f.write(c)

        return True

    return False


def main():

    q = load()

    article = next(
        a for a in q
        if a.get("status") == "SCENE_PLAN_READY"
    )

    plan = article["scene_plan"]

    files = []

    for i, scene in enumerate(plan, 1):

        query = scene["search_query"]

        print("Searching:", query)

        url = search(query)

        if not url:

            print("No video")
            continue

        ext = Path(
            urlparse(url).path
        ).suffix

        path = OUT / f"scene_{i}{ext}"

        if download(url, path):

            files.append(str(path))

            print("READY:", path)

        time.sleep(2)

    if len(files) < 3:

        raise RuntimeError(
            "Not enough scenes"
        )

    article["scene_footage_files"] = files
    article["status"] = "MULTI_MEDIA_READY"

    save(q)

    print()
    print("SCENE_PLAN_READY -> MULTI_MEDIA_READY")


if __name__ == "__main__":
    main()