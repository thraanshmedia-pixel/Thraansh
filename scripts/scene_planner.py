import json
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai


# ============================================================
# THRAANSH GLOBAL NEWS SCENE PLANNER
#
# PURPOSE
#
# Analyze the selected news story and create visual scenes
# that match the ACTUAL story.
#
# INDIA STORY -> INDIA VISUALS
# NEPAL STORY -> NEPAL VISUALS
# USA STORY   -> USA VISUALS
# UK STORY    -> UK VISUALS
#
# PEOPLE:
# Search actual named people first.
#
# SPORTS:
# Search actual player/team/event/stadium.
#
# NEVER:
# Random people
# Generic unrelated presenters
# Foreign footage for unrelated countries
# Repeated stock people
# ============================================================


PROJECT_FOLDER = Path(__file__).resolve().parents[1]

QUEUE_FILE = (
    PROJECT_FOLDER
    / "data"
    / "article_queue.json"
)

load_dotenv(
    PROJECT_FOLDER
    / ".env"
)


# ============================================================
# GEMINI CONFIGURATION
# ============================================================

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    ""
).strip()

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.6-flash"
).strip()


# ============================================================
# SETTINGS
# ============================================================

DEFAULT_SCENE_COUNT = 12

MAX_ARTICLE_CHARACTERS = 10000


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    return " ".join(
        str(value).replace(
            "\r",
            " "
        ).replace(
            "\n",
            " "
        ).split()
    ).strip()


# ============================================================
# LOAD QUEUE
# ============================================================

def load_queue():

    if not QUEUE_FILE.exists():

        raise RuntimeError(
            f"Queue file not found: {QUEUE_FILE}"
        )

    with open(
        QUEUE_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    if not isinstance(
        data,
        list
    ):

        raise RuntimeError(
            "article_queue.json must contain a list."
        )

    return data


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
# ARTICLE BODY
# ============================================================

def get_body(article):

    fields = [
        "content",
        "article_text",
        "description",
        "teaser",
        "summary",
        "excerpt",
    ]

    for field in fields:

        value = clean_text(
            article.get(
                field
            )
        )

        if value:
            return value

    return ""


# ============================================================
# FIND ARTICLE
# ============================================================

def get_next_article(queue):

    for article in queue:

        # ----------------------------------------------------
        # Prefer current production selection
        # ----------------------------------------------------

        if not article.get(
            "production_selected"
        ):

            continue

        status = clean_text(
            article.get(
                "status"
            )
        ).upper()

        # ----------------------------------------------------
        # Allow retry
        # ----------------------------------------------------

        if status not in {
            "VOICE_READY",
            "SCENE_PLAN_FAILED"
        }:

            continue

        # ----------------------------------------------------
        # Hindi narration must exist
        # ----------------------------------------------------

        hindi_script = clean_text(
            article.get(
                "hindi_script"
            )
            or article.get(
                "narration_script"
            )
        )

        if not hindi_script:
            continue

        return article

    return None


# ============================================================
# REMOVE MARKDOWN FROM GEMINI RESPONSE
# ============================================================

def clean_json_response(text):

    text = str(
        text or ""
    ).strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    return text.strip()


# ============================================================
# BUILD SCENE PLANNING PROMPT
# ============================================================

def build_prompt(article):

    title = clean_text(
        article.get(
            "title"
        )
    )

    body = get_body(
        article
    )

    hindi_script = clean_text(
        article.get(
            "hindi_script"
        )
        or article.get(
            "narration_script"
        )
    )

    category = clean_text(
        article.get(
            "category_slug"
        )
        or article.get(
            "category"
        )
    )

    publisher = clean_text(
        article.get(
            "publisher"
        )
    )

    body = body[
        :MAX_ARTICLE_CHARACTERS
    ]

    return f"""
You are the visual editor for THRAANSH, a global news video platform.

Analyze the following news story.

TITLE:
{title}

CATEGORY:
{category}

PUBLISHER:
{publisher}

ARTICLE:
{body}

HINDI NARRATION:
{hindi_script}


YOUR JOB:

Create a factual visual plan for this exact news story.

The most important requirement is:

THE VISUALS MUST MATCH THE REAL STORY.


============================================================
COUNTRY RULE
============================================================

Determine where the actual news event is happening.

Examples:

India story:
use Indian people, locations, institutions and events.

Nepal story:
use Nepal locations, Nepal event visuals and relevant
organisations.

United States story:
use actual US locations, institutions and people.

United Kingdom story:
use actual UK locations, institutions and people.

International diplomatic story:
use the actual countries and organisations involved.


DO NOT automatically use Indian footage.

DO NOT automatically use American footage.

The story decides the country.


============================================================
PEOPLE RULE
============================================================

If the article is about a named person:

search for that ACTUAL PERSON.

For example:

Virat Kohli
Narendra Modi
Donald Trump
Shubman Gill
a named actor
a named minister
a named athlete

Do not replace that person with a random man or woman.


============================================================
SPORTS RULE
============================================================

For sports stories identify:

player
team
country
tournament
stadium
sport
organisation

Example:

If the story is about Indian cricket:

search:
actual Indian player
Team India
BCCI
actual tournament
actual stadium

If the story is about English football:

search:
actual footballer
actual club
actual stadium
actual competition

Do not show cricket footage for football.

Do not show unrelated athletes.


============================================================
DISASTER / WEATHER RULE
============================================================

Identify:

country
city
region
disaster type

For example:

Nepal flood:
Nepal flood
Nepal mountains
actual affected region
Nepal rescue operations

Do not use random flooding from another country
unless there is no better licensed contextual media,
and never label it as footage of the actual event.


============================================================
POLITICS RULE
============================================================

Identify:

actual politician
actual government
actual parliament
actual city
actual organisation

Never substitute politicians from another country.


============================================================
BUSINESS RULE
============================================================

Identify:

actual company
actual CEO when relevant
actual headquarters
actual stock exchange
actual product
actual country


============================================================
TECHNOLOGY RULE
============================================================

Identify:

actual company
actual technology
actual product
actual facility
actual country


============================================================
ENTERTAINMENT RULE
============================================================

Identify:

actual actor
singer
film
event
venue
country

Never use a random celebrity.


============================================================
VISUAL SEARCH RULES
============================================================

Each scene needs 3 search queries.

Search queries must be short and suitable for
Wikimedia Commons.

GOOD:

"Narendra Modi New Delhi"

"Indian Parliament New Delhi"

"Virat Kohli India cricket"

"Kathmandu Nepal"

"Nepal Himalaya glacier"

"ISRO satellite India"

"Donald Trump White House"

"Manchester United Old Trafford"


BAD:

"breaking news"

"news footage"

"important event"

"people talking"

"man speaking"

"woman news"

"office people"

"business people"

"generic presenter"


============================================================
SCENE DIVERSITY
============================================================

Create exactly {DEFAULT_SCENE_COUNT} scenes.

Do not create six searches for the same photograph.

Use a mixture of:

actual person
actual location
actual organisation
actual event
relevant building
relevant contextual imagery


============================================================
ACCURACY
============================================================

Never invent:

people
locations
companies
teams
events
countries
organisations

If something cannot be determined,
use an empty string.


============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

No markdown.

No explanation.

Use EXACTLY this structure:

{{
  "story_country": "",
  "story_city": "",
  "story_region": "",
  "story_category": "",
  "primary_person": "",
  "secondary_people": [],
  "primary_organisation": "",
  "secondary_organisations": [],
  "sports_team": "",
  "sports_event": "",
  "story_event": "",
  "visual_context": "",
  "scenes": [
    {{
      "scene_number": 1,
      "purpose": "",
      "country": "",
      "location": "",
      "person": "",
      "organisation": "",
      "search_queries": [
        "",
        "",
        ""
      ]
    }}
  ]
}}
"""


# ============================================================
# GENERATE PLAN
# ============================================================

def generate_scene_plan(
    client,
    article
):

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=build_prompt(
            article
        )
    )

    if not response.text:

        raise RuntimeError(
            "Gemini returned an empty scene plan."
        )

    raw = clean_json_response(
        response.text
    )

    try:

        plan = json.loads(
            raw
        )

    except json.JSONDecodeError as error:

        print()
        print(
            "RAW GEMINI RESPONSE:"
        )

        print(
            raw
        )

        raise RuntimeError(
            f"Gemini returned invalid JSON: {error}"
        )

    return plan


# ============================================================
# VALIDATE PLAN
# ============================================================

def validate_plan(plan):

    if not isinstance(
        plan,
        dict
    ):

        raise RuntimeError(
            "Scene plan is not a JSON object."
        )

    scenes = plan.get(
        "scenes"
    )

    if not isinstance(
        scenes,
        list
    ):

        raise RuntimeError(
            "Scene plan does not contain scenes."
        )

    if len(
        scenes
    ) < 3:

        raise RuntimeError(
            "Scene plan contains fewer than 3 scenes."
        )

    cleaned_scenes = []

    for index, scene in enumerate(
        scenes[:DEFAULT_SCENE_COUNT],
        start=1
    ):

        if not isinstance(
            scene,
            dict
        ):

            continue

        queries = scene.get(
            "search_queries",
            []
        )

        if not isinstance(
            queries,
            list
        ):

            queries = []

        queries = [
            clean_text(query)
            for query in queries
            if clean_text(query)
        ]

        # Remove duplicates while preserving order.
        queries = list(
            dict.fromkeys(
                queries
            )
        )

        if not queries:

            continue

        cleaned_scene = {

            "scene_number":
                index,

            "purpose":
                clean_text(
                    scene.get(
                        "purpose"
                    )
                ),

            "country":
                clean_text(
                    scene.get(
                        "country"
                    )
                ),

            "location":
                clean_text(
                    scene.get(
                        "location"
                    )
                ),

            "person":
                clean_text(
                    scene.get(
                        "person"
                    )
                ),

            "organisation":
                clean_text(
                    scene.get(
                        "organisation"
                    )
                ),

            "search_queries":
                queries[:3],

            "status":
                "PENDING",

            "media_type":
                None,

            "footage_file":
                None,

            "media_url":
                None,

            "media_title":
                None,

            "license":
                None,
        }

        cleaned_scenes.append(
            cleaned_scene
        )

    if len(
        cleaned_scenes
    ) < 3:

        raise RuntimeError(
            "Not enough valid scenes after validation."
        )

    return cleaned_scenes


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 76)

    print(
        "THRAANSH GLOBAL STORY-AWARE "
        "SCENE PLANNER"
    )

    print("=" * 76)

    print()
    print(
        "Country policy: STORY SPECIFIC ✓"
    )

    print(
        "Named people: EXACT PERSON FIRST ✓"
    )

    print(
        "Sports: PLAYER + TEAM + EVENT ✓"
    )

    print(
        "Random people: NOT ALLOWED ✓"
    )

    print(
        "Generic foreign fallback: NOT ALLOWED ✓"
    )

    # ========================================================
    # GEMINI CHECK
    # ========================================================

    if not GEMINI_API_KEY:

        print()
        print(
            "ERROR:"
        )

        print(
            "GEMINI_API_KEY missing from .env"
        )

        return

    # ========================================================
    # LOAD QUEUE
    # ========================================================

    try:

        queue = load_queue()

    except Exception as error:

        print()
        print(
            "QUEUE ERROR:"
        )

        print(
            error
        )

        return

    article = get_next_article(
        queue
    )

    if article is None:

        print()
        print(
            "No selected VOICE_READY article "
            "is waiting for scene planning."
        )

        return

    title = clean_text(
        article.get(
            "title"
        )
    )

    previous_status = clean_text(
        article.get(
            "status"
        )
    ).upper()

    print()
    print(
        "ARTICLE:"
    )

    print(
        title
    )

    # ========================================================
    # GENERATE
    # ========================================================

    try:

        client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        print()
        print(
            "Analyzing real story context..."
        )

        plan = generate_scene_plan(
            client,
            article
        )

        scenes = validate_plan(
            plan
        )

        # ====================================================
        # STORY METADATA
        # ====================================================

        article[
            "story_country"
        ] = clean_text(
            plan.get(
                "story_country"
            )
        )

        article[
            "story_city"
        ] = clean_text(
            plan.get(
                "story_city"
            )
        )

        article[
            "story_region"
        ] = clean_text(
            plan.get(
                "story_region"
            )
        )

        article[
            "story_category_detected"
        ] = clean_text(
            plan.get(
                "story_category"
            )
        )

        article[
            "primary_person"
        ] = clean_text(
            plan.get(
                "primary_person"
            )
        )

        article[
            "secondary_people"
        ] = plan.get(
            "secondary_people",
            []
        )

        article[
            "primary_organisation"
        ] = clean_text(
            plan.get(
                "primary_organisation"
            )
        )

        article[
            "secondary_organisations"
        ] = plan.get(
            "secondary_organisations",
            []
        )

        article[
            "sports_team"
        ] = clean_text(
            plan.get(
                "sports_team"
            )
        )

        article[
            "sports_event"
        ] = clean_text(
            plan.get(
                "sports_event"
            )
        )

        article[
            "story_event"
        ] = clean_text(
            plan.get(
                "story_event"
            )
        )

        article[
            "visual_context"
        ] = clean_text(
            plan.get(
                "visual_context"
            )
        )

        # ====================================================
        # SCENES
        # ====================================================

        article[
            "scene_plan"
        ] = scenes

        article[
            "scene_count"
        ] = len(
            scenes
        )

        article[
            "scene_plan_version"
        ] = "GLOBAL_STORY_AWARE_V1"

        article[
            "scene_plan_generated_at"
        ] = datetime.now().isoformat()

        article[
            "status"
        ] = "SCENE_PLAN_READY"

        article[
            "last_error"
        ] = None

        article[
            "updated_at"
        ] = datetime.now().isoformat()

        save_queue(
            queue
        )

        # ====================================================
        # OUTPUT
        # ====================================================

        print()
        print("=" * 76)

        print(
            "STORY ANALYSIS"
        )

        print("=" * 76)

        print()
        print(
            "Country:",
            article[
                "story_country"
            ]
            or "Unknown"
        )

        print(
            "City:",
            article[
                "story_city"
            ]
            or "Unknown"
        )

        print(
            "Category:",
            article[
                "story_category_detected"
            ]
            or "Unknown"
        )

        print(
            "Primary person:",
            article[
                "primary_person"
            ]
            or "None"
        )

        print(
            "Organisation:",
            article[
                "primary_organisation"
            ]
            or "None"
        )

        if article[
            "sports_team"
        ]:

            print(
                "Sports team:",
                article[
                    "sports_team"
                ]
            )

        if article[
            "sports_event"
        ]:

            print(
                "Sports event:",
                article[
                    "sports_event"
                ]
            )

        print()
        print("=" * 76)

        print(
            "SCENE SEARCH PLAN"
        )

        print("=" * 76)

        for scene in scenes:

            print()
            print(
                f"SCENE "
                f"{scene['scene_number']}"
            )

            print(
                "Purpose:",
                scene[
                    "purpose"
                ]
            )

            print(
                "Country:",
                scene[
                    "country"
                ]
                or article[
                    "story_country"
                ]
            )

            if scene[
                "person"
            ]:

                print(
                    "Person:",
                    scene[
                        "person"
                    ]
                )

            print(
                "Search queries:"
            )

            for query in scene[
                "search_queries"
            ]:

                print(
                    " -",
                    query
                )

        print()
        print("=" * 76)

        print(
            "SCENE PLAN READY"
        )

        print("=" * 76)

        print()
        print(
            "Status:"
        )

        print(
            f"{previous_status} "
            "-> SCENE_PLAN_READY"
        )

        print()
        print(
            "Next stage:"
        )

        print(
            "Download story-specific "
            "licensed footage/images."
        )

    except Exception as error:

        article[
            "status"
        ] = "SCENE_PLAN_FAILED"

        article[
            "last_error"
        ] = str(
            error
        )

        article[
            "scene_plan_retry_count"
        ] = (
            article.get(
                "scene_plan_retry_count",
                0
            )
            + 1
        )

        article[
            "updated_at"
        ] = datetime.now().isoformat()

        save_queue(
            queue
        )

        print()
        print("=" * 76)

        print(
            "SCENE PLANNING FAILED"
        )

        print("=" * 76)

        print()
        print(
            "Error:"
        )

        print(
            error
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()