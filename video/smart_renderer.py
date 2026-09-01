import json
import subprocess
from pathlib import Path
from datetime import datetime

import imageio_ffmpeg


# ============================================================
# THRAANSH SMART VIDEO RENDERER
# ============================================================

PROJECT_FOLDER = Path(__file__).resolve().parents[1]

DATA_FOLDER = PROJECT_FOLDER / "data"
FINAL_VIDEO_FOLDER = PROJECT_FOLDER / "final_videos"
TEMP_FOLDER = PROJECT_FOLDER / "temp_smart_video"

QUEUE_FILE = DATA_FOLDER / "article_queue.json"

FINAL_VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)
TEMP_FOLDER.mkdir(parents=True, exist_ok=True)

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


# ============================================================
# LOAD QUEUE
# ============================================================

def load_queue():

    if not QUEUE_FILE.exists():
        print("ERROR: article_queue.json not found.")
        return []

    with open(
        QUEUE_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


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
# FIND ARTICLE READY FOR RENDER
# ============================================================

def get_next_article(queue):

    for article in queue:

        if article.get("status") == "SCENES_READY":

            if article.get("scene_files") and article.get("audio_file"):
                return article

    return None


# ============================================================
# SAFE FILE NAME
# ============================================================

def safe_filename(text):

    allowed = []

    for character in text:

        if character.isalnum() or character in (
            " ",
            "-",
            "_"
        ):
            allowed.append(character)

    filename = "".join(allowed).strip()

    filename = filename.replace(
        " ",
        "_"
    )

    if not filename:
        filename = "thraansh_video"

    return filename[:70]


# ============================================================
# GET AUDIO DURATION
# ============================================================

def get_audio_duration(audio_file):

    command = [
        FFMPEG_EXE,
        "-i",
        str(audio_file),
        "-f",
        "null",
        "-"
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    for line in result.stderr.splitlines():

        if "Duration:" in line:

            duration_text = (
                line.split("Duration:")[1]
                .split(",")[0]
                .strip()
            )

            hours, minutes, seconds = duration_text.split(":")

            return (
                int(hours) * 3600
                + int(minutes) * 60
                + float(seconds)
            )

    raise RuntimeError(
        "Could not detect narration duration."
    )


# ============================================================
# NORMALIZE SCENE
# ============================================================

def normalize_scene(
    scene_file,
    output_file,
    duration
):

    command = [
        FFMPEG_EXE,
        "-y",

        "-stream_loop",
        "-1",

        "-i",
        str(scene_file),

        "-t",
        str(duration),

        "-vf",
        (
            "scale=1280:720:"
            "force_original_aspect_ratio=decrease,"
            "pad=1280:720:"
            "(ow-iw)/2:(oh-ih)/2,"
            "fps=30"
        ),

        "-an",

        "-c:v",
        "libx264",

        "-preset",
        "fast",

        "-crf",
        "23",

        "-pix_fmt",
        "yuv420p",

        str(output_file)
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:

        print(result.stderr)

        raise RuntimeError(
            f"Failed preparing scene: {scene_file}"
        )


# ============================================================
# CONCATENATE SCENES
# ============================================================

def concatenate_scenes(
    scene_files,
    output_file
):

    list_file = TEMP_FOLDER / "scene_list.txt"

    with open(
        list_file,
        "w",
        encoding="utf-8"
    ) as file:

        for scene in scene_files:

            safe_path = str(scene).replace(
                "\\",
                "/"
            )

            file.write(
                f"file '{safe_path}'\n"
            )

    command = [
        FFMPEG_EXE,
        "-y",

        "-f",
        "concat",

        "-safe",
        "0",

        "-i",
        str(list_file),

        "-c",
        "copy",

        str(output_file)
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:

        print(result.stderr)

        raise RuntimeError(
            "Failed to combine scenes."
        )


# ============================================================
# ADD NARRATION
# ============================================================

def add_narration(
    video_file,
    audio_file,
    output_file
):

    command = [
        FFMPEG_EXE,
        "-y",

        "-i",
        str(video_file),

        "-i",
        str(audio_file),

        "-map",
        "0:v:0",

        "-map",
        "1:a:0",

        "-c:v",
        "libx264",

        "-preset",
        "medium",

        "-crf",
        "23",

        "-c:a",
        "aac",

        "-b:a",
        "192k",

        "-shortest",

        "-movflags",
        "+faststart",

        str(output_file)
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:

        print(result.stderr)

        raise RuntimeError(
            "Failed to add narration."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("THRAANSH SMART VIDEO RENDERER")
    print("=" * 70)

    queue = load_queue()

    if not queue:

        print()
        print("Article queue is empty.")
        return

    article = get_next_article(queue)

    if article is None:

        print()
        print(
            "No SCENES_READY article "
            "is waiting for rendering."
        )
        return

    title = article.get(
        "title",
        "THRAANSH Video"
    )

    audio_file = Path(
        article.get("audio_file")
    )

    scene_paths = article.get(
        "scene_files",
        []
    )

    print()
    print("ARTICLE:")
    print(title)

    print()
    print(
        f"Scene files received: {len(scene_paths)}"
    )

    if not audio_file.exists():

        print()
        print("ERROR: Audio file not found:")
        print(audio_file)

        return

    valid_scenes = []

    for scene_path in scene_paths:

        scene_file = Path(scene_path)

        if scene_file.exists():
            valid_scenes.append(scene_file)
        else:
            print()
            print("Missing scene:")
            print(scene_file)

    if not valid_scenes:

        print()
        print("ERROR: No valid scene files found.")
        return

    try:

        print()
        print("Detecting narration duration...")

        narration_duration = get_audio_duration(
            audio_file
        )

        scene_count = len(valid_scenes)

        scene_duration = (
            narration_duration
            / scene_count
        )

        print()
        print(
            f"Narration duration: "
            f"{narration_duration:.2f} seconds"
        )

        print(
            f"Scenes: {scene_count}"
        )

        print(
            f"Duration per scene: "
            f"{scene_duration:.2f} seconds"
        )

        normalized_scenes = []

        for number, scene_file in enumerate(
            valid_scenes,
            start=1
        ):

            print()
            print(
                f"Preparing scene "
                f"{number}/{scene_count}"
            )

            normalized_file = (
                TEMP_FOLDER
                / f"scene_{number}.mp4"
            )

            normalize_scene(
                scene_file,
                normalized_file,
                scene_duration
            )

            normalized_scenes.append(
                normalized_file
            )

        print()
        print("Combining smart scenes...")

        combined_video = (
            TEMP_FOLDER
            / "combined_video.mp4"
        )

        concatenate_scenes(
            normalized_scenes,
            combined_video
        )

        filename = safe_filename(
            title
        )

        final_video = (
            FINAL_VIDEO_FOLDER
            / f"{filename}_SMART_FINAL.mp4"
        )

        print()
        print(
            "Adding THRAANSH narration..."
        )

        add_narration(
            combined_video,
            audio_file,
            final_video
        )

        if not final_video.exists():

            raise RuntimeError(
                "Final video was not created."
            )

        article[
            "final_video_file"
        ] = str(final_video)

        article[
            "smart_video_file"
        ] = str(final_video)

        article[
            "video_duration_seconds"
        ] = round(
            narration_duration,
            2
        )

        article[
            "scene_duration_seconds"
        ] = round(
            scene_duration,
            2
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

        save_queue(queue)

        print()
        print("=" * 70)
        print("SMART VIDEO GENERATED SUCCESSFULLY")
        print("=" * 70)

        print()
        print("Final video:")
        print(final_video)

        print()
        print(
            f"Scenes used: "
            f"{scene_count}"
        )

        print(
            f"Final duration: "
            f"{narration_duration:.2f} seconds"
        )

        print()
        print(
            "SCENES_READY -> VIDEO_READY"
        )

    except Exception as error:

        article[
            "status"
        ] = "VIDEO_FAILED"

        article[
            "retry_count"
        ] = (
            article.get(
                "retry_count",
                0
            ) + 1
        )

        article[
            "last_error"
        ] = str(error)

        article[
            "updated_at"
        ] = datetime.now().isoformat()

        save_queue(queue)

        print()
        print("=" * 70)
        print("SMART VIDEO RENDER FAILED")
        print("=" * 70)

        print()
        print(error)


if __name__ == "__main__":
    main()