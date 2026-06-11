from __future__ import annotations

from typing import Any

from app.models import WorkflowRequest


class InputCollector:
    def collect(self, request: WorkflowRequest) -> dict[str, Any]:
        metadata = request.metadata if isinstance(request.metadata, dict) else {}
        topic_hint = str(metadata.get("topic_hint", "")).strip()
        audience_hint = str(metadata.get("audience_hint", "")).strip()
        channel_hint = str(metadata.get("channel_hint", "")).strip()

        return {
            "idea": request.idea.strip(),
            "caption_seed": (request.caption_seed or "").strip(),
            "reference_image_urls": request.reference_image_urls,
            "reference_video_url": request.reference_video_url,
            "metadata": metadata,
            "topic_hint": topic_hint,
            "audience_hint": audience_hint,
            "channel_hint": channel_hint,
            "source": "api",
        }
