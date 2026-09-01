import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai


# ============================================================
# THRAANSH HINDI PRESENTER V2
# ============================================================
#
# CHANGES:
#
# âœ“ No "Namaste THRAANSH"
# âœ“ No repetitive welcome message
# âœ“ No "aaj hum baat karenge"
# âœ“ Starts immediately with the news
# âœ“ Short, energetic news sentences
# âœ“ Easy conversational Hindi
# âœ“ Facts only from source article
# âœ“ Greeting cleaner as second protection
# âœ“ Ready for faster TTS narration
#
# OUTPUT STATUS:
# SCRIPT_READY
#
# ============================================================


# ============================================================
# PROJECT
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

QUEUE_FILE = (
    PROJECT_ROOT
    / "data"
    / "article_queue.json"
)

ENV_FILE = (
    PROJECT_ROOT
    / ".env"
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv(
    ENV_FILE,
    override=True
)

GEMINI_API_KEY = str(
    os.getenv(
        "GEMINI_API_KEY",
        ""
    )
).strip()

GEMINI_MODEL = str(
    os.getenv(
        "GEMINI_MODEL",
        "gemini-3.6-flash"
    )
).strip()


# ============================================================
# DISPLAY
# ============================================================

def line():

    print(
        "=" * 72
    )


def header(text):

    print()
    line()
    print(text)
    line()
    print()


def fail(message):

    print()
    line()

    print(
        f"âŒ {message}"
    )

    line()

    sys.exit(1)


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    return (
        " ".join(
            str(value).split()
        )
        .strip()
    )


# ============================================================
# REMOVE AI MARKDOWN
# ============================================================

def clean_ai_output(text):

    text = clean_text(
        text
    )

    text = re.sub(
        r"^```(?:text|markdown|hindi)?",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```$",
        "",
        text
    )

    text = (
        text
        .replace(
            "**",
            ""
        )
        .replace(
            "__",
            ""
        )
        .strip()
    )

    return text


# ============================================================
# REMOVE REPETITIVE PRESENTER GREETINGS
# ============================================================

def remove_presenter_greeting(text):

    if not text:
        return ""

    text = text.strip()

    # --------------------------------------------------------
    # These are intentionally only beginning-of-script rules.
    # We do not remove words if legitimately used later.
    # --------------------------------------------------------

    patterns = [

        r"^\s*à¤¨à¤®à¤¸à¥à¤¤à¥‡\s+à¤¥à¥à¤°à¤¾à¤‚à¤¶\s*[,.!à¥¤:\-â€“â€”]*\s*",

        r"^\s*à¤¨à¤®à¤¸à¥à¤¤à¥‡\s+THRAANSH\s*[,.!à¥¤:\-â€“â€”]*\s*",

        r"^\s*à¤¨à¤®à¤¸à¥à¤•à¤¾à¤°\s+à¤¥à¥à¤°à¤¾à¤‚à¤¶\s*[,.!à¥¤:\-â€“â€”]*\s*",

        r"^\s*à¤¨à¤®à¤¸à¥à¤•à¤¾à¤°\s+THRAANSH\s*[,.!à¥¤:\-â€“â€”]*\s*",

        r"^\s*à¤¨à¤®à¤¸à¥à¤¤à¥‡\s*[,.!à¥¤:\-â€“â€”]*\s*",

        r"^\s*à¤¨à¤®à¤¸à¥à¤•à¤¾à¤°\s*[,.!à¥¤:\-â€“â€”]*\s*",

        (
            r"^\s*THRAANSH\s+à¤®à¥‡à¤‚\s+"
            r"à¤†à¤ªà¤•à¤¾\s+à¤¸à¥à¤µà¤¾à¤—à¤¤\s+à¤¹à¥ˆ\s*"
            r"[,.!à¥¤:\-â€“â€”]*\s*"
        ),

        (
            r"^\s*à¤¥à¥à¤°à¤¾à¤‚à¤¶\s+à¤®à¥‡à¤‚\s+"
            r"à¤†à¤ªà¤•à¤¾\s+à¤¸à¥à¤µà¤¾à¤—à¤¤\s+à¤¹à¥ˆ\s*"
            r"[,.!à¥¤:\-â€“â€”]*\s*"
        ),

        (
            r"^\s*THRAANSH\s+à¤ªà¤°\s+"
            r"à¤†à¤ªà¤•à¤¾\s+à¤¸à¥à¤µà¤¾à¤—à¤¤\s+à¤¹à¥ˆ\s*"
            r"[,.!à¥¤:\-â€“â€”]*\s*"
        ),

        (
            r"^\s*à¤†à¤œ\s+à¤¹à¤®\s+à¤¬à¤¾à¤¤\s+"
            r"à¤•à¤°à¥‡à¤‚à¤—à¥‡\s*[,.!à¥¤:\-â€“â€”]*\s*"
        ),

        (
            r"^\s*à¤†à¤œ\s+à¤¹à¤®\s+à¤œà¤¾à¤¨à¥‡à¤‚à¤—à¥‡\s*"
            r"[,.!à¥¤:\-â€“â€”]*\s*"
        ),

        (
            r"^\s*à¤‡à¤¸\s+à¤µà¥€à¤¡à¤¿à¤¯à¥‹\s+à¤®à¥‡à¤‚\s+"
            r"à¤¹à¤®\s+à¤œà¤¾à¤¨à¥‡à¤‚à¤—à¥‡\s*"
            r"[,.!à¥¤:\-â€“â€”]*\s*"
        ),

        (
            r"^\s*à¤‡à¤¸\s+à¤µà¥€à¤¡à¤¿à¤¯à¥‹\s+à¤®à¥‡à¤‚\s+"
            r"à¤¹à¤®\s+à¤¬à¤¾à¤¤\s+à¤•à¤°à¥‡à¤‚à¤—à¥‡\s*"
            r"[,.!à¥¤:\-â€“â€”]*\s*"
        ),

        (
            r"^\s*à¤†à¤ª\s+à¤¦à¥‡à¤–\s+à¤°à¤¹à¥‡\s+à¤¹à¥ˆà¤‚\s+"
            r"THRAANSH\s*[,.!à¥¤:\-â€“â€”]*\s*"
        ),

        (
            r"^\s*à¤†à¤ª\s+à¤¦à¥‡à¤–\s+à¤°à¤¹à¥‡\s+à¤¹à¥ˆà¤‚\s+"
            r"à¤¥à¥à¤°à¤¾à¤‚à¤¶\s*[,.!à¥¤:\-â€“â€”]*\s*"
        ),
    ]

    # Repeat because Gemini could combine:
    #
    # "Namaste. THRAANSH mein aapka swagat hai..."
    #
    # Removing only one expression would leave the next one.

    changed = True

    while changed:

        changed = False

        for pattern in patterns:

            cleaned = re.sub(
                pattern,
                "",
                text,
                count=1,
                flags=re.IGNORECASE
            ).strip()

            if cleaned != text:

                text = cleaned

                changed = True

    return text.strip()


# ============================================================
# QUEUE
# ============================================================

def load_queue():

    if not QUEUE_FILE.exists():

        fail(
            "article_queue.json not found:\n"
            f"{QUEUE_FILE}"
        )

    try:

        with open(
            QUEUE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(
                file
            )

    except Exception as error:

        fail(
            "Could not read article_queue.json:\n"
            f"{error}"
        )


def extract_articles(data):

    if isinstance(
        data,
        list
    ):

        return data

    if isinstance(
        data,
        dict
    ):

        for key in (
            "articles",
            "items",
            "queue",
            "news",
            "data",
        ):

            value = data.get(
                key
            )

            if isinstance(
                value,
                list
            ):

                return value

    fail(
        "Could not locate article list "
        "inside article_queue.json."
    )


def save_queue(data):

    try:

        with open(
            QUEUE_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )

    except Exception as error:

        fail(
            "Could not save article_queue.json:\n"
            f"{error}"
        )


# ============================================================
# CURRENT STORY
# ============================================================

def current_article(
    articles
):

    selected = []

    for article in articles:

        if not isinstance(
            article,
            dict
        ):

            continue

        if article.get(
            "production_selected"
        ) is True:

            selected.append(
                article
            )

    if not selected:

        fail(
            "No production_selected story found."
        )

    return selected[-1]


# ============================================================
# ARTICLE SOURCE TEXT
# ============================================================

def get_article_context(
    article
):

    title = clean_text(
        article.get(
            "title"
        )
    )

    teaser = clean_text(
        article.get(
            "teaser"
        )
    )

    summary = clean_text(
        article.get(
            "summary"
        )
    )

    description = clean_text(
        article.get(
            "description"
        )
    )

    content = clean_text(
        article.get(
            "content"
        )
    )

    article_text = clean_text(
        article.get(
            "article_text"
        )
    )

    publisher = clean_text(
        article.get(
            "publisher"
        )
    )

    country = clean_text(
        article.get(
            "story_country"
        )
    )

    category = clean_text(
        article.get(
            "category_slug"
        )
    )

    source_url = clean_text(
        article.get(
            "url"
        )
    )

    sections = [
        f"TITLE: {title}",
        f"PUBLISHER: {publisher}",
        f"COUNTRY: {country}",
        f"CATEGORY: {category}",
        f"TEASER: {teaser}",
        f"SUMMARY: {summary}",
        f"DESCRIPTION: {description}",
        f"ARTICLE TEXT: {article_text}",
        f"CONTENT: {content}",
        f"SOURCE URL: {source_url}",
    ]

    return "\n\n".join(
        sections
    )


# ============================================================
# GEMINI PROMPT
# ============================================================

def build_prompt(
    article
):

    source = get_article_context(
        article
    )

    return f"""
You are the Hindi news presenter and script writer for THRAANSH.

Create a professional Hindi narration script from the supplied news information.

CRITICAL PRESENTER RULES:

1. NEVER begin with:
   - Namaste
   - Namaskar
   - Namaste THRAANSH
   - Namaskar THRAANSH
   - THRAANSH mein aapka swagat hai
   - Aap dekh rahe hain THRAANSH
   - Aaj hum baat karenge
   - Aaj hum jaanenge
   - Is video mein hum jaanenge

2. DO NOT introduce the channel at the beginning.

3. START IMMEDIATELY WITH THE NEWS.

4. The first sentence must contain the strongest fact, event, number,
   development or headline from the story.

5. The first 5 seconds should make the viewer want to continue watching.

6. Use easy, natural, conversational Hindi understood across India.

7. Do not use unnecessarily difficult Hindi.

8. English names, companies, technology names, cities and common business
   terminology may remain in English when that sounds more natural.

9. Use short sentences.

10. Make the narration energetic and professional.

11. Avoid long introductions.

12. Avoid filler.

13. Avoid repeating the headline multiple times.

14. Avoid repeating the same information in different words.

15. Do not invent facts.

16. Do not make assumptions not present in the supplied source.

17. Do not add fake quotes.

18. Do not exaggerate.

19. If details are uncertain in the source, do not present them as confirmed.

20. Write for spoken narration, not for an article.

21. Do not include section headings such as:
    INTRO
    HOOK
    BODY
    CONCLUSION
    SCENE 1
    PRESENTER

22. Do not output Markdown.

23. Do not use bullet points.

24. Return only the narration that should actually be spoken.

25. THRAANSH can be mentioned naturally only once near the end if useful,
    but it is not compulsory.

ENDING STYLE:

Finish naturally in one or two short sentences.
Do not repeat a long channel promotion.
Do not say Namaste at the end.

SOURCE NEWS:

{source}

Now write the final Hindi spoken-news narration only.
""".strip()


# ============================================================
# GENERATE SCRIPT
# ============================================================

def generate_script(
    article
):

    if not GEMINI_API_KEY:

        fail(
            "GEMINI_API_KEY is missing from .env"
        )

    client = genai.Client(
        api_key=GEMINI_API_KEY
    )

    prompt = build_prompt(
        article
    )

    print(
        "Gemini model:"
    )

    print(
        GEMINI_MODEL
    )

    print()

    try:

        response = (
            client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )
        )

    except Exception as error:

        fail(
            "Gemini script generation failed:\n"
            f"{error}"
        )

    generated_text = clean_text(
        getattr(
            response,
            "text",
            ""
        )
    )

    if not generated_text:

        fail(
            "Gemini returned an empty Hindi script."
        )

    generated_text = clean_ai_output(
        generated_text
    )

    # --------------------------------------------------------
    # Fail-safe:
    # even if Gemini ignores the prompt, strip greetings.
    # --------------------------------------------------------

    generated_text = remove_presenter_greeting(
        generated_text
    )

    if len(
        generated_text
    ) < 80:

        fail(
            "Generated Hindi narration is unexpectedly short."
        )

    return generated_text


# ============================================================
# MAIN
# ============================================================

def main():

    header(
        "THRAANSH HINDI PRESENTER V2"
    )

    print(
        "Presenter style:"
    )

    print(
        "DIRECT NEWS START"
    )

    print()

    print(
        "Opening greeting:"
    )

    print(
        "DISABLED"
    )

    print()

    data = load_queue()

    articles = extract_articles(
        data
    )

    article = current_article(
        articles
    )

    title = clean_text(
        article.get(
            "title"
        )
    )

    print(
        "Selected story:"
    )

    print(
        title
    )

    print()

    previous_status = clean_text(
        article.get(
            "status"
        )
    )

    try:

        narration = generate_script(
            article
        )

        # ----------------------------------------------------
        # Save using primary field + compatibility aliases.
        # ----------------------------------------------------

        article[
            "hindi_script"
        ] = narration

        article[
            "presenter_script"
        ] = narration

        article[
            "narration_text"
        ] = narration

        article[
            "script_language"
        ] = "hi-IN"

        article[
            "script_style"
        ] = "DIRECT_NEWS_FAST"

        article[
            "presenter_greeting_enabled"
        ] = False

        article[
            "script_generated_at"
        ] = (
            datetime.now()
            .astimezone()
            .isoformat()
        )

        article[
            "status"
        ] = "SCRIPT_READY"

        article[
            "last_error"
        ] = None

        article[
            "updated_at"
        ] = (
            datetime.now()
            .astimezone()
            .isoformat()
        )

        save_queue(
            data
        )

        header(
            "âœ… HINDI SCRIPT READY"
        )

        print(
            "Story:"
        )

        print(
            title
        )

        print()

        print(
            "Previous status:"
        )

        print(
            previous_status
            or "UNKNOWN"
        )

        print()

        print(
            "New status:"
        )

        print(
            "SCRIPT_READY"
        )

        print()

        print(
            "Greeting:"
        )

        print(
            "REMOVED âœ“"
        )

        print()

        print(
            "Narration preview:"
        )

        print()

        preview = narration[:900]

        print(
            preview
        )

        if len(
            narration
        ) > 900:

            print(
                "..."
            )

        print()

        line()

    except Exception as error:

        article[
            "last_error"
        ] = str(
            error
        )

        article[
            "status"
        ] = "HINDI_SCRIPT_FAILED"

        article[
            "updated_at"
        ] = (
            datetime.now()
            .astimezone()
            .isoformat()
        )

        save_queue(
            data
        )

        raise


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
