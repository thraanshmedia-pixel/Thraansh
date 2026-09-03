import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

import edge_tts


# ============================================================
# THRAANSH GLOBAL HINDI NEWS VOICE GENERATOR
#
# NEWS:
# India + International
#
# NARRATION:
# Easy Hindi
#
# VOICE:
# hi-IN-MadhurNeural
#
# INPUT:
# production_selected = True
# status = SCRIPT_READY / VOICE_FAILED
#
# OUTPUT:
# voice_file
# audio_file
# voice_status = READY
# status = VOICE_READY
# ============================================================


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_FOLDER = Path(__file__).resolve().parents[1]

QUEUE_FILE = (
    PROJECT_FOLDER
    / "data"
    / "article_queue.json"
)

AUDIO_FOLDER = (
    PROJECT_FOLDER
    / "audio"
)

AUDIO_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# VOICE SETTINGS
# ============================================================

VOICE_NAME = "hi-IN-MadhurNeural"

VOICE_LANGUAGE = "hi-IN"

VOICE_RATE = "+18%"

VOICE_PITCH = "+0Hz"

VOICE_VOLUME = "+0%"


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def safe_filename(value):

    value = clean_text(
        value
    )

    value = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        value
    )

    value = re.sub(
        r"\s+",
        "_",
        value
    )

    value = value.strip(
        "._"
    )

    if not value:
        value = "THRAANSH_NEWS"

    return value[:120]


# ============================================================
# LOAD QUEUE
# ============================================================

def load_queue():

    if not QUEUE_FILE.exists():

        raise RuntimeError(
            f"Queue file not found: "
            f"{QUEUE_FILE}"
        )

    with open(
        QUEUE_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(
            file
        )

    if not isinstance(
        data,
        list
    ):

        raise RuntimeError(
            "article_queue.json "
            "must contain a list."
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
# GET HINDI SCRIPT
# ============================================================

def get_hindi_script(article):

    possible_fields = [
        "hindi_script",
        "narration_script",
        "script",
    ]

    for field in possible_fields:

        value = clean_text(
            article.get(
                field
            )
        )

        if value:
            return value

    return ""


# ============================================================
# FIND NEXT ARTICLE
# ============================================================

def get_next_article(queue):

    skipped_not_selected = 0
    skipped_wrong_status = 0
    skipped_no_script = 0
    skipped_existing_voice = 0

    # ========================================================
    # CURRENT SELECTED STORY ONLY
    # ========================================================

    for article in queue:

        if not article.get(
            "production_selected"
        ):

            skipped_not_selected += 1
            continue

        status = clean_text(
            article.get(
                "status"
            )
        ).upper()

        if status not in {
            "SCRIPT_READY",
            "VOICE_FAILED",
        }:

            skipped_wrong_status += 1
            continue

        script = get_hindi_script(
            article
        )

        if not script:

            skipped_no_script += 1
            continue

        existing_voice = clean_text(
            article.get(
                "voice_file"
            )
            or article.get(
                "audio_file"
            )
        )

        if existing_voice:

            existing_path = Path(
                existing_voice
            )

            if existing_path.exists():

                skipped_existing_voice += 1
                continue

        return article

    print()
    print(
        "Skipped not-selected records:",
        skipped_not_selected
    )

    print(
        "Skipped wrong-status records:",
        skipped_wrong_status
    )

    print(
        "Skipped records without Hindi script:",
        skipped_no_script
    )

    print(
        "Skipped records with existing voice:",
        skipped_existing_voice
    )

    return None


# ============================================================
# GENERATE SPEECH
# ============================================================

async def generate_voice(
    script,
    output_file
):

    communicator = edge_tts.Communicate(
        text=script,
        voice=VOICE_NAME,
        rate=VOICE_RATE,
        pitch=VOICE_PITCH,
        volume=VOICE_VOLUME
    )

    await communicator.save(
        str(output_file)
    )


# ============================================================
# VALIDATE AUDIO
# ============================================================

def validate_audio_file(path):

    if not path.exists():

        raise RuntimeError(
            "Voice file was not created."
        )

    size = path.stat().st_size

    if size < 5000:

        raise RuntimeError(
            "Generated voice file "
            "is unexpectedly small."
        )

    return True


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 74)

    print(
        "THRAANSH GLOBAL HINDI "
        "NEWS VOICE GENERATOR"
    )

    print("=" * 74)

    print()
    print(
        "News policy:"
    )

    print(
        "INDIA + INTERNATIONAL âœ“"
    )

    print()
    print(
        "Voice:",
        VOICE_NAME
    )

    print(
        "Language: Easy Hindi âœ“"
    )

    print(
        "Country restriction: NONE âœ“"
    )

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

    # ========================================================
    # FIND ARTICLE
    # ========================================================

    article = get_next_article(
        queue
    )

    if article is None:

        print()
        print(
            "No selected SCRIPT_READY "
            "article is waiting for voice."
        )

        return

    # ========================================================
    # ARTICLE DATA
    # ========================================================

    title = clean_text(
        article.get(
            "title"
        )
    )

    script = get_hindi_script(
        article
    )

    previous_status = clean_text(
        article.get(
            "status"
        )
    ).upper()

    print()
    print("=" * 74)

    print(
        "SELECTED STORY"
    )

    print("=" * 74)

    print()
    print(
        title
    )

    print()
    print(
        "Script characters:",
        len(
            script
        )
    )

    # ========================================================
    # OUTPUT FILE
    # ========================================================

    output_name = (
        safe_filename(
            title
        )
        + ".mp3"
    )

    output_file = (
        AUDIO_FOLDER
        / output_name
    )

    # ========================================================
    # GENERATE VOICE
    # ========================================================

    try:

        print()
        print(
            "Generating Hindi narration..."
        )

        asyncio.run(
            generate_voice(
                script,
                output_file
            )
        )

        validate_audio_file(
            output_file
        )

        # ====================================================
        # SAVE SUCCESS
        # ====================================================

        article[
            "voice_file"
        ] = str(
            output_file
        )

        article[
            "audio_file"
        ] = str(
            output_file
        )

        article[
            "narration_file"
        ] = str(
            output_file
        )

        article[
            "voice_name"
        ] = VOICE_NAME

        article[
            "voice_language"
        ] = VOICE_LANGUAGE

        article[
            "voice_rate"
        ] = VOICE_RATE

        article[
            "voice_pitch"
        ] = VOICE_PITCH

        article[
            "voice_volume"
        ] = VOICE_VOLUME

        article[
            "voice_status"
        ] = "READY"

        article[
            "status"
        ] = "VOICE_READY"

        article[
            "last_error"
        ] = None

        article[
            "voice_generated_at"
        ] = datetime.now().isoformat()

        article[
            "updated_at"
        ] = datetime.now().isoformat()

        save_queue(
            queue
        )

        # ====================================================
        # SUCCESS OUTPUT
        # ====================================================

        size_mb = (
            output_file.stat().st_size
            / 1024
            / 1024
        )

        print()
        print("=" * 74)

        print(
            "HINDI VOICE READY"
        )

        print("=" * 74)

        print()
        print(
            "Voice file:"
        )

        print(
            output_file
        )

        print()
        print(
            f"Size: "
            f"{size_mb:.2f} MB"
        )

        print()
        print(
            "Easy Hindi âœ“"
        )

        print(
            "India news supported âœ“"
        )

        print(
            "International news supported âœ“"
        )

        print(
            "Original story country preserved âœ“"
        )

        print()
        print(
            "Status:"
        )

        print(
            f"{previous_status} "
            "-> VOICE_READY"
        )

        print()
        print(
            "Next:"
        )

        print(
            "Story-aware scene planning."
        )

    except Exception as error:

        # ====================================================
        # FAILURE
        # ====================================================

        article[
            "status"
        ] = "VOICE_FAILED"

        article[
            "voice_status"
        ] = "FAILED"

        article[
            "last_error"
        ] = str(
            error
        )

        article[
            "voice_retry_count"
        ] = (
            article.get(
                "voice_retry_count",
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
        print("=" * 74)

        print(
            "VOICE GENERATION FAILED"
        )

        print("=" * 74)

        print()
        print(
            "Error:"
        )

        print(
            error
        )

        # Propagate TTS failure to the orchestration layer.
        # This prevents scene/video generation from continuing
        # when no valid narration MP3 exists.
        raise


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
