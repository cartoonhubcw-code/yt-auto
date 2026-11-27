import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def next_publish_time() -> str:
    """Next occurrence of the configured local time, at least 1 hour away, in UTC ISO format."""
    tz = ZoneInfo(config.PUBLISH_TZ)
    now = datetime.now(tz)
    t = now.replace(hour=config.PUBLISH_HOUR, minute=config.PUBLISH_MINUTE, second=0, microsecond=0)
    if t - now < timedelta(hours=1):
        t += timedelta(days=1)
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def upload(video: Path, thumb: Path, title, description, tags):
    yt = _service()
    publish_at = next_publish_time()
    tags = (list(tags) + config.DEFAULT_TAGS)[:15]
    while sum(len(t) + 1 for t in tags) > 450:
        tags.pop()
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": tags,
            "categoryId": config.CATEGORY_ID,
        },
        "status": {
            "privacyStatus": "private",      # required for scheduled publishing
            "publishAt": publish_at,
            "selfDeclaredMadeForKids": config.MADE_FOR_KIDS,
            "containsSyntheticMedia": config.AI_DISCLOSURE,
        },
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    vid = resp["id"]

    try:  # custom thumbnails need a phone-verified channel; don't fail the run if not
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb))).execute()
    except HttpError as e:
        print(f"[thumbnail] skipped: {e}")
    return vid, publish_at
