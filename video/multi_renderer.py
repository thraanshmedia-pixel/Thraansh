import json
import subprocess
from pathlib import Path

import imageio_ffmpeg

PROJECT = Path(__file__).resolve().parents[1]

QUEUE = PROJECT / "data" / "article_queue.json"

FINAL = PROJECT / "final_videos"

TEMP = PROJECT / "temp"

FINAL.mkdir(exist_ok=True)
TEMP.mkdir(exist_ok=True)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def load():

    return json.load(
        open(QUEUE, encoding="utf-8")
    )


def save(q):

    json.dump(
        q,
        open(QUEUE, "w", encoding="utf-8"),
        indent=2,
        ensure_ascii=False
    )


def main():

    q = load()

    article = next(
        a for a in q
        if a.get("status") == "MULTI_MEDIA_READY"
    )

    scenes = article[
        "scene_footage_files"
    ]

    audio = (
        article.get("voice_file")
        or article.get("audio_file")
    )

    list_file = TEMP / "scenes.txt"

    with open(
        list_file,
        "w",
        encoding="utf-8"
    ) as f:

        for scene in scenes:

            p = Path(scene).resolve()

            f.write(
                f"file '{p.as_posix()}'\n"
            )

    joined = TEMP / "joined.mp4"

    cmd1 = [

        FFMPEG,

        "-y",

        "-f",
        "concat",

        "-safe",
        "0",

        "-i",
        str(list_file),

        "-vf",
        "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",

        "-c:v",
        "libx264",

        "-pix_fmt",
        "yuv420p",

        str(joined)
    ]

    subprocess.run(
        cmd1,
        check=True
    )

    output = (
        FINAL
        / "THRAANSH_MULTI_SCENE.mp4"
    )

    cmd2 = [

        FFMPEG,

        "-y",

        "-stream_loop",
        "-1",

        "-i",
        str(joined),

        "-i",
        str(audio),

        "-map",
        "0:v:0",

        "-map",
        "1:a:0",

        "-c:v",
        "libx264",

        "-c:a",
        "aac",

        "-shortest",

        str(output)
    ]

    subprocess.run(
        cmd2,
        check=True
    )

    article[
        "final_video_file"
    ] = str(output)

    article[
        "status"
    ] = "VIDEO_READY"

    save(q)

    print()
    print("MULTI_MEDIA_READY -> VIDEO_READY")

    print("Final video:")
    print(output)


if __name__ == "__main__":
    main()