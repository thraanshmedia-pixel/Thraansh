import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import imageio_ffmpeg
from PIL import Image


# ============================================================
# THRAANSH ULTRA-FAST STORY VIDEO RENDERER
#
# MAIN FIX:
# Images are resized ONCE with Pillow.
# FFmpeg does not repeatedly resize huge images frame-by-frame.
#
# VIDEO:
# 1280x720
# 24 FPS
#
# AUDIO:
# Easy Hindi narration
# Background instrumental music
#
# MEDIA:
# Story-specific files only
# No presenter fallback
# No duplicate files
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

FINAL_FOLDER = (
    PROJECT_FOLDER
    / "final_videos"
)

MUSIC_FILE = (
    PROJECT_FOLDER
    / "music"
    / "background_music.mp3"
)


TEMP_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)

PREPARED_IMAGE_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)

FINAL_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# FFMPEG
# ============================================================

FFMPEG_EXE = Path(
    imageio_ffmpeg.get_ffmpeg_exe()
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


# ============================================================
# AUDIO SETTINGS
# ============================================================

AUDIO_CODEC = "aac"

AUDIO_BITRATE = "192k"

AUDIO_SAMPLE_RATE = 44100

VOICE_VOLUME = 1.0

MUSIC_VOLUME = 0.08


# ============================================================
# RULES
# ============================================================

MIN_SCENES = 3


# ============================================================
# FILE TYPES
# ============================================================

VIDEO_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mov",
    ".mkv",
    ".avi",
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
    ".tif",
    ".tiff",
}

AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".flac",
    ".opus",
}


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

    return value[:100]


# ============================================================
# QUEUE
# ============================================================

def load_queue():

    if not QUEUE_FILE.exists():

        raise RuntimeError(
            "article_queue.json not found."
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
            "article_queue.json must contain a list."
        )

    return data


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
# ARTICLE
# ============================================================

def get_next_article(queue):

    for article in queue:

        if not article.get(
            "production_selected"
        ):
            continue

        status = clean_text(
            article.get(
                "status"
            )
        ).upper()

        if status in {
            "MULTI_MEDIA_READY",
            "MULTI_VIDEO_FAILED",
        }:

            return article

    for article in queue:

        status = clean_text(
            article.get(
                "status"
            )
        ).upper()

        if status in {
            "MULTI_MEDIA_READY",
            "MULTI_VIDEO_FAILED",
        }:

            return article

    return None


# ============================================================
# FFMPEG RUNNER
# ============================================================

def run_ffmpeg(arguments):

    command = [
        str(FFMPEG_EXE)
    ] + arguments

    print()
    print(
        "Running FFmpeg..."
    )

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    if result.returncode != 0:

        print()
        print("=" * 72)

        print(
            "FFMPEG FAILED"
        )

        print("=" * 72)

        print()
        print(
            result.stderr
        )

        raise RuntimeError(
            "FFmpeg command failed."
        )

    print()
    print(
        "FFmpeg completed successfully ✓"
    )


# ============================================================
# MEDIA INSPECTION
# ============================================================

def inspect_media(path):

    result = subprocess.run(
        [
            str(FFMPEG_EXE),
            "-hide_banner",
            "-i",
            str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    return (
        result.stdout
        + "\n"
        + result.stderr
    )


def get_duration(path):

    information = inspect_media(
        path
    )

    match = re.search(
        r"Duration:\s*"
        r"(\d+):"
        r"(\d+):"
        r"(\d+(?:\.\d+)?)",
        information
    )

    if not match:

        raise RuntimeError(
            f"Could not determine duration: {path}"
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

    duration = (
        hours * 3600
        + minutes * 60
        + seconds
    )

    if duration <= 0:

        raise RuntimeError(
            f"Invalid duration: {path}"
        )

    return duration


def has_video_stream(path):

    information = inspect_media(
        path
    )

    return bool(
        re.search(
            r"Stream\s+#.*Video:",
            information,
            re.IGNORECASE
        )
    )


def has_audio_stream(path):

    information = inspect_media(
        path
    )

    return bool(
        re.search(
            r"Stream\s+#.*Audio:",
            information,
            re.IGNORECASE
        )
    )


# ============================================================
# FIND VOICE
# ============================================================

def find_voice_file(article):

    fields = [
        "voice_file",
        "audio_file",
        "narration_file",
        "voice_path",
        "audio_path",
    ]

    for field in fields:

        value = clean_text(
            article.get(
                field
            )
        )

        if not value:
            continue

        path = Path(
            value
        )

        if (
            path.exists()
            and path.is_file()
        ):

            return path

    audio_folder = (
        PROJECT_FOLDER
        / "audio"
    )

    if not audio_folder.exists():
        return None

    title = safe_filename(
        article.get(
            "title"
        )
    ).lower()

    candidates = []

    for file in audio_folder.iterdir():

        if not file.is_file():
            continue

        if (
            file.suffix.lower()
            not in AUDIO_EXTENSIONS
        ):
            continue

        file_title = safe_filename(
            file.stem
        ).lower()

        if (
            title[:35] in file_title
            or
            file_title[:35] in title
        ):

            candidates.append(
                file
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item:
            item.stat().st_mtime,
        reverse=True
    )

    return candidates[0]


# ============================================================
# STORY SCENES
# ============================================================

def get_valid_scenes(article):

    scenes = article.get(
        "scene_plan",
        []
    )

    if not isinstance(
        scenes,
        list
    ):

        return []

    valid = []

    used_files = set()

    story_folder = (
        SCENE_FOLDER.resolve()
    )

    for scene in scenes:

        if not isinstance(
            scene,
            dict
        ):
            continue

        file_value = clean_text(
            scene.get(
                "footage_file"
            )
        )

        if not file_value:
            continue

        path = Path(
            file_value
        )

        if not path.exists():
            continue

        resolved = path.resolve()

        # ====================================================
        # STORY MEDIA ONLY
        # ====================================================

        if story_folder not in resolved.parents:

            print(
                "Rejected external/default media:",
                resolved
            )

            continue

        identity = str(
            resolved
        ).lower()

        if identity in used_files:

            print(
                "Duplicate scene skipped:",
                resolved.name
            )

            continue

        extension = (
            resolved.suffix.lower()
        )

        if extension in IMAGE_EXTENSIONS:

            media_type = "IMAGE"

        elif extension in VIDEO_EXTENSIONS:

            if not has_video_stream(
                resolved
            ):

                print(
                    "Rejected non-video:",
                    resolved
                )

                continue

            media_type = "VIDEO"

        else:

            continue

        valid.append(
            {
                "path":
                    resolved,

                "type":
                    media_type,
            }
        )

        used_files.add(
            identity
        )

    return valid


# ============================================================
# PILLOW IMAGE PREPARATION
# ============================================================

def prepare_image(
    source,
    destination
):

    print()
    print(
        "Preparing image with Pillow..."
    )

    with Image.open(
        source
    ) as image:

        image = image.convert(
            "RGB"
        )

        source_width = (
            image.width
        )

        source_height = (
            image.height
        )

        # ----------------------------------------------------
        # SCALE TO FIT
        # ----------------------------------------------------

        scale = min(
            WIDTH / source_width,
            HEIGHT / source_height
        )

        resized_width = max(
            1,
            int(
                source_width
                * scale
            )
        )

        resized_height = max(
            1,
            int(
                source_height
                * scale
            )
        )

        image = image.resize(
            (
                resized_width,
                resized_height
            ),
            Image.Resampling.LANCZOS
        )

        # ----------------------------------------------------
        # CREATE BLACK 720P CANVAS
        # ----------------------------------------------------

        canvas = Image.new(
            "RGB",
            (
                WIDTH,
                HEIGHT
            ),
            (
                0,
                0,
                0
            )
        )

        x = (
            WIDTH
            - resized_width
        ) // 2

        y = (
            HEIGHT
            - resized_height
        ) // 2

        canvas.paste(
            image,
            (
                x,
                y
            )
        )

        canvas.save(
            destination,
            "JPEG",
            quality=90,
            optimize=True
        )

    print(
        "Prepared image ✓"
    )


# ============================================================
# IMAGE TO VIDEO
# ============================================================

def render_image_scene(
    source,
    destination,
    duration,
    number
):

    prepared_image = (
        PREPARED_IMAGE_FOLDER
        / f"prepared_{number:02d}.jpg"
    )

    prepare_image(
        source,
        prepared_image
    )

    # ========================================================
    # FFmpeg now receives an already-prepared 1280x720 image.
    #
    # No scale filter.
    # No zoom.
    # No pad.
    # No resize workload.
    # ========================================================

    run_ffmpeg(
        [
            "-y",

            "-loop",
            "1",

            "-framerate",
            str(FPS),

            "-i",
            str(prepared_image),

            "-t",
            f"{duration:.3f}",

            "-an",

            "-c:v",
            VIDEO_CODEC,

            "-preset",
            VIDEO_PRESET,

            "-crf",
            VIDEO_CRF,

            "-pix_fmt",
            "yuv420p",

            "-r",
            str(FPS),

            str(destination),
        ]
    )


# ============================================================
# VIDEO SCENE
# ============================================================

def render_video_scene(
    source,
    destination,
    duration
):

    video_filter = (
        f"scale={WIDTH}:{HEIGHT}:"
        "force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:"
        "(ow-iw)/2:(oh-ih)/2,"
        "setsar=1,"
        f"fps={FPS},"
        "format=yuv420p"
    )

    run_ffmpeg(
        [
            "-y",

            "-stream_loop",
            "-1",

            "-i",
            str(source),

            "-t",
            f"{duration:.3f}",

            "-an",

            "-vf",
            video_filter,

            "-c:v",
            VIDEO_CODEC,

            "-preset",
            VIDEO_PRESET,

            "-crf",
            VIDEO_CRF,

            "-pix_fmt",
            "yuv420p",

            "-r",
            str(FPS),

            str(destination),
        ]
    )


# ============================================================
# JOIN SCENES
# ============================================================

def join_scenes(rendered_files):

    list_file = (
        TEMP_FOLDER
        / "scene_list.txt"
    )

    with open(
        list_file,
        "w",
        encoding="utf-8"
    ) as file:

        for video in rendered_files:

            file.write(
                f"file '{video.resolve().as_posix()}'\n"
            )

    joined_file = (
        TEMP_FOLDER
        / "joined_scenes.mp4"
    )

    run_ffmpeg(
        [
            "-y",

            "-f",
            "concat",

            "-safe",
            "0",

            "-i",
            str(list_file),

            "-c",
            "copy",

            str(joined_file),
        ]
    )

    return joined_file


# ============================================================
# FINAL AUDIO MIX
# ============================================================

def render_final(
    joined_video,
    voice_file,
    output_file,
    voice_duration
):

    if MUSIC_FILE.exists():

        print()
        print(
            "Background music: ON"
        )

        print(
            f"Music volume: "
            f"{int(MUSIC_VOLUME * 100)}%"
        )

        filter_complex = (
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
                str(joined_video),

                "-i",
                str(voice_file),

                "-stream_loop",
                "-1",

                "-i",
                str(MUSIC_FILE),

                "-filter_complex",
                filter_complex,

                "-map",
                "0:v:0",

                "-map",
                "[audio]",

                "-t",
                f"{voice_duration:.3f}",

                "-c:v",
                "copy",

                "-c:a",
                AUDIO_CODEC,

                "-b:a",
                AUDIO_BITRATE,

                "-ar",
                str(AUDIO_SAMPLE_RATE),

                "-ac",
                "2",

                "-movflags",
                "+faststart",

                str(output_file),
            ]
        )

        return True

    print()
    print(
        "Background music: OFF"
    )

    run_ffmpeg(
        [
            "-y",

            "-stream_loop",
            "-1",

            "-i",
            str(joined_video),

            "-i",
            str(voice_file),

            "-map",
            "0:v:0",

            "-map",
            "1:a:0",

            "-t",
            f"{voice_duration:.3f}",

            "-c:v",
            "copy",

            "-c:a",
            AUDIO_CODEC,

            "-b:a",
            AUDIO_BITRATE,

            str(output_file),
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


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 72)

    print(
        "THRAANSH ULTRA-FAST STORY RENDERER"
    )

    print("=" * 72)

    print()
    print(
        "Resolution: 1280x720"
    )

    print(
        "FPS: 24"
    )

    print(
        "Pillow pre-resize enabled ✓"
    )

    print(
        "Presenter fallback disabled ✓"
    )

    print()
    print(
        "FFmpeg:"
    )

    print(
        FFMPEG_EXE
    )

    if not FFMPEG_EXE.exists():

        print()
        print(
            "ERROR: bundled FFmpeg missing."
        )

        return

    # ========================================================
    # LOAD ARTICLE
    # ========================================================

    queue = load_queue()

    article = get_next_article(
        queue
    )

    if article is None:

        print()
        print(
            "No render-ready article."
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
    # VOICE
    # ========================================================

    voice_file = find_voice_file(
        article
    )

    if voice_file is None:

        print()
        print(
            "ERROR: Hindi voice not found."
        )

        return

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
    # SCENES
    # ========================================================

    scenes = get_valid_scenes(
        article
    )

    print()
    print(
        "Story scenes:",
        len(scenes)
    )

    if len(
        scenes
    ) < MIN_SCENES:

        print()
        print(
            "ERROR:"
        )

        print(
            "At least 3 story visuals required."
        )

        return

    scene_duration = (
        voice_duration
        / len(scenes)
    )

    # ========================================================
    # RENDER
    # ========================================================

    try:

        clean_temp()

        rendered_files = []

        for number, scene in enumerate(
            scenes,
            start=1
        ):

            destination = (
                TEMP_FOLDER
                / f"scene_{number:02d}.mp4"
            )

            print()
            print("=" * 60)

            print(
                f"SCENE {number}"
            )

            print("=" * 60)

            print(
                "Type:",
                scene["type"]
            )

            print(
                "Source:",
                scene["path"]
            )

            print(
                f"Duration: "
                f"{scene_duration:.2f}s"
            )

            if (
                scene["type"]
                == "IMAGE"
            ):

                render_image_scene(
                    scene["path"],
                    destination,
                    scene_duration,
                    number
                )

            else:

                render_video_scene(
                    scene["path"],
                    destination,
                    scene_duration
                )

            rendered_files.append(
                destination
            )

            print()
            print(
                f"Scene {number} ready ✓"
            )

        # ====================================================
        # JOIN
        # ====================================================

        print()
        print("=" * 72)

        print(
            "JOINING SCENES"
        )

        print("=" * 72)

        joined_video = join_scenes(
            rendered_files
        )

        # ====================================================
        # FINAL
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
        print("=" * 72)

        print(
            "FINAL VIDEO RENDER"
        )

        print("=" * 72)

        music_used = render_final(
            joined_video,
            voice_file,
            output_file,
            voice_duration
        )

        if not output_file.exists():

            raise RuntimeError(
                "Final MP4 not created."
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
            "video_resolution"
        ] = "1280x720"

        article[
            "video_fps"
        ] = FPS

        article[
            "background_music_enabled"
        ] = music_used

        article[
            "video_render_policy"
        ] = (
            "PILLOW_FAST_STORY_ONLY"
        )

        article[
            "status"
        ] = "VIDEO_READY"

        article[
            "last_error"
        ] = None

        article[
            "updated_at"
        ] = datetime.now().isoformat()

        save_queue(
            queue
        )

        print()
        print("=" * 72)

        print(
            "THRAANSH VIDEO READY"
        )

        print("=" * 72)

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
            f"{size_mb:.2f} MB"
        )

        print()
        print(
            "720p ✓"
        )

        print(
            "Fast Pillow images ✓"
        )

        print(
            "Story-only visuals ✓"
        )

        print(
            "No presenter fallback ✓"
        )

        print(
            "Hindi narration ✓"
        )

        if music_used:

            print(
                "Background music ✓"
            )

        print()
        print(
            "Status:"
        )

        print(
            f"{previous_status} "
            "-> VIDEO_READY"
        )

    except Exception as error:

        article[
            "status"
        ] = "MULTI_VIDEO_FAILED"

        article[
            "last_error"
        ] = str(
            error
        )

        article[
            "updated_at"
        ] = datetime.now().isoformat()

        save_queue(
            queue
        )

        print()
        print("=" * 72)

        print(
            "RENDER FAILED"
        )

        print("=" * 72)

        print()
        print(
            error
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()