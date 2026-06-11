from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "sns-workflow"
    app_env: str = "local"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    workflow_storage_dir: Path = Path("./data")
    workflow_artifact_dir: Path = Path("./artifacts")
    default_platform_targets: str = Field(
        default="youtube,instagram,tiktok,facebook,linkedin,x,threads,bluesky,pinterest"
    )

    llm_provider: str = "gemini"
    openai_api_key: str | None = None
    openai_model: str = "mock-free"
    gemini_api_key: str | None = None
    gemini_video_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_image_model: str = "imagen-4.0-fast-generate-001"
    gemini_tts_model: str = "gemini-2.5-flash-preview-tts"
    gemini_tts_voice: str = "Kore"
    gemini_tts_language_code: str = "ko-KR"
    gemini_video_model: str = "veo-3.1-fast-generate-preview"
    gemini_video_aspect_ratio: str = "9:16"
    gemini_video_resolution: str = "720p"
    gemini_video_duration_seconds: int = 8
    gemini_video_poll_seconds: int = 10
    gemini_video_timeout_seconds: int = 420
    telegram_bot_token: str | None = None
    google_drive_folder_id: str | None = None
    google_sheets_spreadsheet_id: str | None = None
    nanobanana_api_url: str | None = None
    veo3_api_url: str | None = None
    blotato_api_url: str | None = None

    youtube_access_token: str | None = None
    meta_access_token: str | None = None
    linkedin_access_token: str | None = None
    x_access_token: str | None = None
    tiktok_access_token: str | None = None

    @property
    def platform_targets(self) -> list[str]:
        return [item.strip() for item in self.default_platform_targets.split(",") if item.strip()]


settings = Settings()
