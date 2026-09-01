import json
from pathlib import Path
from datetime import datetime

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


PROJECT_FOLDER = Path(__file__).resolve().parents[1]

CREDENTIALS_FOLDER = PROJECT_FOLDER / "credentials"
DATA_FOLDER = PROJECT_FOLDER / "data"

CLIENT_SECRET_FILE = CREDENTIALS_FOLDER / "youtube_client_secret.json"
TOKEN_FILE = CREDENTIALS_FOLDER / "youtube_token.json"
QUEUE_FILE = DATA_FOLDER / "article_queue.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload"
]


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


def get_youtube_service():

    credentials = None

    if TOKEN_FILE.exists():

        credentials = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES
        )

    if (
        credentials
        and credentials.expired
        and credentials.refresh_token
    ):

        credentials.refresh(
            Request()
        )

    if not credentials or not credentials.valid:

        flow = InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            SCOPES
        )

        credentials = flow.run_local_server(
            port=0
        )

        TOKEN_FILE.write_text(
            credentials.to_json(),
            encoding="utf-8"
        )

    return build(
        "youtube",
        "v3",
        credentials=credentials
    )


def get_next_video(queue):

    for article in queue:

        if article.get("status") != "VIDEO_READY":
            continue

        if article.get("youtube_video_id"):
            continue

        if article.get("rights_status") not in [
            "REVIEWED",
            "REVIEWED_WITH_WARNINGS"
        ]:
            continue

        final_video = article.get(
            "final_video_file"
        )

        if not final_video:
            continue

        if not Path(final_video).exists():
            continue

        return article

    return None


def build_description(article):

    source_link = article.get(
        "link",
        ""
    )

    description = (
        "Latest update from THRAANSH.\n\n"
        f"Source: {source_link}\n\n"
        "Stock footage source: Pexels\n"
        "https://www.pexels.com/\n\n"
        "THRAANSH\n"
        "News • Trends • Business • Technology • Sports • Entertainment"
    )

    return description


def upload_video(
    youtube,
    video_file,
    title,
    description
):

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title[:100],
                "description": description,
                "categoryId": "25"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        },
        media_body=MediaFileUpload(
            str(video_file),
            chunksize=-1,
            resumable=True
        )
    )

    return request.execute()


def main():

    print()
    print("=" * 70)
    print("THRAANSH YOUTUBE PUBLISHER")
    print("=" * 70)

    if not CLIENT_SECRET_FILE.exists():

        print()
        print("ERROR: OAuth credentials file missing:")
        print(CLIENT_SECRET_FILE)

        return

    queue = load_queue()

    if not queue:

        print()
        print("Article queue is empty.")
        return

    article = get_next_video(
        queue
    )

    if article is None:

        print()
        print(
            "No approved VIDEO_READY article "
            "is waiting for YouTube publishing."
        )

        return

    video_file = Path(
        article["final_video_file"]
    )

    title = article.get(
        "title",
        "THRAANSH News"
    )

    description = build_description(
        article
    )

    print()
    print("Publishing:")
    print(title)

    print()
    print("Video:")
    print(video_file)

    youtube = get_youtube_service()

    print()
    print("Uploading to YouTube as PUBLIC...")

    response = upload_video(
        youtube,
        video_file,
        title,
        description
    )

    video_id = response.get(
        "id"
    )

    if not video_id:

        raise RuntimeError(
            "YouTube upload completed but no video ID was returned."
        )

    article[
        "youtube_video_id"
    ] = video_id

    article[
        "youtube_url"
    ] = (
        f"https://www.youtube.com/watch?v={video_id}"
    )

    article[
        "youtube_upload_status"
    ] = "PUBLISHED"

    article[
        "youtube_published_at"
    ] = datetime.now().isoformat()

    save_queue(
        queue
    )

    print()
    print("=" * 70)
    print("YOUTUBE PUBLICATION SUCCESSFUL")
    print("=" * 70)

    print()
    print("Video ID:")
    print(video_id)

    print()
    print("YouTube URL:")
    print(
        article["youtube_url"]
    )

    print()
    print(
        "Duplicate protection enabled: "
        "this article will not upload again."
    )


if __name__ == "__main__":
    main()