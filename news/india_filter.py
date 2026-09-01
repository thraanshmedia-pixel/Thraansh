import json
from datetime import datetime
from pathlib import Path


PROJECT_FOLDER = Path(__file__).resolve().parents[1]
QUEUE_FILE = PROJECT_FOLDER / "data" / "article_queue.json"


INDIA_TERMS = [
    "india",
    "indian",
    "bharat",
    "delhi",
    "new delhi",
    "mumbai",
    "bengaluru",
    "bangalore",
    "chennai",
    "hyderabad",
    "kolkata",
    "pune",
    "ahmedabad",
    "jaipur",
    "lucknow",
    "patna",
    "guwahati",
    "kochi",
    "kerala",
    "karnataka",
    "tamil nadu",
    "telangana",
    "maharashtra",
    "gujarat",
    "punjab",
    "haryana",
    "uttar pradesh",
    "madhya pradesh",
    "rajasthan",
    "odisha",
    "bihar",
    "assam",
    "goa",

    "prime minister",
    "narendra modi",
    "modi",
    "parliament",
    "lok sabha",
    "rajya sabha",
    "supreme court",
    "high court",
    "ministry",
    "mea",
    "ministry of external affairs",

    "rbi",
    "reserve bank of india",
    "sensex",
    "nifty",
    "rupee",

    "isro",
    "drdo",

    "bcci",
    "ipl",
    "team india",
    "indian cricket",
    "shubman gill",
    "virat kohli",
    "rohit sharma",

    "bollywood",
    "indian cinema",

    "indian army",
    "indian navy",
    "indian air force",
]


FOREIGN_ONLY_TERMS = [
    "united kingdom",
    "uk police",
    "britain",
    "british police",
    "england police",

    "united states",
    "us judge",
    "american football",
    "nfl",

    "canada tariffs",
    "swedish military",
]


def clean_text(value):
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def load_queue():
    if not QUEUE_FILE.exists():
        print("ERROR: article_queue.json not found.")
        return []

    with open(
        QUEUE_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    return data if isinstance(data, list) else []


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


def article_text(article):
    return " ".join(
        [
            clean_text(article.get("title")),
            clean_text(article.get("teaser")),
            clean_text(article.get("description")),
            clean_text(article.get("content")),
            clean_text(article.get("article_text")),
            clean_text(article.get("publisher")),
            clean_text(article.get("category_slug")),
        ]
    ).lower()


def india_score(article):
    text = article_text(article)

    score = 0

    for term in INDIA_TERMS:
        if term in text:
            score += 2

    # Stronger weight if title itself is India-related
    title = clean_text(
        article.get("title")
    ).lower()

    for term in INDIA_TERMS:
        if term in title:
            score += 3

    for term in FOREIGN_ONLY_TERMS:
        if term in text:
            score -= 2

    return score


def classify_article(article):
    score = india_score(article)

    if score >= 3:
        return "INDIA", score

    return "NON_INDIA", score


def main():
    print()
    print("=" * 70)
    print("THRAANSH INDIA STORY FILTER")
    print("=" * 70)

    queue = load_queue()

    if not queue:
        print("No articles found.")
        return

    india_count = 0
    non_india_count = 0

    for article in queue:
        classification, score = classify_article(
            article
        )

        article[
            "story_region"
        ] = classification

        article[
            "india_score"
        ] = score

        article[
            "region_checked_at"
        ] = datetime.now().isoformat()

        if classification == "INDIA":
            india_count += 1

        else:
            non_india_count += 1

    save_queue(queue)

    print()
    print(
        f"India stories: {india_count}"
    )

    print(
        f"Non-India stories: {non_india_count}"
    )

    print()
    print(
        "Queue updated successfully."
    )


if __name__ == "__main__":
    main()