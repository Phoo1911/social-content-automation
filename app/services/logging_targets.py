from __future__ import annotations

from typing import Any


class GoogleSheetsLogger:
    def append(self, row_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "target": "google_sheets",
            "row_type": row_type,
            "logged": True,
            "payload_keys": sorted(payload.keys()),
        }


class GoogleDriveUploader:
    def upload_reference_images(self, image_urls: list[str]) -> dict[str, Any]:
        return {
            "target": "google_drive",
            "uploaded_count": len(image_urls),
            "folder": "mock-drive-folder",
        }
