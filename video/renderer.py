import json
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path

import imageio_ffmpeg

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print()
    print("=" * 70)
    print("THRAANSH VIDEO RENDERER")
    print("=" * 70)
    print()
    print("Pillow is missing.")
    print()
    print("Run:")
    print(
        r".\.venv\Scripts\python.exe -m pip install pillow"
    )
    print()
    raise SystemExit(1)


# ============================================================
# THRAANSH FINAL VIDEO RENDERER
#
# FOOTAGE       = Story-accurate / India-first
# VOICE         = Easy Hindi presenter
# HEADLINE      = English
# BRANDING      = THRAANSH
# MUSIC         = Low background music
# OUTPUT        = 1920x1080 MP4
# ============================================================


PROJECT_FOLDER = Path(__file__).resolve().parents[1]

DATA_FOLDER = PROJECT_FOLDER / "data"

FINAL_VIDEO_FOLDER = (
    PROJECT_FOLDER / "final_videos"
)

TEMP_FOLDER = (
    PROJECT_FOLDER / "temp"
)

MUSIC_FOLDER = (
    PROJECT_FOLDER / "music"
)

QUEUE_FILE = (
    DATA_FOLDER / "article_queue.json"
)


FINAL_VIDEO_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)

TEMP_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)

MUSIC_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


FFMPEG_EXE = (
    imageio_ffmpeg.get_ffmpeg_exe()
)


# ============================================================
# VIDEO CONFIGURATION
# ============================================================

VIDEO_WIDTH = 1920

VIDEO_HEIGHT = 1080

VIDEO_FPS = 30


# Narration is the main audio
VOICE_VOLUME = 1.0


# Background music should stay subtle
MUSIC_VOLUME = 0.10


# English headline appears for first seconds
HEADLINE_DURATION = 8


# ============================================================
# LOAD QUEUE
# ============================================================

def load_queue():

    if not QUEUE_FILE.exists():

        print()
        print(
            "ERROR: article_queue.json not found."
        )

        return []

    try:

        with open(
            QUEUE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(
            data,
            list
        ):

            return data

    except Exception as error:

        print()
        print(
            "ERROR reading queue:"
        )

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
# CLEAN TEXT
# ============================================================

def clean_text(value):

    if value is None:

        return ""

    return " ".join(
        str(value).split()
    ).strip()


# ============================================================
# FIND NEXT ARTICLE
# ============================================================

def get_next_article(queue):

    for article in queue:

        status = clean_text(
            article.get(
                "status"
            )
        ).upper()

        if status not in [
            "MEDIA_READY",
            "VIDEO_FAILED",
        ]:

            continue

        footage_file = (
            article.get(
                "footage_file"
            )
        )

        audio_file = (
            article.get(
                "voice_file"
            )
            or article.get(
                "audio_file"
            )
        )

        if not footage_file:

            continue

        if not audio_file:

            continue

        if not Path(
            footage_file
        ).exists():

            continue

        if not Path(
            audio_file
        ).exists():

            continue

        return article

    return None


# ============================================================
# SAFE FILE NAME
# ============================================================

def safe_filename(text):

    allowed = []

    for character in clean_text(
        text
    ):

        if (
            character.isalnum()
            or character
            in (
                " ",
                "-",
                "_",
            )
        ):

            allowed.append(
                character
            )

    filename = "".join(
        allowed
    ).strip()

    filename = filename.replace(
        " ",
        "_"
    )

    if not filename:

        filename = (
            "thraansh_video"
        )

    return filename[:65]


# ============================================================
# FIND WINDOWS FONT
# ============================================================



# ============================================================
# CREATE ENGLISH HEADLINE OVERLAY
# ============================================================

def find_font():
    fonts = [Path(r'C:\Windows\Fonts\arialbd.ttf'), Path(r'C:\Windows\Fonts\arial.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    for font in fonts:
        if font.exists():
            return font
    return None

def create_headline_overlay(
    title,
    publisher,
    output_file
):

    image = Image.new(
        "RGBA",
        (
            VIDEO_WIDTH,
            VIDEO_HEIGHT
        ),
        (
            0,
            0,
            0,
            0
        )
    )


    draw = ImageDraw.Draw(
        image
    )


    font_path = find_font()


    if font_path:

        brand_font = (
            ImageFont.truetype(
                str(font_path),
                42
            )
        )

        title_font = (
            ImageFont.truetype(
                str(font_path),
                54
            )
        )

        source_font = (
            ImageFont.truetype(
                str(font_path),
                26
            )
        )

    else:

        brand_font = (
            ImageFont.load_default()
        )

        title_font = (
            ImageFont.load_default()
        )

        source_font = (
            ImageFont.load_default()
        )


    # ========================================================
    # TOP BRAND BAR
    # ========================================================

    draw.rounded_rectangle(
        (
            65,
            55,
            450,
            130
        ),
        radius=16,
        fill=(
            9,
            14,
            23,
            235
        )
    )


    draw.text(
        (
            95,
            70
        ),
        "THRAANSH",
        font=brand_font,
        fill=(
            255,
            255,
            255,
            255
        )
    )


    # ========================================================
    # HEADLINE PANEL
    # ========================================================

    panel_top = 735

    draw.rounded_rectangle(
        (
            70,
            panel_top,
            1850,
            1015
        ),
        radius=25,
        fill=(
            6,
            11,
            18,
            220
        )
    )


    wrapped_lines = (
        textwrap.wrap(
            title,
            width=52
        )
    )


    wrapped_lines = (
        wrapped_lines[:3]
    )


    headline = "\n".join(
        wrapped_lines
    )


    draw.multiline_text(
        (
            115,
            panel_top + 45
        ),
        headline,
        font=title_font,
        fill=(
            255,
            255,
            255,
            255
        ),
        spacing=12
    )


    if publisher:

        source_text = (
            f"Source: {publisher}"
        )

        draw.text(
            (
                118,
                965
            ),
            source_text,
            font=source_font,
            fill=(
                190,
                198,
                210,
                255
            )
        )


    image.save(
        output_file
    )


# ============================================================
# FIND BACKGROUND MUSIC
# ============================================================

def find_background_music():

    supported_extensions = {
        ".mp3",
        ".wav",
        ".m4a",
        ".aac",
        ".ogg",
    }


    preferred_file = (
        MUSIC_FOLDER
        / "background_music.mp3"
    )


    if preferred_file.exists():

        return preferred_file


    for file in MUSIC_FOLDER.iterdir():

        if (
            file.is_file()
            and file.suffix.lower()
            in supported_extensions
        ):

            return file


    return None


# ============================================================
# RENDER WITHOUT MUSIC
# ============================================================

def render_without_music(
    footage_file,
    audio_file,
    overlay_file,
    output_file
):

    filter_complex = (
        f"[0:v]"
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:"
        f"force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
        f"fps={VIDEO_FPS}"
        f"[base];"

        f"[base][2:v]"
        f"overlay=0:0:"
        f"enable='between(t,0,"
        f"{HEADLINE_DURATION})'"
        f"[video]"
    )


    command = [

        FFMPEG_EXE,

        "-y",


        # Loop footage
        "-stream_loop",
        "-1",

        "-i",
        str(
            footage_file
        ),


        # Hindi narration
        "-i",
        str(
            audio_file
        ),


        # English headline PNG
        "-loop",
        "1",

        "-i",
        str(
            overlay_file
        ),


        "-filter_complex",
        filter_complex,


        "-map",
        "[video]",

        "-map",
        "1:a:0",


        "-c:v",
        "libx264",

        "-preset",
        "medium",

        "-crf",
        "21",

        "-pix_fmt",
        "yuv420p",


        "-c:a",
        "aac",

        "-b:a",
        "192k",


        "-shortest",


        "-movflags",
        "+faststart",


        str(
            output_file
        ),
    ]


    run_ffmpeg(
        command
    )


# ============================================================
# RENDER WITH LIGHT BACKGROUND MUSIC + DUCKING
# ============================================================

def render_with_music(
    footage_file,
    narration_file,
    music_file,
    overlay_file,
    output_file
):

    # Background music is lowered,
    # then ducked further whenever
    # the Hindi narration is speaking.

    filter_complex = (

        # Video
        f"[0:v]"
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:"
        f"force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
        f"fps={VIDEO_FPS}"
        f"[base];"


        # Overlay English headline
        f"[base][3:v]"
        f"overlay=0:0:"
        f"enable='between(t,0,"
        f"{HEADLINE_DURATION})'"
        f"[video];"


        # Hindi presenter narration
        f"[1:a]"
        f"volume={VOICE_VOLUME}"
        f"[voice];"


        # Background music
        f"[2:a]"
        f"volume={MUSIC_VOLUME}"
        f"[music];"


        # Duck music whenever voice speaks
        f"[music][voice]"
        f"sidechaincompress="
        f"threshold=0.025:"
        f"ratio=8:"
        f"attack=20:"
        f"release=500"
        f"[ducked];"


        # Final mix
        f"[voice][ducked]"
        f"amix="
        f"inputs=2:"
        f"duration=first:"
        f"dropout_transition=2"
        f"[audio]"
    )


    command = [

        FFMPEG_EXE,

        "-y",


        # Loop visual footage
        "-stream_loop",
        "-1",

        "-i",
        str(
            footage_file
        ),


        # Hindi narration
        "-i",
        str(
            narration_file
        ),


        # Loop background music
        "-stream_loop",
        "-1",

        "-i",
        str(
            music_file
        ),


        # Overlay image
        "-loop",
        "1",

        "-i",
        str(
            overlay_file
        ),


        "-filter_complex",
        filter_complex,


        "-map",
        "[video]",

        "-map",
        "[audio]",


        "-c:v",
        "libx264",

        "-preset",
        "medium",

        "-crf",
        "21",

        "-pix_fmt",
        "yuv420p",


        "-c:a",
        "aac",

        "-b:a",
        "192k",


        "-shortest",


        "-movflags",
        "+faststart",


        str(
            output_file
        ),
    ]


    run_ffmpeg(
        command
    )


# ============================================================
# RUN FFMPEG
# ============================================================

def run_ffmpeg(command):

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )


    if (
        result.returncode
        != 0
    ):

        print()
        print(
            "FFmpeg error:"
        )

        print(
            result.stderr
        )

        raise RuntimeError(
            "FFmpeg final video rendering failed."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)

    print(
        "THRAANSH FINAL VIDEO RENDERER"
    )

    print("=" * 70)


    print()
    print(
        "FFmpeg:"
    )

    print(
        FFMPEG_EXE
    )


    queue = load_queue()


    if not queue:

        print()
        print(
            "Article queue is empty."
        )

        return


    article = get_next_article(
        queue
    )


    if article is None:

        print()
        print(
            "No MEDIA_READY or VIDEO_FAILED "
            "article is waiting for rendering."
        )

        return


    title = clean_text(
        article.get(
            "title",
            "THRAANSH News"
        )
    )


    publisher = clean_text(
        article.get(
            "publisher"
        )
    )


    footage_path = (
        article.get(
            "footage_file"
        )
    )


    narration_path = (
        article.get(
            "voice_file"
        )
        or article.get(
            "audio_file"
        )
    )


    footage_file = Path(
        footage_path
    )


    narration_file = Path(
        narration_path
    )


    if not footage_file.exists():

        print()
        print(
            "ERROR: Footage file not found."
        )

        print(
            footage_file
        )

        return


    if not narration_file.exists():

        print()
        print(
            "ERROR: Hindi narration file not found."
        )

        print(
            narration_file
        )

        return


    print()
    print(
        "ARTICLE:"
    )

    print(
        title
    )


    print()
    print(
        "FOOTAGE:"
    )

    print(
        footage_file
    )


    print()
    print(
        "HINDI NARRATION:"
    )

    print(
        narration_file
    )


    # ========================================================
    # ENGLISH HEADLINE OVERLAY
    # ========================================================

    filename = safe_filename(
        title
    )


    overlay_file = (
        TEMP_FOLDER
        / (
            f"{filename}"
            f"_headline.png"
        )
    )


    create_headline_overlay(
        title,
        publisher,
        overlay_file
    )


    print()
    print(
        "English headline overlay:"
    )

    print(
        overlay_file
    )


    # ========================================================
    # BACKGROUND MUSIC
    # ========================================================

    music_file = (
        find_background_music()
    )


    if music_file:

        print()
        print(
            "Background music:"
        )

        print(
            music_file
        )

        print(
            f"Music volume: "
            f"{int(MUSIC_VOLUME * 100)}%"
        )

    else:

        print()
        print(
            "WARNING:"
        )

        print(
            "No background music file was found."
        )

        print(
            "Rendering with Hindi narration only."
        )

        print()
        print(
            "To add music to every video, put a "
            "licensed music file here:"
        )

        print(
            MUSIC_FOLDER
            / "background_music.mp3"
        )


    # ========================================================
    # FINAL OUTPUT
    # ========================================================

    output_file = (
        FINAL_VIDEO_FOLDER
        / (
            f"{filename}"
            f"_THRAANSH_FINAL.mp4"
        )
    )


    previous_status = clean_text(
        article.get(
            "status"
        )
    ).upper()


    try:

        print()
        print(
            "Rendering final THRAANSH video..."
        )


        print()
        print(
            "Video: 1920x1080"
        )

        print(
            "Visual text: English"
        )

        print(
            "Narration: Easy Hindi"
        )


        if music_file:

            print(
                "Background music: ON"
            )

            print(
                "Automatic music ducking: ON"
            )


            render_with_music(
                footage_file,
                narration_file,
                music_file,
                overlay_file,
                output_file
            )

        else:

            print(
                "Background music: OFF"
            )


            render_without_music(
                footage_file,
                narration_file,
                overlay_file,
                output_file
            )


        if not output_file.exists():

            raise RuntimeError(
                "Final MP4 was not created."
            )


        if (
            output_file.stat().st_size
            < 100_000
        ):

            raise RuntimeError(
                "Final MP4 is unexpectedly small."
            )


        # ====================================================
        # SUCCESS
        # ====================================================

        article[
            "final_video_file"
        ] = str(
            output_file
        )


        article[
            "video_status"
        ] = "READY"


        article[
            "video_width"
        ] = VIDEO_WIDTH


        article[
            "video_height"
        ] = VIDEO_HEIGHT


        article[
            "video_language"
        ] = "en"


        article[
            "narration_language"
        ] = "hi"


        article[
            "background_music"
        ] = bool(
            music_file
        )


        article[
            "music_volume"
        ] = (
            MUSIC_VOLUME
            if music_file
            else 0
        )


        article[
            "headline_language"
        ] = "en"


        article[
            "status"
        ] = "VIDEO_READY"


        article[
            "last_error"
        ] = None


        article[
            "video_generated_at"
        ] = (
            datetime.now().isoformat()
        )


        article[
            "updated_at"
        ] = (
            datetime.now().isoformat()
        )


        save_queue(
            queue
        )


        print()
        print("=" * 70)

        print(
            "VIDEO GENERATED SUCCESSFULLY"
        )

        print("=" * 70)


        print()
        print(
            "Final video:"
        )

        print(
            output_file
        )


        print()
        print(
            f"Size: "
            f"{output_file.stat().st_size / 1024 / 1024:.2f} MB"
        )


        print()
        print(
            "Language configuration:"
        )

        print(
            "Headline / visuals = English âœ“"
        )

        print(
            "Presenter voice = Easy Hindi âœ“"
        )


        if music_file:

            print(
                "Background music = Low + ducked âœ“"
            )

        else:

            print(
                "Background music = Missing"
            )


        print()
        print(
            "Status:"
        )

        print(
            f"{previous_status} -> VIDEO_READY"
        )


        print()
        print(
            "Next stage:"
        )

        print(
            "Preview final video before YouTube upload."
        )


    except Exception as error:

        article[
            "video_status"
        ] = "FAILED"


        article[
            "status"
        ] = "VIDEO_FAILED"


        article[
            "retry_count"
        ] = (
            article.get(
                "retry_count",
                0
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
            datetime.now().isoformat()
        )


        save_queue(
            queue
        )


        print()
        print("=" * 70)

        print(
            "VIDEO RENDERING FAILED"
        )

        print("=" * 70)


        print()
        print(
            "Error:"
        )

        print(
            error
        )


if __name__ == "__main__":

    main()


