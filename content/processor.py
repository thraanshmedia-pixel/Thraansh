import json
from pathlib import Path
from datetime import datetime


# ============================================================
# THRAANSH CONTENT PROCESSOR
# ============================================================

PROJECT_FOLDER = Path(__file__).resolve().parents[1]

DATA_FOLDER = PROJECT_FOLDER / "data"

QUEUE_FILE = DATA_FOLDER / "article_queue.json"


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

        print("ERROR: Could not read article_queue.json")
        print(error)

        return []


# ============================================================
# SAVE QUEUE
# ============================================================

def save_queue(queue):

    with open(
        QUEUE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            queue,
            file,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# FIND NEXT NEW ARTICLE
# ============================================================

def get_next_article(queue):

    for article in queue:

        if article.get("status") == "NEW":
            return article

    return None


# ============================================================
# PROCESS ARTICLE
# ============================================================

def process_article(article):

    print()
    print("=" * 60)
    print("THRAANSH CONTENT PROCESSOR")
    print("=" * 60)

    print()
    print("Article selected:")
    print(article.get("title"))

    print()
    print("Article link:")
    print(article.get("link"))

    print()

    article["status"] = "PROCESSING"

    article["updated_at"] = datetime.now().isoformat()

    print("Status changed:")
    print("NEW -> PROCESSING")

    return article


# ============================================================
# MAIN
# ============================================================

def main():

    queue = load_queue()

    if not queue:

        print("Article queue is empty.")
        return

    article = get_next_article(queue)

    if article is None:

        print("No NEW articles are waiting.")
        return

    process_article(article)

    save_queue(queue)

    print()
    print("Queue updated successfully.")

    print()
    print("Next stage will be script generation.")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()