from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubePublisher:
    def __init__(self, token_file: Path) -> None:
        self.token_file = token_file

    def _load_credentials(self) -> Credentials:
        if not self.token_file.exists():
            raise FileNotFoundError(
                f"Missing YouTube token file: {self.token_file}. Run youtube_auth.py first."
            )

        creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self.token_file.write_text(creds.to_json(), encoding="utf-8")

        if not creds.valid:
            raise RuntimeError(
                "YouTube credentials are invalid. Re-run youtube_auth.py to refresh token.json."
            )

        return creds

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str] | None = None,
        privacy_status: str = "private",
    ) -> dict[str, str]:
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {path}")

        creds = self._load_credentials()
        youtube = build("youtube", "v3", credentials=creds)

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title[:100],
                    "description": description,
                    "tags": tags or [],
                },
                "status": {"privacyStatus": privacy_status},
            },
            media_body=MediaFileUpload(str(path), resumable=True),
        )
        response = request.execute()
        video_id = response["id"]
        return {
            "video_id": video_id,
            "permalink": f"https://www.youtube.com/watch?v={video_id}",
        }
