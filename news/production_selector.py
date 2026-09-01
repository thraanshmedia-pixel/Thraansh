import json
import re
from datetime import datetime
from pathlib import Path


# ============================================================
# THRAANSH PRODUCTION SELECTOR V4
# IMPORTANT NEWS + STRICT INDIA CRICKET PRIORITY
# FREE ONLY
# ============================================================

PROJECT_FOLDER = Path(__file__).resolve().parents[1]
QUEUE_FILE = PROJECT_FOLDER / "data" / "article_queue.json"

PROCESSED_STATUSES = {
    "SCRIPT_READY",
    "VOICE_READY",
    "SCENE_PLAN_READY",
    "SCENE_FOOTAGE_FAILED",
    "MULTI_MEDIA_READY",
    "MULTI_VIDEO_FAILED",
    "VIDEO_READY",
    "RIGHTS_PASS",
    "PUBLISHED",
    "UPLOADED",
}

FULL_MIN_CHARS = 1200
MEDIUM_MIN_CHARS = 600
SHORT_MIN_CHARS = 300

MIN_IMPORTANCE_SCORE = 45


# ============================================================
# KEYWORDS
# ============================================================

BREAKING_TERMS = {
    "breaking",
    "breaking news",
    "just in",
    "major",
    "urgent",
    "developing",
}

HIGH_IMPACT_TERMS = {
    "killed",
    "dies",
    "death",
    "attack",
    "war",
    "missile",
    "explosion",
    "blast",
    "earthquake",
    "flood",
    "cyclone",
    "landslide",
    "crash",
    "fire",
    "emergency",
    "arrested",
    "convicted",
    "verdict",
    "supreme court",
    "high court",
    "resigns",
    "resignation",
    "ceasefire",
    "sanctions",
}

GOVERNMENT_TERMS = {
    "prime minister",
    "president",
    "government",
    "parliament",
    "cabinet",
    "minister",
    "ministry",
    "election",
    "lok sabha",
    "rajya sabha",
    "chief minister",
    "supreme court",
    "high court",
    "rbi",
}

BUSINESS_TERMS = {
    "merger",
    "acquisition",
    "acquires",
    "ipo",
    "bankruptcy",
    "layoffs",
    "market crash",
    "interest rate",
    "repo rate",
    "inflation",
    "gdp",
}

TECH_TERMS = {
    "artificial intelligence",
    "openai",
    "google ai",
    "microsoft ai",
    "apple ai",
    "meta ai",
    "nvidia",
    "cyberattack",
    "cyber attack",
    "data breach",
}

MAJOR_SPORTS_TERMS = {
    "world cup",
    "final",
    "semi-final",
    "semifinal",
    "champion",
    "champions",
    "wins title",
    "won title",
    "gold medal",
    "silver medal",
    "bronze medal",
    "world record",
    "national record",
    "retirement",
    "retires",
    "injured",
    "injury",
    "suspended",
    "banned",
    "squad announced",
}

LOW_VALUE_TERMS = {
    "horoscope",
    "astrology",
    "zodiac",
    "photo gallery",
    "airport look",
    "spotted at",
    "throwback",
    "old video",
    "old photo",
    "internet reacts",
    "fans react",
}


# ============================================================
# STRICT CRICKET TERMS
# ============================================================

STRONG_CRICKET_TERMS = {
    "cricket",
    "bcci",
    "icc",
    "test cricket",
    "test match",
    "odi",
    "t20i",
    "ipl",
    "wicket",
    "wickets",
    "innings",
    "batsman",
    "batter",
    "bowler",
    "bowling",
    "batting",
    "cricketer",
}

INDIA_CRICKET_TERMS = {
    "bcci",
    "team india",
    "india cricket",
    "indian cricket",
    "india men's team",
    "india mens team",
    "india women's team",
    "india womens team",
    "women in blue",
    "men in blue",
}

INDIAN_CRICKET_PLAYERS = {
    "virat kohli",
    "rohit sharma",
    "shubman gill",
    "jasprit bumrah",
    "hardik pandya",
    "ravindra jadeja",
    "kl rahul",
    "rishabh pant",
    "suryakumar yadav",
    "mohammed siraj",
    "kuldeep yadav",
    "yashasvi jaiswal",
    "abhishek sharma",
    "smriti mandhana",
    "harmanpreet kaur",
    "jemimah rodrigues",
    "deepti sharma",
    "shafali verma",
    "renuka singh",
}

CRICKET_IMPORTANT_TERMS = {
    "squad",
    "selected",
    "selection",
    "dropped",
    "recalled",
    "injured",
    "injury",
    "ruled out",
    "replacement",
    "captain",
    "captaincy",
    "coach",
    "retirement",
    "retires",
    "retired",
    "record",
    "century",
    "five-wicket",
    "hat-trick",
    "hat trick",
    "wins",
    "won",
    "defeats",
    "defeated",
    "final",
    "semi-final",
    "semifinal",
    "world cup",
    "champions trophy",
    "asia cup",
    "test championship",
    "central contract",
    "suspended",
    "banned",
    "announces",
    "announced",
}


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def normalize(value):
    return clean_text(value).lower()


def contains_term(text, term):
    pattern = (
        r"(?<![a-z0-9])"
        + re.escape(term.lower())
        + r"(?![a-z0-9])"
    )

    return bool(
        re.search(
            pattern,
            text.lower()
        )
    )


def term_hits(text, terms):
    return [
        term
        for term in terms
        if contains_term(text, term)
    ]


# ============================================================
# QUEUE
# ============================================================

def load_queue():

    if not QUEUE_FILE.exists():
        print("ERROR: article_queue.json not found.")
        return []

    try:
        with QUEUE_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

    except Exception as error:
        print("ERROR:", error)

    return []


def save_queue(queue):

    temp = QUEUE_FILE.with_suffix(
        ".json.tmp"
    )

    with temp.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            queue,
            file,
            ensure_ascii=False,
            indent=2
        )

    temp.replace(QUEUE_FILE)


# ============================================================
# ARTICLE TEXT
# ============================================================

def get_body(article):

    fields = [
        "source_text",
        "article_text",
        "content",
        "description",
        "teaser",
        "summary",
        "excerpt",
    ]

    best = ""

    for field in fields:

        value = clean_text(
            article.get(field)
        )

        if len(value) > len(best):
            best = value

    return best


def title_text(article):
    return normalize(
        article.get("title")
    )


def category_text(article):

    values = [
        article.get("category"),
        article.get("category_slug"),
        article.get("subcategory"),
    ]

    return normalize(
        " ".join(
            clean_text(v)
            for v in values
            if v
        )
    )


def summary_text(article):

    values = [
        article.get("title"),
        article.get("description"),
        article.get("teaser"),
        article.get("summary"),
        article.get("excerpt"),
    ]

    return normalize(
        " ".join(
            clean_text(v)
            for v in values
            if v
        )
    )


# ============================================================
# SOURCE QUALITY
# ============================================================

def classify_source(article):

    body = get_body(article)
    char_count = len(body)

    status = clean_text(
        article.get("source_fetch_status")
    ).upper()

    long_ready = bool(
        article.get("long_form_source_ready")
    )

    if (
        char_count >= FULL_MIN_CHARS
        or long_ready
        or status == "FULL_SOURCE_READY"
    ):
        return "FULL", char_count

    if char_count >= MEDIUM_MIN_CHARS:
        return "MEDIUM", char_count

    if char_count >= SHORT_MIN_CHARS:
        return "SHORT", char_count

    return "SKIP", char_count


# ============================================================
# PROCESSED
# ============================================================

def already_processed(article):

    status = clean_text(
        article.get("status")
    ).upper()

    if status in PROCESSED_STATUSES:
        return True

    output_fields = [
        "hindi_script",
        "narration_script",
        "voice_file",
        "audio_file",
        "final_video_file",
        "youtube_video_id",
        "facebook_video_id",
        "instagram_media_id",
    ]

    return any(
        clean_text(article.get(field))
        for field in output_fields
    )


def clear_old_selections(queue):

    count = 0

    for article in queue:

        if article.get("production_selected"):

            article["production_selected"] = False
            count += 1

    return count


# ============================================================
# STRICT CRICKET CLASSIFIER
# ============================================================

def cricket_analysis(article):

    title = title_text(article)
    category = category_text(article)
    summary = summary_text(article)

    # --------------------------------------------------------
    # Cricket must be established from title/category first.
    # We deliberately DO NOT scan the entire scraped webpage.
    # --------------------------------------------------------

    title_cricket = term_hits(
        title,
        STRONG_CRICKET_TERMS
    )

    category_cricket = (
        "cricket" in category
    )

    title_players = term_hits(
        title,
        INDIAN_CRICKET_PLAYERS
    )

    summary_cricket = term_hits(
        summary,
        STRONG_CRICKET_TERMS
    )

    # A known Indian cricketer in the headline counts as
    # cricket evidence even if "cricket" isn't literally there.

    is_cricket = bool(
        title_cricket
        or category_cricket
        or title_players
        or (
            summary_cricket
            and (
                "sports" in category
                or "cricket" in category
            )
        )
    )

    if not is_cricket:

        return {
            "is_cricket": False,
            "india_related": False,
            "important_update": False,
            "important_hits": [],
        }

    india_hits = term_hits(
        summary,
        INDIA_CRICKET_TERMS
    )

    player_hits = term_hits(
        summary,
        INDIAN_CRICKET_PLAYERS
    )

    india_related = bool(
        india_hits
        or player_hits
    )

    important_hits = term_hits(
        summary,
        CRICKET_IMPORTANT_TERMS
    )

    important_update = bool(
        is_cricket
        and india_related
        and important_hits
    )

    return {
        "is_cricket":
            is_cricket,

        "india_related":
            india_related,

        "important_update":
            important_update,

        "important_hits":
            important_hits,
    }


# ============================================================
# IMPORTANCE
# ============================================================

def importance_score(
    article,
    source_class
):

    title = title_text(article)

    # Only headline + editorial summary for topic scoring.
    # This prevents related-story/footer contamination.

    text = summary_text(article)

    score = 0
    reasons = []

    if source_class == "FULL":
        score += 10
        reasons.append("full-source")

    elif source_class == "MEDIUM":
        score += 7
        reasons.append("medium-source")

    else:
        score += 4
        reasons.append("short-source")

    breaking = term_hits(
        title,
        BREAKING_TERMS
    )

    if breaking:
        score += 15
        reasons.append("breaking")

    impact = term_hits(
        text,
        HIGH_IMPACT_TERMS
    )

    if impact:
        score += min(
            30,
            12 + len(impact) * 4
        )

        reasons.append("high-impact")

    government = term_hits(
        text,
        GOVERNMENT_TERMS
    )

    if government:
        score += min(
            20,
            8 + len(government) * 2
        )

        reasons.append(
            "government-public-interest"
        )

    business = term_hits(
        text,
        BUSINESS_TERMS
    )

    if business:
        score += min(
            18,
            7 + len(business) * 2
        )

        reasons.append("major-business")

    technology = term_hits(
        text,
        TECH_TERMS
    )

    if technology:
        score += min(
            18,
            7 + len(technology) * 2
        )

        reasons.append("technology")

    sports = term_hits(
        text,
        MAJOR_SPORTS_TERMS
    )

    if sports:
        score += min(
            22,
            8 + len(sports) * 3
        )

        reasons.append("major-sports")

    cricket = cricket_analysis(
        article
    )

    if cricket["important_update"]:

        score += 28

        reasons.append(
            "important-indian-cricket"
        )

    elif (
        cricket["is_cricket"]
        and cricket["india_related"]
    ):

        score += 8

        reasons.append(
            "india-cricket"
        )

    low = term_hits(
        text,
        LOW_VALUE_TERMS
    )

    if low:

        score -= min(
            35,
            15 + len(low) * 5
        )

        reasons.append(
            "low-value-penalty"
        )

    # Headline quality signal.

    if len(title) >= 35:
        score += 3

    if len(title) >= 65:
        score += 2

    score = max(
        0,
        min(100, score)
    )

    return score, reasons, cricket


# ============================================================
# SELECT
# ============================================================

def select_story(queue):

    candidates = []

    stats = {
        "total": len(queue),
        "processed": 0,
        "short": 0,
        "below_importance": 0,
        "eligible": 0,
    }

    for position, article in enumerate(queue):

        title = clean_text(
            article.get("title")
        )

        if not title:
            continue

        if already_processed(article):

            stats["processed"] += 1
            continue

        source_class, chars = (
            classify_source(article)
        )

        if source_class == "SKIP":

            stats["short"] += 1
            continue

        score, reasons, cricket = (
            importance_score(
                article,
                source_class
            )
        )

        if score < MIN_IMPORTANCE_SCORE:

            stats[
                "below_importance"
            ] += 1

            continue

        stats["eligible"] += 1

        source_priority = {
            "FULL": 3,
            "MEDIUM": 2,
            "SHORT": 1,
        }[source_class]

        candidates.append({
            "position": position,
            "article": article,
            "source_class": source_class,
            "chars": chars,
            "score": score,
            "reasons": reasons,
            "cricket": cricket,
            "source_priority":
                source_priority,
        })

    if not candidates:
        return None, stats

    candidates.sort(
        key=lambda x: (
            x["score"],
            x["source_priority"],
            -x["position"],
        ),
        reverse=True
    )

    return candidates[0], stats


# ============================================================
# VIDEO DURATION
# ============================================================

def duration_settings(source_class):

    if source_class == "FULL":

        return {
            "video_duration_class":
                "FULL",
            "target_min_seconds":
                120,
            "target_preferred_seconds":
                150,
            "target_max_seconds":
                180,
        }

    if source_class == "MEDIUM":

        return {
            "video_duration_class":
                "MEDIUM",
            "target_min_seconds":
                60,
            "target_preferred_seconds":
                90,
            "target_max_seconds":
                120,
        }

    return {
        "video_duration_class":
            "SHORT",
        "target_min_seconds":
            30,
        "target_preferred_seconds":
            45,
        "target_max_seconds":
            60,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 76)
    print("THRAANSH PRODUCTION SELECTOR V4")
    print(
        "IMPORTANT NEWS + STRICT INDIA CRICKET PRIORITY"
    )
    print("=" * 76)
    print()

    queue = load_queue()

    if not queue:
        print("Article queue empty.")
        return

    print(
        "Articles in queue:",
        len(queue)
    )

    cleared = clear_old_selections(
        queue
    )

    print(
        "Old selections cleared:",
        cleared
    )

    selection, stats = (
        select_story(queue)
    )

    if not selection:

        save_queue(queue)

        print()
        print(
            "NO IMPORTANT STORY AVAILABLE."
        )

        print(
            "Weak news will not be uploaded."
        )

        return

    article = selection["article"]
    source_class = selection[
        "source_class"
    ]

    score = selection["score"]
    cricket = selection["cricket"]

    settings = duration_settings(
        source_class
    )

    article[
        "production_selected"
    ] = True

    article[
        "production_scope"
    ] = "GLOBAL"

    article[
        "production_queue_position"
    ] = selection["position"]

    article[
        "production_selected_at"
    ] = datetime.now().isoformat()

    article[
        "status"
    ] = "ARTICLE_READY"

    article[
        "last_error"
    ] = None

    article[
        "updated_at"
    ] = datetime.now().isoformat()

    article[
        "source_quality_class"
    ] = source_class

    article[
        "production_source_characters"
    ] = selection["chars"]

    article[
        "importance_score"
    ] = score

    article[
        "importance_reasons"
    ] = selection["reasons"]

    article[
        "is_cricket_story"
    ] = cricket["is_cricket"]

    article[
        "is_india_cricket_story"
    ] = cricket["india_related"]

    article[
        "important_cricket_update"
    ] = cricket[
        "important_update"
    ]

    if cricket["important_update"]:

        priority = (
            "CRICKET_PRIORITY"
        )

    elif score >= 75:

        priority = (
            "BREAKING_HIGH"
        )

    elif score >= 60:

        priority = "HIGH"

    else:

        priority = "IMPORTANT"

    article[
        "production_priority"
    ] = priority

    article.update(settings)

    save_queue(queue)

    print()
    print("=" * 76)
    print("IMPORTANT STORY SELECTED")
    print("=" * 76)

    print()
    print("TITLE:")
    print(
        article.get("title")
    )

    print()
    print(
        "Publisher:",
        clean_text(
            article.get("publisher")
        )
        or "Unknown"
    )

    print()
    print(
        "IMPORTANCE SCORE:",
        score,
        "/ 100"
    )

    print(
        "REASONS:",
        ", ".join(
            selection["reasons"]
        )
    )

    print()
    print(
        "CRICKET:",
        cricket["is_cricket"]
    )

    print(
        "INDIA CRICKET:",
        cricket["india_related"]
    )

    print(
        "IMPORTANT CRICKET UPDATE:",
        cricket["important_update"]
    )

    print()
    print(
        "PRODUCTION PRIORITY:",
        priority
    )

    print()
    print(
        "SOURCE QUALITY:",
        source_class
    )

    print(
        "VIDEO TARGET:",
        settings[
            "target_min_seconds"
        ],
        "-",
        settings[
            "target_max_seconds"
        ],
        "seconds"
    )

    print()
    print(
        "status = ARTICLE_READY"
    )


if __name__ == "__main__":
    main()
