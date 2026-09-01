from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google import genai
from groq import Groq

BASE_DIR = Path(__file__).resolve().parents[1]
QUEUE_FILE = BASE_DIR / "data" / "article_queue.json"
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE, override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
).strip()


TARGET_MIN_SECONDS = 120
TARGET_PREFERRED_SECONDS = 140
TARGET_MAX_SECONDS = 180
PREFERRED_MIN_WORDS = 280
PREFERRED_MAX_WORDS = 430
ABSOLUTE_MIN_WORDS = 120
MAX_ARTICLE_CHARACTERS = 18000
REPETITION_WARNING_THRESHOLD = 0.80
NEAR_EXACT_DUPLICATE_THRESHOLD = 0.93
IST = ZoneInfo("Asia/Kolkata")
PACIFIC = ZoneInfo("America/Los_Angeles")
SCRIPT_VERSION = "COMPLETE_NEWS_FREE_TIER_SINGLE_CALL_V3"


def line():
    print("=" * 76)


def header(text):
    print(); line(); print(text); line(); print()


def clean_text(value):
    if value is None:
        return ""
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split()).strip()


def load_queue():
    if not QUEUE_FILE.exists():
        raise RuntimeError(f"Queue file not found: {QUEUE_FILE}")
    with QUEUE_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise RuntimeError("article_queue.json must contain a list.")
    return data


def save_queue(data):
    temp_file = QUEUE_FILE.with_suffix(".json.tmp")
    with temp_file.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    temp_file.replace(QUEUE_FILE)


def get_next_article(data):
    allowed = {"SELECTED", "PRODUCTION_SELECTED", "READY_FOR_SCRIPT", "HINDI_SCRIPT_FAILED", "HINDI_SCRIPT_QUOTA_WAIT"}
    for article in data:
        if not article.get("production_selected"):
            continue
        existing = clean_text(article.get("hindi_script") or article.get("narration_script") or article.get("presenter_script"))
        status = clean_text(article.get("status")).upper()
        if existing and status in {"SCRIPT_READY", "VOICE_READY", "SCENES_READY", "VIDEO_READY", "RIGHTS_PASS"}:
            continue
        if status in allowed:
            return article
    for article in data:
        if article.get("production_selected") and not clean_text(article.get("hindi_script")):
            return article
    return None


def get_article_body(article):
    fields = ["content", "article_text", "full_text", "body", "description", "teaser", "summary", "excerpt"]
    sections, seen = [], set()
    for field in fields:
        value = clean_text(article.get(field))
        if not value:
            continue
        normalized = re.sub(r"\W+", " ", value.lower(), flags=re.UNICODE).strip()
        if not normalized or normalized in seen:
            continue
        duplicate = False
        for previous in seen:
            if normalized in previous or previous in normalized:
                shorter, longer = min(len(normalized), len(previous)), max(len(normalized), len(previous))
                if longer and shorter / longer > 0.70:
                    duplicate = True
                    break
        if duplicate:
            continue
        seen.add(normalized)
        sections.append(value)
    return "\n\n".join(sections)[:MAX_ARTICLE_CHARACTERS]


def remove_greeting(text):
    text = str(text or "").strip()
    patterns = [r"^\s*नमस्कार[।,!:\-\s]*", r"^\s*नमस्ते[।,!:\-\s]*", r"^\s*हेलो[।,!:\-\s]*", r"^\s*स्वागत है[।,!:\-\s]*", r"^\s*THRAANSH में आपका स्वागत है[।,!:\-\s]*", r"^\s*थ्रांश में आपका स्वागत है[।,!:\-\s]*"]
    for pattern in patterns:
        text = re.sub(pattern, "", text, count=1, flags=re.IGNORECASE)
    return text.strip()


def word_count(text):
    return len(clean_text(text).split())


def split_sentences(text):
    text = clean_text(text)
    if not text:
        return []
    return [x.strip() for x in re.split(r"(?<=[।.!?])\s+", text) if x.strip()]


def normalize_for_similarity(text):
    text = clean_text(text).lower()
    text = re.sub(r"[^\w\u0900-\u097F\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def repetition_report(text, threshold=REPETITION_WARNING_THRESHOLD):
    sentences = split_sentences(text)
    duplicates = []
    for i in range(len(sentences)):
        first = normalize_for_similarity(sentences[i])
        if len(first.split()) < 7:
            continue
        for j in range(i + 1, len(sentences)):
            second = normalize_for_similarity(sentences[j])
            if len(second.split()) < 7:
                continue
            similarity = SequenceMatcher(None, first, second).ratio()
            if similarity >= threshold:
                duplicates.append({"first_index": i, "second_index": j, "similarity": round(similarity, 3)})
    return duplicates


def remove_near_exact_duplicates_locally(text):
    kept = []
    for sentence in split_sentences(text):
        normalized = normalize_for_similarity(sentence)
        if len(normalized.split()) < 7:
            kept.append(sentence)
            continue
        duplicate = False
        for previous in kept:
            p = normalize_for_similarity(previous)
            if len(p.split()) >= 7 and SequenceMatcher(None, normalized, p).ratio() >= NEAR_EXACT_DUPLICATE_THRESHOLD:
                duplicate = True
                break
        if not duplicate:
            kept.append(sentence)
    return " ".join(kept).strip()


def parse_iso_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=IST)
        return parsed
    except Exception:
        return None


def next_free_tier_daily_reset():
    now_pt = datetime.now(PACIFIC)
    tomorrow = (now_pt + timedelta(days=1)).date()
    reset_pt = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 5, tzinfo=PACIFIC)
    return reset_pt.astimezone(IST)


def quota_wait_active(article):
    retry_at = parse_iso_datetime(article.get("gemini_retry_not_before"))
    if not retry_at:
        return False, None
    return datetime.now(retry_at.tzinfo or IST) < retry_at, retry_at


def classify_quota_error(error):
    text = str(error)
    is_429 = "429" in text or "RESOURCE_EXHAUSTED" in text.upper()
    daily_markers = ["GenerateRequestsPerDayPerProjectPerModel-FreeTier", "generate_content_free_tier_requests", "Quota exceeded for metric"]
    is_daily = is_429 and any(marker.lower() in text.lower() for marker in daily_markers)
    return is_429, is_daily


def build_prompt(article):
    title = clean_text(article.get("title"))
    body = get_article_body(article)
    publisher = clean_text(article.get("publisher"))
    category = clean_text(article.get("category_slug") or article.get("category"))
    return f"""
You are the senior Hindi news presenter and final factual editor for THRAANSH.
You have ONE generation pass only. Return the final publish-ready narration in this single response.

PRIMARY RULE: Tell the COMPLETE AVAILABLE STORY exactly ONCE. Information density is more important than duration.
Use every important VERIFIED fact from the supplied source, but never repeat a fact merely to make the narration longer.

STRICT ANTI-REPETITION:
- do not repeat the headline later
- do not repeat what happened in different words
- do not repeat the same death, injury, arrest, count or location detail
- do not repeat the same quote in paraphrased form
- do not repeat background
- do not create an end recap
- do not pad a short article
- every new sentence must add a new factual detail
Before answering, silently remove any sentence that communicates information the viewer has already heard.

ACCURACY:
Use ONLY the supplied source. Never invent dates, numbers, names, quotes, causes, motives, reactions, police statements, court statements, government statements, casualties, financial figures, statistics or investigation findings.
Preserve allegation and attribution language accurately. Do not convert allegations into established facts.

LENGTH:
Preferred length is roughly {PREFERRED_MIN_WORDS}-{PREFERRED_MAX_WORDS} words ONLY when the source genuinely supports that much unique information.
If the source is shorter, finish early. A factual 60-90 second report is better than a padded 2-minute report.

STYLE:
- natural spoken Hindi for an Indian digital news presenter
- start directly with the news
- no greeting or welcome line
- clear professional sentences
- proper nouns and common technology/business/sports terms may remain English
- no sensationalism

FLOW WHEN AVAILABLE:
main development -> core verified facts -> sequence -> official response/additional details -> useful background -> latest position -> short natural close.

OUTPUT: Return ONLY the final Hindi narration. No markdown, headings, bullets, notes, explanation, word count or duration.

TITLE: {title}
CATEGORY: {category}
PUBLISHER: {publisher}
FULL AVAILABLE ARTICLE MATERIAL:
{body}
"""


def generate_script_one_call(client, article):
    """
    THRAANSH FREE AI ROUTER.

    Gemini is primary.
    Groq is automatic fallback when Gemini quota/rate/service
    problems prevent generation.
    """

    prompt = build_prompt(article)

    gemini_error = None

    # --------------------------------------------------------
    # PRIMARY: GEMINI
    # --------------------------------------------------------

    if client is not None and GEMINI_API_KEY:

        try:

            print(
                "[AI] Trying Gemini primary..."
            )

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )

            if not response.text:
                raise RuntimeError(
                    "Gemini returned an empty Hindi script."
                )

            narration = remove_greeting(
                response.text
            )

            if not narration:
                raise RuntimeError(
                    "Hindi narration became empty after cleaning."
                )

            print(
                "[AI] Gemini narration successful."
            )

            return narration

        except Exception as error:

            gemini_error = error

            print()
            print(
                "[AI] Gemini unavailable/quota/error:"
            )
            print(
                str(error)[:800]
            )

            if not GROQ_API_KEY:
                raise

            print()
            print(
                "[AI] Switching automatically to Groq FREE fallback..."
            )

    # --------------------------------------------------------
    # FALLBACK: GROQ
    # --------------------------------------------------------

    if not GROQ_API_KEY:

        if gemini_error:
            raise gemini_error

        raise RuntimeError(
            "Neither Gemini nor Groq API is available."
        )

    groq_client = Groq(
        api_key=GROQ_API_KEY
    )

    completion = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Hindi news script writer for "
                    "THRAANSH. Follow the supplied instructions "
                    "strictly. Return only the requested final "
                    "Hindi narration."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.2,
    )

    if (
        not completion.choices
        or not completion.choices[0].message.content
    ):
        raise RuntimeError(
            "Groq returned an empty Hindi script."
        )

    narration = remove_greeting(
        completion.choices[0].message.content
    )

    if not narration:
        raise RuntimeError(
            "Groq Hindi narration became empty after cleaning."
        )

    print(
        "[AI] Groq fallback narration successful."
    )

    return narration


def save_success(data, article, narration, initial_count, final_duplicates):
    final_count = word_count(narration)
    for key in ("hindi_script", "narration_script", "script", "presenter_script", "narration_text"):
        article[key] = narration
    article["script_language"] = "hi-IN"
    article["script_style"] = SCRIPT_VERSION
    article["script_generation_mode"] = "FREE_TIER_SINGLE_GEMINI_CALL"
    article["script_gemini_calls"] = 1
    article["script_gemini_max_calls"] = 1
    article["script_initial_word_count"] = initial_count
    article["presenter_greeting_enabled"] = False
    article["target_video_min_seconds"] = TARGET_MIN_SECONDS
    article["target_video_preferred_seconds"] = TARGET_PREFERRED_SECONDS
    article["target_video_max_seconds"] = TARGET_MAX_SECONDS
    article["script_word_count"] = final_count
    article["script_repetition_flags"] = len(final_duplicates)
    article["script_repetition_check"] = "PASS" if len(final_duplicates) < 3 else "FAIL"
    article["script_padding_enabled"] = False
    article["script_generated_at"] = datetime.now().astimezone().isoformat()
    article["gemini_quota_blocked_at"] = None
    article["gemini_retry_not_before"] = None
    article["status"] = "SCRIPT_READY"
    article["last_error"] = None
    article["updated_at"] = datetime.now().astimezone().isoformat()
    save_queue(data)


def main():
    header("THRAANSH HINDI NEWS PRESENTER V3 - FREE TIER SINGLE CALL")
    print("Gemini calls per article: MAXIMUM 1")
    print("Repeated scheduler runs reuse durable queue state.")
    print("Semantic second-pass Gemini review: OFF")
    print("Local near-exact duplicate cleanup: ON")
    print("Artificial padding: OFF")
    print()

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY missing from .env")

    data = load_queue()
    article = get_next_article(data)
    if article is None:
        print("No production-selected article is waiting for Hindi script generation.")
        return

    title = clean_text(article.get("title"))
    previous_status = clean_text(article.get("status")).upper()
    source_body = get_article_body(article)
    if not source_body:
        raise RuntimeError("Selected article has no usable source text.")

    print("Story:"); print(title); print()
    print("Available source characters:", len(source_body)); print()

    waiting, retry_at = quota_wait_active(article)

    if waiting:

        message = (
            "Gemini free-tier quota cooldown active until: "
            f"{retry_at.astimezone(IST).isoformat()}"
        )

        print(
            message
        )

        if GROQ_API_KEY:

            print(
                "[AI] Groq fallback is available. "
                "Pipeline will continue."
            )

        else:

            article["status"] = "HINDI_SCRIPT_QUOTA_WAIT"
            article["last_error"] = message
            article["updated_at"] = (
                datetime.now()
                .astimezone()
                .isoformat()
            )

            save_queue(
                data
            )

            raise RuntimeError(
                message
            )

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("PASS 1/1: Generating final factual Hindi narration...")
        narration = generate_script_one_call(client, article)
        initial_count = word_count(narration)
        print("Initial word count:", initial_count)

        narration = remove_near_exact_duplicates_locally(narration)
        narration = remove_greeting(narration)
        final_count = word_count(narration)
        final_duplicates = repetition_report(narration)
        print("Final word count:", final_count)
        print("Final repetition flags:", len(final_duplicates))

        if final_count < ABSOLUTE_MIN_WORDS:
            print("[WARNING] Source produced a shorter report. THRAANSH will not pad it.")
        if len(final_duplicates) >= 3:
            raise RuntimeError("Narration still contains excessive repetition. Free-tier mode will not spend a second Gemini request. Video generation blocked.")

        save_success(data, article, narration, initial_count, final_duplicates)
        header("[OK] HINDI SCRIPT READY - FREE TIER SINGLE CALL")
        print("Story:"); print(title); print()
        print("Previous status:", previous_status or "UNKNOWN")
        print("New status: SCRIPT_READY")
        print("Gemini calls used: 1")
        print("Final word count:", final_count)
        print("Repetition flags:", len(final_duplicates))
        print("Artificial padding: OFF")
        print("Greeting: OFF")
        print(); print("Narration preview:"); print()
        print(narration[:1200] + ("..." if len(narration) > 1200 else ""))
        print(); line()

    except Exception as error:
        is_429, is_daily = classify_quota_error(error)
        if is_daily:
            retry_at = next_free_tier_daily_reset()
            article["gemini_quota_blocked_at"] = datetime.now().astimezone().isoformat()
            article["gemini_retry_not_before"] = retry_at.isoformat()
            article["status"] = "HINDI_SCRIPT_QUOTA_WAIT"
            article["last_error"] = f"Gemini free-tier DAILY quota exhausted. Automatic API calls paused until {retry_at.astimezone(IST).isoformat()}."
            print(); print("[QUOTA] Gemini free-tier daily quota exhausted.")
            print("No more Gemini requests will be made for this article before:")
            print(retry_at.astimezone(IST).isoformat())
        elif is_429:
            retry_at = datetime.now(IST) + timedelta(minutes=2)
            article["gemini_quota_blocked_at"] = datetime.now().astimezone().isoformat()
            article["gemini_retry_not_before"] = retry_at.isoformat()
            article["status"] = "HINDI_SCRIPT_QUOTA_WAIT"
            article["last_error"] = f"Gemini temporary rate limit. Retry not before {retry_at.isoformat()}."
        else:
            article["last_error"] = str(error)
            article["status"] = "HINDI_SCRIPT_FAILED"
        article["updated_at"] = datetime.now().astimezone().isoformat()
        save_queue(data)
        raise


if __name__ == "__main__":
    main()
