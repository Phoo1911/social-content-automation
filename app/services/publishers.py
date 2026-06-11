from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.models import PublishResult
from app.services.youtube_publisher import YouTubePublisher


class MultiPlatformPublisher:
    def __init__(self, settings: Settings) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.youtube = YouTubePublisher(project_root / "token.json")
        self.settings = settings

    def _mock_result(self, platform: str, run_id: str) -> PublishResult:
        external_id = f"{platform}_{run_id[:8]}"
        return PublishResult(
            platform=platform,
            success=True,
            external_id=external_id,
            permalink=f"https://mock.local/{platform}/{external_id}",
        )

    def _publish_youtube(
        self,
        run_id: str,
        title: str,
        caption: str,
        video_path: str | None,
    ) -> PublishResult:
        if not video_path:
            return PublishResult(
                platform="youtube",
                success=False,
                error=(
                    "YouTube upload needs a local video file path. "
                    "Set request.metadata.video_file_path or keep dry_run=true."
                ),
            )

        try:
            upload = self.youtube.upload_video(video_path, title, caption, tags=["shorts", "autosns"])
            return PublishResult(
                platform="youtube",
                success=True,
                external_id=upload["video_id"],
                permalink=upload["permalink"],
            )
        except Exception as exc:
            return PublishResult(
                platform="youtube",
                success=False,
                error=str(exc),
            )

    def publish(
        self,
        run_id: str,
        platforms: list[str],
        title: str,
        caption: str,
        video_url: str,
        *,
        video_path: str | None = None,
        dry_run: bool = True,
    ) -> list[PublishResult]:
        results: list[PublishResult] = []
        for platform in platforms:
            normalized = platform.lower()
            if normalized == "youtube" and not dry_run:
                results.append(self._publish_youtube(run_id, title, caption, video_path))
                continue

            results.append(self._mock_result(normalized, run_id))
        return results
