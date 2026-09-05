from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import imageio_ffmpeg
from PIL import Image
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate


# ============================================================
# THRAANSH ULTRA-FAST MULTI-SCENE NEWS VIDEO RENDERER
#
# OUTPUT
# ------
# 1280x720
# 24 FPS
# H.264 + AAC
#
# FEATURES
# --------
# - Story-specific footage only
# - Multiple video/image scenes
# - Hindi narration
# - Background music
# - Burned-in Hindi subtitles
# - Windows + GitHub Ubuntu compatible
# - Noto Sans Devanagari subtitle support
# - Queue/state updates
# - No presenter fallback
# ============================================================


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_FOLDER = (
    Path(__file__)
    .resolve()
    .parents[1]
)

QUEUE_FILE = (
    PROJECT_FOLDER
    / "data"
    / "article_queue.json"
)

SCENE_FOLDER = (
    PROJECT_FOLDER
    / "scene_footage"
)

TEMP_FOLDER = (
    PROJECT_FOLDER
    / "temp_multi"
)

PREPARED_IMAGE_FOLDER = (
    TEMP_FOLDER
    / "prepared_images"
)

PREPARED_VIDEO_FOLDER = (
    TEMP_FOLDER
    / "prepared_videos"
)

FINAL_FOLDER = (
    PROJECT_FOLDER
    / "final_videos"
)

MUSIC_FILE = (
    PROJECT_FOLDER
    / "music"
    / "background_music.mp3"
)


for folder in (
    SCENE_FOLDER,
    TEMP_FOLDER,
    PREPARED_IMAGE_FOLDER,
    PREPARED_VIDEO_FOLDER,
    FINAL_FOLDER,
):
    folder.mkdir(
        parents=True,
        exist_ok=True
    )


# ============================================================
# FFMPEG
# ============================================================

# GitHub Ubuntu:
# use system FFmpeg because it contains libass/subtitles support.
#
# Windows:
# if system FFmpeg is unavailable, use imageio-ffmpeg fallback.

SYSTEM_FFMPEG = shutil.which(
    "ffmpeg"
)

if SYSTEM_FFMPEG:

    FFMPEG_EXE = Path(
        SYSTEM_FFMPEG
    )

else:

    FFMPEG_EXE = Path(
        imageio_ffmpeg.get_ffmpeg_exe()
    )


SYSTEM_FFPROBE = shutil.which(
    "ffprobe"
)


# ============================================================
# VIDEO SETTINGS
# ============================================================

WIDTH = 1280

HEIGHT = 720

FPS = 24

VIDEO_CODEC = "libx264"

VIDEO_PRESET = "ultrafast"

VIDEO_CRF = "25"

PIXEL_FORMAT = "yuv420p"


# ============================================================
# AUDIO SETTINGS
# ============================================================

AUDIO_CODEC = "aac"

AUDIO_BITRATE = "192k"

AUDIO_SAMPLE_RATE = 44100

VOICE_VOLUME = 1.0

MUSIC_VOLUME = 0.08


# ============================================================
# SCENE SETTINGS
# ============================================================

MIN_SCENES = 3

DEFAULT_SCENE_SECONDS = 6.0

MIN_SCENE_SECONDS = 3.0


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".mpeg",
    ".mpg",
    ".ogv",
}


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
}


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

    print(
        text
    )

    line()

    print()


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(value):

    if value is None:

        return ""

    return (
        " ".join(
            str(value)
            .replace(
                "\r",
                " "
            )
            .replace(
                "\n",
                " "
            )
            .split()
        )
        .strip()
    )


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

        value = (
            "THRAANSH_NEWS"
        )

    return value[:90]


# ============================================================
# QUEUE
# ============================================================

def load_queue():

    if not QUEUE_FILE.exists():

        raise RuntimeError(
            f"Queue file missing: "
            f"{QUEUE_FILE}"
        )

    with QUEUE_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(
            file
        )

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

            if isinstance(
                data.get(key),
                list
            ):

                return data[key]

    raise RuntimeError(
        "article_queue.json "
        "does not contain a valid article list."
    )


def save_queue(queue):

    temp_file = (
        QUEUE_FILE
        .with_suffix(
            ".json.tmp"
        )
    )

    with temp_file.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            queue,
            file,
            indent=2,
            ensure_ascii=False
        )

    temp_file.replace(
        QUEUE_FILE
    )


# ============================================================
# FIND CURRENT ARTICLE
# ============================================================

def get_article(queue):

    selected = [
        article
        for article in queue
        if (
            isinstance(
                article,
                dict
            )
            and article.get(
                "production_selected"
            )
            is True
        )
    ]

    if selected:

        return selected[-1]

    # Compatibility fallback.

    allowed_statuses = {
        "MULTI_MEDIA_READY",
        "MEDIA_READY",
        "SCENE_FOOTAGE_READY",
        "VIDEO_FAILED",
    }

    for article in reversed(
        queue
    ):

        status = clean_text(
            article.get(
                "status"
            )
        ).upper()

        if status in allowed_statuses:

            return article

    return None


# ============================================================
# PATH RESOLUTION
# ============================================================

def resolve_file(value):

    if not value:

        return None

    raw = str(
        value
    ).strip()

    if not raw:

        return None

    path = Path(
        raw
    )

    if path.exists():

        return path.resolve()

    # Handle paths produced on another OS.

    basename = Path(
        raw.replace(
            "\\",
            "/"
        )
    ).name

    candidates = [

        PROJECT_FOLDER
        / raw,

        SCENE_FOLDER
        / basename,

        PROJECT_FOLDER
        / "voice"
        / basename,

        PROJECT_FOLDER
        / "audio"
        / basename,

        FINAL_FOLDER
        / basename,

    ]

    for candidate in candidates:

        if candidate.exists():

            return candidate.resolve()

    return None


# ============================================================
# VOICE FILE
# ============================================================

def find_voice_file(article):

    possible = [

        article.get(
            "voice_file"
        ),

        article.get(
            "audio_file"
        ),

        article.get(
            "narration_file"
        ),

    ]

    for item in possible:

        path = resolve_file(
            item
        )

        if (
            path
            and path.exists()
        ):

            return path

    return None


# ============================================================
# SCENES
# ============================================================

def get_valid_scenes(article):

    raw_scenes = article.get(
        "scene_plan"
    )

    if not isinstance(
        raw_scenes,
        list
    ):

        raw_scenes = []

    scenes = []

    for scene in raw_scenes:

        if not isinstance(
            scene,
            dict
        ):

            continue

        footage = (
            scene.get(
                "footage_file"
            )
            or scene.get(
                "media_file"
            )
            or scene.get(
                "file"
            )
        )

        path = resolve_file(
            footage
        )

        if (
            not path
            or not path.exists()
        ):

            continue

        extension = (
            path.suffix.lower()
        )

        if extension not in (
            VIDEO_EXTENSIONS
            | IMAGE_EXTENSIONS
        ):

            continue

        scenes.append(
            {
                **scene,
                "_resolved_file":
                    path,
            }
        )

    # Compatibility with footage_files.

    if not scenes:

        files = article.get(
            "footage_files"
        )

        if isinstance(
            files,
            list
        ):

            for index, item in enumerate(
                files,
                start=1
            ):

                path = resolve_file(
                    item
                )

                if (
                    not path
                    or not path.exists()
                ):

                    continue

                scenes.append(
                    {
                        "scene_number":
                            index,

                        "_resolved_file":
                            path,
                    }
                )

    return scenes


# ============================================================
# FFMPEG RUNNER
# ============================================================

def run_ffmpeg(arguments):

    command = [

        str(
            FFMPEG_EXE
        ),

        *[
            str(item)
            for item
            in arguments
        ],
    ]

    print()

    print(
        "Running FFmpeg..."
    )

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    if result.returncode != 0:

        print(
            result.stdout[-8000:]
        )

        raise RuntimeError(
            "FFmpeg failed with "
            f"exit code "
            f"{result.returncode}."
        )

    return result


# ============================================================
# MEDIA DURATION
# ============================================================

def get_duration(file_path):

    if SYSTEM_FFPROBE:

        command = [

            SYSTEM_FFPROBE,

            "-v",
            "error",

            "-show_entries",
            "format=duration",

            "-of",
            "default="
            "noprint_wrappers=1:"
            "nokey=1",

            str(
                file_path
            ),
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        try:

            duration = float(
                result.stdout.strip()
            )

            if duration > 0:

                return duration

        except Exception:

            pass

    # FFmpeg fallback.

    result = subprocess.run(
        [
            str(
                FFMPEG_EXE
            ),
            "-i",
            str(
                file_path
            ),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    match = re.search(
        r"Duration:\s*"
        r"(\d+):"
        r"(\d+):"
        r"([\d.]+)",
        result.stdout
    )

    if not match:

        raise RuntimeError(
            "Could not determine duration "
            f"for {file_path}"
        )

    hours = int(
        match.group(1)
    )

    minutes = int(
        match.group(2)
    )

    seconds = float(
        match.group(3)
    )

    return (
        hours * 3600
        + minutes * 60
        + seconds
    )


# ============================================================
# STREAM VALIDATION
# ============================================================

def has_video_stream(file_path):

    result = subprocess.run(
        [
            str(
                FFMPEG_EXE
            ),
            "-i",
            str(
                file_path
            ),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    return (
        "Video:"
        in result.stdout
    )


def has_audio_stream(file_path):

    result = subprocess.run(
        [
            str(
                FFMPEG_EXE
            ),
            "-i",
            str(
                file_path
            ),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    return (
        "Audio:"
        in result.stdout
    )


# ============================================================
# IMAGE PREPARATION
# ============================================================

def prepare_image(
    source_file,
    destination
):

    with Image.open(
        source_file
    ) as image:

        image = image.convert(
            "RGB"
        )

        source_width, source_height = (
            image.size
        )

        target_ratio = (
            WIDTH
            / HEIGHT
        )

        source_ratio = (
            source_width
            / source_height
        )

        if source_ratio > target_ratio:

            new_width = int(
                source_height
                * target_ratio
            )

            left = (
                source_width
                - new_width
            ) // 2

            image = image.crop(
                (
                    left,
                    0,
                    left
                    + new_width,
                    source_height,
                )
            )

        else:

            new_height = int(
                source_width
                / target_ratio
            )

            top = (
                source_height
                - new_height
            ) // 2

            image = image.crop(
                (
                    0,
                    top,
                    source_width,
                    top
                    + new_height,
                )
            )

        image = image.resize(
            (
                WIDTH,
                HEIGHT
            ),
            Image.Resampling.LANCZOS
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        image.save(
            destination,
            "JPEG",
            quality=92
        )

    return destination


# ============================================================
# PREPARE VIDEO SCENE
# ============================================================

def create_video_scene(
    source,
    output,
    duration
):

    run_ffmpeg(
        [
            "-y",

            "-stream_loop",
            "-1",

            "-i",
            str(
                source
            ),

            "-t",
            f"{duration:.3f}",

            "-an",

            "-vf",
            (
                f"scale="
                f"{WIDTH}:"
                f"{HEIGHT}:"
                f"force_original_aspect_ratio="
                f"increase,"
                f"crop="
                f"{WIDTH}:"
                f"{HEIGHT},"
                f"fps={FPS}"
            ),

            "-c:v",
            VIDEO_CODEC,

            "-preset",
            VIDEO_PRESET,

            "-crf",
            VIDEO_CRF,

            "-pix_fmt",
            PIXEL_FORMAT,

            "-movflags",
            "+faststart",

            str(
                output
            ),
        ]
    )


# ============================================================
# PREPARE IMAGE SCENE
# ============================================================

def create_image_scene(
    source,
    output,
    duration,
    index
):

    prepared_image = (
        PREPARED_IMAGE_FOLDER
        / (
            f"scene_"
            f"{index:03d}.jpg"
        )
    )

    prepare_image(
        source,
        prepared_image
    )

    total_frames = max(
        1,
        int(
            duration
            * FPS
        )
    )

    # Very subtle zoom to avoid static image.

    zoom_direction = (
        1
        if index % 2
        else -1
    )

    if zoom_direction > 0:

        zoom_expression = (
            "min(zoom+0.00035,1.06)"
        )

    else:

        zoom_expression = (
            "if(eq(on,1),1.06,"
            "max(zoom-0.00035,1.0))"
        )

    filter_value = (
        f"zoompan="
        f"z='{zoom_expression}':"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':"
        f"d={total_frames}:"
        f"s={WIDTH}x{HEIGHT}:"
        f"fps={FPS},"
        f"format=yuv420p"
    )

    run_ffmpeg(
        [
            "-y",

            "-loop",
            "1",

            "-i",
            str(
                prepared_image
            ),

            "-t",
            f"{duration:.3f}",

            "-an",

            "-vf",
            filter_value,

            "-c:v",
            VIDEO_CODEC,

            "-preset",
            VIDEO_PRESET,

            "-crf",
            VIDEO_CRF,

            "-pix_fmt",
            PIXEL_FORMAT,

            str(
                output
            ),
        ]
    )


# ============================================================
# CREATE ALL SCENE CLIPS
# ============================================================

def prepare_scenes(
    scenes,
    voice_duration
):

    scene_count = len(
        scenes
    )

    if scene_count <= 0:

        raise RuntimeError(
            "No valid scenes."
        )

    # Make combined scene video at least
    # as long as narration.

    scene_duration = max(
        MIN_SCENE_SECONDS,
        float(
            voice_duration
        )
        / float(
            scene_count
        )
    )

    prepared = []

    for index, scene in enumerate(
        scenes,
        start=1
    ):

        source = scene[
            "_resolved_file"
        ]

        output = (
            PREPARED_VIDEO_FOLDER
            / (
                f"scene_"
                f"{index:03d}.mp4"
            )
        )

        print()

        print(
            f"Preparing scene "
            f"{index}/"
            f"{scene_count}"
        )

        print(
            source
        )

        extension = (
            source.suffix.lower()
        )

        if extension in VIDEO_EXTENSIONS:

            create_video_scene(
                source,
                output,
                scene_duration
            )

        elif extension in IMAGE_EXTENSIONS:

            create_image_scene(
                source,
                output,
                scene_duration,
                index
            )

        else:

            continue

        if (
            output.exists()
            and output.stat().st_size
            > 0
        ):

            prepared.append(
                output
            )

    return prepared


# ============================================================
# CONCAT SCENES
# ============================================================

def join_scenes(
    scene_files,
    output_file
):

    if not scene_files:

        raise RuntimeError(
            "No prepared scene files."
        )

    concat_file = (
        TEMP_FOLDER
        / "concat.txt"
    )

    lines = []

    for file in scene_files:

        path = (
            file.resolve()
            .as_posix()
            .replace(
                "'",
                r"'\''"
            )
        )

        lines.append(
            f"file '{path}'"
        )

    concat_file.write_text(
        "\n".join(
            lines
        ),
        encoding="utf-8"
    )

    run_ffmpeg(
        [
            "-y",

            "-f",
            "concat",

            "-safe",
            "0",

            "-i",
            str(
                concat_file
            ),

            "-an",

            "-c:v",
            "copy",

            str(
                output_file
            ),
        ]
    )

    return output_file


# ============================================================
# SUBTITLE HELPERS
# ============================================================

def srt_timestamp(seconds):

    seconds = max(
        0.0,
        float(
            seconds
        )
    )

    milliseconds = int(
        round(
            seconds
            * 1000
        )
    )

    hours = (
        milliseconds
        // 3_600_000
    )

    milliseconds %= (
        3_600_000
    )

    minutes = (
        milliseconds
        // 60_000
    )

    milliseconds %= (
        60_000
    )

    secs = (
        milliseconds
        // 1000
    )

    millis = (
        milliseconds
        % 1000
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{secs:02d},"
        f"{millis:03d}"
    )


def split_subtitle_text(text):

    text = clean_text(
        text
    )

    if not text:

        return []

    sentences = [

        part.strip()

        for part in re.split(
            r"(?<=[à¥¤!?])\s+",
            text
        )

        if part.strip()
    ]

    if not sentences:

        sentences = [
            text
        ]

    chunks = []

    for sentence in sentences:

        words = (
            sentence.split()
        )

        # Keep subtitles short
        # and easy to read.

        current = []

        for word in words:

            current.append(
                word
            )

            if len(current) >= 7:

                chunks.append(
                    " ".join(
                        current
                    )
                )

                current = []

        if current:

            chunks.append(
                " ".join(
                    current
                )
            )

    return chunks


# ============================================================
# CREATE SRT
# ============================================================


# ============================================================
# NATURAL ROMAN HINDI SUBTITLES
# ============================================================

def romanize_hindi(text):

    text = clean_text(text)

    if not text:
        return ""

    # --------------------------------------------------------
    # COMMON NATURAL ROMAN-HINDI PHRASES
    # --------------------------------------------------------

    phrase_map = {

        "आप कैसे हो": "Aap kaise ho",
        "क्या करते हो": "Kya karte ho",

        "आज की बड़ी खबर": "Aaj ki badi khabar",

        "सामने आ रही है":
            "saamne aa rahi hai",

        "सामने आ रहा है":
            "saamne aa raha hai",

        "सामने आया है":
            "saamne aaya hai",

        "सामने आई है":
            "saamne aayi hai",

        "नई दिल्ली":
            "New Delhi",

        "सुप्रीम कोर्ट":
            "Supreme Court",

        "प्रधानमंत्री":
            "Pradhan Mantri",

        "मुख्यमंत्री":
            "Mukhya Mantri",

        "केंद्रीय सरकार":
            "Kendra Sarkar",

        "भारत सरकार":
            "Bharat Sarkar",
    }

    result = text

    # Replace longer phrases first.

    for hindi in sorted(
        phrase_map.keys(),
        key=len,
        reverse=True
    ):

        result = result.replace(
            hindi,
            phrase_map[hindi]
        )

    # --------------------------------------------------------
    # NATURAL WORD DICTIONARY
    # --------------------------------------------------------

    word_map = {

        "आप": "aap",
        "हम": "hum",
        "मैं": "main",
        "वह": "woh",
        "वे": "woh",
        "यह": "yeh",
        "ये": "yeh",

        "क्या": "kya",
        "क्यों": "kyun",
        "कैसे": "kaise",
        "कौन": "kaun",
        "कब": "kab",
        "कहां": "kahan",
        "कहाँ": "kahan",

        "आज": "aaj",
        "कल": "kal",
        "अब": "ab",
        "फिर": "phir",
        "पहले": "pehle",
        "बाद": "baad",

        "की": "ki",
        "का": "ka",
        "के": "ke",

        "को": "ko",
        "से": "se",
        "में": "mein",
        "पर": "par",
        "तक": "tak",

        "और": "aur",
        "लेकिन": "lekin",
        "अगर": "agar",
        "तो": "to",

        "एक": "ek",
        "इस": "is",
        "उस": "us",

        "है": "hai",
        "हैं": "hain",
        "था": "tha",
        "थी": "thi",
        "थे": "the",

        "नहीं": "nahi",

        "कर": "kar",
        "करता": "karta",
        "करती": "karti",
        "करते": "karte",
        "करना": "karna",
        "किया": "kiya",

        "हुआ": "hua",
        "हुई": "hui",
        "हुए": "hue",

        "गया": "gaya",
        "गई": "gayi",
        "गए": "gaye",

        "रहा": "raha",
        "रही": "rahi",
        "रहे": "rahe",

        "आ": "aa",
        "आया": "aaya",
        "आई": "aayi",

        "लिए": "liye",
        "ने": "ne",
        "साथ": "saath",

        "बड़ी": "badi",
        "बड़ा": "bada",

        "खबर": "khabar",
        "मामला": "maamla",
        "मामले": "maamle",

        "जानकारी": "jaankari",

        "फैसला": "faisla",

        "सरकार": "sarkar",

        "अधिकारी": "adhikari",
        "अधिकारियों": "adhikariyon",

        "अदालत": "adalat",

        "भारत": "Bharat",
        "भारतीय": "Bharatiya",

        "दिल्ली": "Delhi",
        "मुंबई": "Mumbai",
        "बेंगलुरु": "Bengaluru",
        "बैंगलोर": "Bengaluru",
        "चेन्नई": "Chennai",
        "कोलकाता": "Kolkata",
        "हैदराबाद": "Hyderabad",

        "पुलिस": "police",

        "वीडियो": "video",

        "फेसबुक": "Facebook",
        "इंस्टाग्राम": "Instagram",
        "यूट्यूब": "YouTube",
    }

    # --------------------------------------------------------
    # REPLACE DEVANAGARI WORDS
    # --------------------------------------------------------

    for hindi in sorted(
        word_map.keys(),
        key=len,
        reverse=True
    ):

        result = result.replace(
            hindi,
            word_map[hindi]
        )

    # --------------------------------------------------------
    # FALLBACK FOR ANY HINDI STILL LEFT
    # --------------------------------------------------------

    if re.search(
        r"[\u0900-\u097F]",
        result
    ):

        result = transliterate(
            result,
            sanscript.DEVANAGARI,
            sanscript.ITRANS
        )

        fallback_fixes = [
            (".Dh", "dh"),
            (".D", "d"),
            (".Th", "th"),
            (".T", "t"),
            ("~N", "n"),
            ("~n", "n"),
            (".n", "n"),
            (".m", "n"),
            ("M", "n"),
            ("H", "h"),
            ("|", "."),
        ]

        for old, new in fallback_fixes:

            result = result.replace(
                old,
                new
            )

        # Naturalize common ITRANS output.

        natural_fixes = {

            "Aapa": "Aap",
            "aapa": "aap",

            "kyaa": "kya",
            "Kyaa": "Kya",

            "karate": "karte",
            "karatee": "karti",

            "aaja": "aaj",
            "Aaja": "Aaj",

            "kee": "ki",

            "baDee": "badi",
            "ba.Dee": "badi",

            "khabara": "khabar",

            "dillee": "Delhi",
            "dillii": "Delhi",
            "delhii": "Delhi",

            "saamane": "saamne",

            "rahee": "rahi",
            "rahaa": "raha",

            "sarakaar": "sarkar",
            "sarakaara": "sarkar",

            "bhaarata": "Bharat",

            "mumbaee": "Mumbai",

            "chennaee": "Chennai",

            "kolakaataa": "Kolkata",

            "haidarabaada": "Hyderabad",
        }

        words = result.split()

        final_words = []

        for word in words:

            punctuation_before = ""
            punctuation_after = ""

            core = word

            while (
                core
                and core[0]
                in '"''([{'
            ):

                punctuation_before += core[0]
                core = core[1:]

            while (
                core
                and core[-1]
                in '.,!?;:)]}"'''
            ):

                punctuation_after = (
                    core[-1]
                    + punctuation_after
                )

                core = core[:-1]

            fixed = natural_fixes.get(
                core,
                natural_fixes.get(
                    core.lower(),
                    core
                )
            )

            final_words.append(
                punctuation_before
                + fixed
                + punctuation_after
            )

        result = " ".join(
            final_words
        )

    # --------------------------------------------------------
    # FINAL EXACT NATURAL CORRECTIONS
    # --------------------------------------------------------

    corrections = {

        "Aap kaise ho? kya karte ho?":
            "Aap kaise ho? Kya karte ho?",

        "aap kaise ho?":
            "Aap kaise ho?",

        "aaj ki badi khabar":
            "Aaj ki badi khabar",

        "Delhi se saamne aa rahi hai":
            "Delhi se saamne aa rahi hai",

        "dillee": "Delhi",
        "Dillee": "Delhi",

        "Aapa": "Aap",

        "kyaa": "kya",

        "karate": "karte",
    }

    for old, new in corrections.items():

        result = result.replace(
            old,
            new
        )

    result = result.replace(
        "|",
        "."
    )

    result = re.sub(
        r"\s+",
        " ",
        result
    ).strip()

    # Capitalize sentence starts.

    result = re.sub(
        r"(^|[.!?]\s+)([a-z])",
        lambda match:
            match.group(1)
            + match.group(2).upper(),
        result
    )

    return result

def create_subtitle_file(
    article,
    voice_duration,
    output_file
):

    narration = clean_text(

        article.get(
            "narration_script"
        )

        or article.get(
            "hindi_script"
        )

        or ""
    )

    if not narration:

        raise RuntimeError(
            "Hindi narration script "
            "missing. Cannot create subtitles."
        )

    chunks = (
        split_subtitle_text(
            narration
        )
    )

    if not chunks:

        raise RuntimeError(
            "Subtitle chunks could "
            "not be created."
        )

    duration = float(
        voice_duration
    )

    weights = [

        max(
            1,
            len(
                re.sub(
                    r"\s+",
                    "",
                    chunk
                )
            )
        )

        for chunk
        in chunks
    ]

    total_weight = sum(
        weights
    )

    current_time = 0.0

    srt_lines = []

    for index, (
        chunk,
        weight
    ) in enumerate(
        zip(
            chunks,
            weights
        ),
        start=1
    ):

        if index == len(
            chunks
        ):

            end_time = (
                duration
            )

        else:

            calculated = (
                duration
                * weight
                / total_weight
            )

            end_time = min(
                duration,
                current_time
                + calculated
            )

        # Safety.

        if end_time <= current_time:

            end_time = min(
                duration,
                current_time
                + 0.5
            )

        srt_lines.extend(
            [
                str(
                    index
                ),

                (
                    f"{srt_timestamp(current_time)} "
                    f"--> "
                    f"{srt_timestamp(end_time)}"
                ),

                romanize_hindi(
                    chunk
                ),

                "",
            ]
        )

        current_time = (
            end_time
        )

    output_file.write_text(
        "\n".join(
            srt_lines
        ),
        encoding="utf-8"
    )

    return output_file


# ============================================================
# SUBTITLE FONT
# ============================================================

def subtitle_font():

    # Windows options.

    windows_fonts = [

        Path(
            r"C:\Windows\Fonts\Nirmala.ttf"
        ),

        Path(
            r"C:\Windows\Fonts\NirmalaB.ttf"
        ),

        Path(
            r"C:\Windows\Fonts\mangal.ttf"
        ),

    ]

    for font in windows_fonts:

        if font.exists():

            return (
                "Nirmala UI"
            )

    # GitHub Ubuntu:
    # installed with fonts-noto-core.

    return (
        "Noto Sans"
    )


# ============================================================
# FFMPEG SUBTITLE FILTER
# ============================================================

def subtitle_filter(
    subtitle_file
):

    path = (
        subtitle_file
        .resolve()
        .as_posix()
    )

    # Required by FFmpeg on Windows:
    # C:/... becomes C\:/...

    path = (
        path
        .replace(
            ":",
            r"\:"
        )
        .replace(
            "'",
            r"\'"
        )
    )

    font = (
        subtitle_font()
    )

    style = (
        f"FontName={font},"
        "FontSize=25,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BackColour=&H78000000,"
        "Bold=1,"
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=1,"
        "Alignment=2,"
        "MarginL=65,"
        "MarginR=65,"
        "MarginV=35"
    )

    return (
        "subtitles="
        f"filename='{path}':"
        f"force_style='{style}'"
    )


# ============================================================
# FINAL RENDER
# ============================================================

def render_final(
    joined_video,
    voice_file,
    output_file,
    voice_duration,
    subtitle_file
):

    video_filter = (
        subtitle_filter(
            subtitle_file
        )
    )

    # --------------------------------------------------------
    # WITH BACKGROUND MUSIC
    # --------------------------------------------------------

    if (
        MUSIC_FILE.exists()
        and MUSIC_FILE.stat().st_size
        > 0
    ):

        print()

        print(
            "Background music: ON"
        )

        print(
            f"Music volume: "
            f"{int(MUSIC_VOLUME * 100)}%"
        )

        print(
            "Roman Hindi subtitles: ON"
        )

        audio_filter = (

            f"[1:a]"
            f"volume={VOICE_VOLUME},"
            f"aresample={AUDIO_SAMPLE_RATE},"
            f"aformat=channel_layouts=stereo"
            f"[voice];"

            f"[2:a]"
            f"volume={MUSIC_VOLUME},"
            f"aresample={AUDIO_SAMPLE_RATE},"
            f"aformat=channel_layouts=stereo"
            f"[music];"

            f"[voice][music]"
            f"amix="
            f"inputs=2:"
            f"duration=first:"
            f"dropout_transition=2,"
            f"alimiter=limit=0.95"
            f"[audio]"
        )

        run_ffmpeg(
            [
                "-y",

                "-stream_loop",
                "-1",

                "-i",
                str(
                    joined_video
                ),

                "-i",
                str(
                    voice_file
                ),

                "-stream_loop",
                "-1",

                "-i",
                str(
                    MUSIC_FILE
                ),

                "-filter_complex",
                audio_filter,

                "-vf",
                video_filter,

                "-map",
                "0:v:0",

                "-map",
                "[audio]",

                "-t",
                f"{voice_duration:.3f}",

                "-c:v",
                VIDEO_CODEC,

                "-preset",
                VIDEO_PRESET,

                "-crf",
                VIDEO_CRF,

                "-pix_fmt",
                PIXEL_FORMAT,

                "-c:a",
                AUDIO_CODEC,

                "-b:a",
                AUDIO_BITRATE,

                "-ar",
                str(
                    AUDIO_SAMPLE_RATE
                ),

                "-ac",
                "2",

                "-movflags",
                "+faststart",

                str(
                    output_file
                ),
            ]
        )

        return True

    # --------------------------------------------------------
    # WITHOUT MUSIC
    # --------------------------------------------------------

    print()

    print(
        "Background music: OFF"
    )

    print(
        "Roman Hindi subtitles: ON"
    )

    run_ffmpeg(
        [
            "-y",

            "-stream_loop",
            "-1",

            "-i",
            str(
                joined_video
            ),

            "-i",
            str(
                voice_file
            ),

            "-vf",
            video_filter,

            "-map",
            "0:v:0",

            "-map",
            "1:a:0",

            "-t",
            f"{voice_duration:.3f}",

            "-c:v",
            VIDEO_CODEC,

            "-preset",
            VIDEO_PRESET,

            "-crf",
            VIDEO_CRF,

            "-pix_fmt",
            PIXEL_FORMAT,

            "-c:a",
            AUDIO_CODEC,

            "-b:a",
            AUDIO_BITRATE,

            "-ar",
            str(
                AUDIO_SAMPLE_RATE
            ),

            "-ac",
            "2",

            "-movflags",
            "+faststart",

            str(
                output_file
            ),
        ]
    )

    return False


# ============================================================
# CLEAN TEMP
# ============================================================

def clean_temp():

    if TEMP_FOLDER.exists():

        for item in TEMP_FOLDER.iterdir():

            try:

                if item.is_file():

                    item.unlink()

                elif item.is_dir():

                    shutil.rmtree(
                        item
                    )

            except Exception:

                pass

    PREPARED_IMAGE_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )

    PREPARED_VIDEO_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    line()

    print(
        "THRAANSH ULTRA-FAST STORY RENDERER"
    )

    line()

    print()

    print(
        "Resolution: "
        f"{WIDTH}x{HEIGHT}"
    )

    print(
        f"FPS: {FPS}"
    )

    print(
        f"FFmpeg: "
        f"{FFMPEG_EXE}"
    )

    print()

    print(
        "Roman Hindi subtitles: ENABLED"
    )

    print(
        "Presenter fallback: DISABLED"
    )

    # ========================================================
    # VALIDATE FFMPEG
    # ========================================================

    if not FFMPEG_EXE.exists():

        raise RuntimeError(
            "FFmpeg executable missing."
        )

    # ========================================================
    # LOAD ARTICLE
    # ========================================================

    queue = load_queue()

    # ========================================================
    # STRICT SAME-ARTICLE SELECTION
    # ========================================================
    #
    # The final renderer MUST use the exact article selected
    # by production_selector.py.
    #
    # No fallback to an old ARTICLE_READY, VOICE_READY,
    # MULTI_MEDIA_READY or failed article is allowed.
    # ========================================================

    selected_articles = [
        item
        for item in queue
        if (
            isinstance(item, dict)
            and item.get("production_selected") is True
        )
    ]

    if len(selected_articles) == 0:
        raise RuntimeError(
            "FINAL VIDEO BLOCKED: "
            "no production_selected article exists."
        )

    if len(selected_articles) > 1:
        selected_titles = [
            clean_text(
                item.get("title")
                or "UNTITLED"
            )
            for item in selected_articles
        ]

        raise RuntimeError(
            "FINAL VIDEO BLOCKED: "
            "multiple production_selected articles exist: "
            + " | ".join(selected_titles)
        )

    article = selected_articles[0]

    title = clean_text(
        article.get("title")
        or "THRAANSH News"
    )

    print()
    print("=" * 72)
    print("FINAL VIDEO ARTICLE LOCK")
    print("=" * 72)
    print("Article:")
    print(title)
    print("production_selected: TRUE")
    print("=" * 72)

    # --------------------------------------------------------
    # Validate that THIS SAME ARTICLE completed script stage
    # --------------------------------------------------------

    selected_script = clean_text(
        article.get("hindi_script")
        or article.get("narration_script")
        or article.get("presenter_script")
        or article.get("script")
    )

    if not selected_script:
        raise RuntimeError(
            "FINAL VIDEO BLOCKED: "
            "production_selected article has no Hindi script: "
            + title
        )


    title = clean_text(
        article.get(
            "title"
        )
        or "THRAANSH News"
    )

    print()

    print(
        "ARTICLE:"
    )

    print(
        title
    )

    # ========================================================
    # VOICE
    # ========================================================

    voice_file = find_voice_file(
        article
    )

    if voice_file is None:

        raise RuntimeError(
            "Hindi voice file "
            "could not be found."
        )

    voice_duration = get_duration(
        voice_file
    )

    print()

    print(
        "Hindi voice:"
    )

    print(
        voice_file
    )

    print(
        f"Duration: "
        f"{voice_duration:.2f}s"
    )

    # ========================================================
    # STORY SCENES
    # ========================================================

    scenes = get_valid_scenes(
        article
    )

    print()

    print(
        f"Valid story scenes: "
        f"{len(scenes)}"
    )

    if len(scenes) < MIN_SCENES:

        raise RuntimeError(
            f"At least "
            f"{MIN_SCENES} "
            f"valid story scenes required."
        )

    # ========================================================
    # CLEAN TEMP
    # ========================================================

    clean_temp()

    try:

        # ====================================================
        # PREPARE SCENES
        # ====================================================

        prepared_scenes = prepare_scenes(
            scenes,
            voice_duration
        )

        if len(
            prepared_scenes
        ) < MIN_SCENES:

            raise RuntimeError(
                "Too few scenes were "
                "successfully prepared."
            )

        # ====================================================
        # JOIN SCENES
        # ====================================================

        joined_video = (
            TEMP_FOLDER
            / "joined_story.mp4"
        )

        join_scenes(
            prepared_scenes,
            joined_video
        )

        if not joined_video.exists():

            raise RuntimeError(
                "Joined story video "
                "was not created."
            )

        # ====================================================
        # SUBTITLES
        # ====================================================

        subtitle_file = (
            TEMP_FOLDER
            / (
                safe_filename(
                    title
                )
                + "_Roman_Hindi_Subtitles.srt"
            )
        )

        create_subtitle_file(
            article,
            voice_duration,
            subtitle_file
        )

        print()

        print(
            "Hindi subtitle file:"
        )

        print(
            subtitle_file
        )

        # ====================================================
        # FINAL OUTPUT
        # ====================================================

        output_file = (
            FINAL_FOLDER
            / (
                safe_filename(
                    title
                )
                + "_THRAANSH_FINAL.mp4"
            )
        )

        print()

        print(
            "Rendering final "
            "THRAANSH video..."
        )

        music_used = render_final(
            joined_video,
            voice_file,
            output_file,
            voice_duration,
            subtitle_file
        )

        # ====================================================
        # VALIDATION
        # ====================================================

        if not output_file.exists():

            raise RuntimeError(
                "Final MP4 not created."
            )

        if (
            output_file.stat().st_size
            <= 0
        ):

            raise RuntimeError(
                "Final MP4 is empty."
            )

        if not has_video_stream(
            output_file
        ):

            raise RuntimeError(
                "Final video stream missing."
            )

        if not has_audio_stream(
            output_file
        ):

            raise RuntimeError(
                "Final audio stream missing."
            )

        size_mb = (
            output_file.stat().st_size
            / 1024
            / 1024
        )

        # ====================================================
        # SAVE SUCCESS
        # ====================================================

        article[
            "final_video_file"
        ] = str(
            output_file
        )

        article[
            "final_video_size_mb"
        ] = round(
            size_mb,
            2
        )

        article[
            "video_width"
        ] = WIDTH

        article[
            "video_height"
        ] = HEIGHT

        article[
            "video_fps"
        ] = FPS

        article[
            "video_status"
        ] = "READY"

        article[
            "background_music"
        ] = bool(
            music_used
        )

        article[
            "music_volume"
        ] = (
            MUSIC_VOLUME
            if music_used
            else 0
        )

        article[
            "narration_language"
        ] = "hi"

        article[
            "subtitles_burned_in"
        ] = True

        article[
            "subtitle_language"
        ] = "hi"

        article[
            "subtitle_status"
        ] = "BURNED_IN"

        article[
            "subtitle_file"
        ] = str(
            subtitle_file
        )

        article[
            "subtitle_source"
        ] = (
            "narration_script"
            if clean_text(
                article.get(
                    "narration_script"
                )
            )
            else "hindi_script"
        )

        article[
            "status"
        ] = "VIDEO_READY"

        article[
            "last_error"
        ] = None

        article[
            "video_generated_at"
        ] = (
            datetime.now()
            .isoformat()
        )

        article[
            "updated_at"
        ] = (
            datetime.now()
            .isoformat()
        )

        save_queue(
            queue
        )

        # ====================================================
        # SUCCESS OUTPUT
        # ====================================================

        print()

        line()

        print(
            "THRAANSH VIDEO GENERATED SUCCESSFULLY"
        )

        line()

        print()

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
            "Story footage âœ“"
        )

        print(
            "Hindi narration âœ“"
        )

        print(
            "Roman Hindi burned-in subtitles âœ“"
        )

        if music_used:

            print(
                "Background music âœ“"
            )

        else:

            print(
                "Background music not used"
            )

        print()

    except Exception as error:

        # ====================================================
        # SAVE FAILURE
        # ====================================================

        article[
            "video_status"
        ] = "FAILED"

        article[
            "status"
        ] = "VIDEO_FAILED"

        article[
            "retry_count"
        ] = (
            int(
                article.get(
                    "retry_count"
                )
                or 0
            )
            + 1
        )

        article[
            "last_error"
        ] = str(
            error
        )

        article[
            "updated_at"
        ] = (
            datetime.now()
            .isoformat()
        )

        save_queue(
            queue
        )

        print()

        line()

        print(
            "THRAANSH VIDEO RENDER FAILED"
        )

        line()

        print()

        print(
            error
        )

        raise


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()

        print(
            "Renderer interrupted."
        )

        sys.exit(
            130
        )

    except Exception as error:

        print()

        print(
            f"FATAL: {error}"
        )

        sys.exit(
            1
        )

