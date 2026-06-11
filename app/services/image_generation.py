from __future__ import annotations

import base64
from typing import Any

import httpx

from app.config import settings
from app.services.artifacts import ArtifactManager


class ImageGenerationService:
    def __init__(self, artifacts: ArtifactManager) -> None:
        self.artifacts = artifacts
        self.provider = settings.llm_provider.lower()
        self.gemini_api_key = settings.gemini_api_key
        self.gemini_image_model = settings.gemini_image_model

    def _generate_gemini_image(self, prompt: str) -> tuple[bytes, str]:
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_image_model}:generateContent",
            headers={
                "x-goog-api-key": self.gemini_api_key,
                "Content-Type": "application/json",
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt,
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "responseModalities": ["IMAGE"],
                },
            },
            timeout=120.0,
        )
        response.raise_for_status()
        payload = response.json()
        parts = payload.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        for part in parts:
            inline = part.get("inlineData")
            if inline and inline.get("data"):
                mime_type = inline.get("mimeType", "image/png")
                return base64.b64decode(inline["data"]), mime_type
        raise ValueError("Gemini image response did not contain image data")

    def create_image(
        self,
        run_id: str,
        prompt_bundle: dict[str, Any],
        dry_run: bool,
        enabled: bool = True,
    ) -> dict[str, Any]:
        if not enabled:
            return {
                "provider": "skipped-image",
                "status": "skipped",
                "prompt": prompt_bundle["prompt"],
                "negative_prompt": prompt_bundle["negative_prompt"],
                "image_url": None,
            }

        if self.provider == "gemini" and self.gemini_api_key and not dry_run:
            try:
                image_bytes, mime_type = self._generate_gemini_image(prompt_bundle["prompt"])
                extension = ".png" if "png" in mime_type else ".jpg"
                artifact_path = self.artifacts.write_bytes(run_id, f"generated_image{extension}", image_bytes)
                return {
                    "provider": self.gemini_image_model,
                    "status": "completed",
                    "prompt": prompt_bundle["prompt"],
                    "negative_prompt": prompt_bundle["negative_prompt"],
                    "image_url": None,
                    "artifact_path": str(artifact_path),
                    "mime_type": mime_type,
                }
            except Exception as exc:
                payload = {
                    "provider": "mock-free-image",
                    "status": "fallback_mock",
                    "prompt": prompt_bundle["prompt"],
                    "negative_prompt": prompt_bundle["negative_prompt"],
                    "image_url": f"https://mock.local/{run_id}/generated-image.png",
                    "warning": str(exc),
                }
                artifact_path = self.artifacts.write_json(run_id, "generated_image.json", payload)
                payload["artifact_path"] = str(artifact_path)
                return payload

        payload = {
            "provider": "mock-free-image",
            "status": "completed",
            "prompt": prompt_bundle["prompt"],
            "negative_prompt": prompt_bundle["negative_prompt"],
            "image_url": f"https://mock.local/{run_id}/generated-image.png",
        }
        artifact_path = self.artifacts.write_json(run_id, "generated_image.json", payload)
        payload["artifact_path"] = str(artifact_path)
        return payload
