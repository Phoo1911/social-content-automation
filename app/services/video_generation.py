from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import settings
from app.services.artifacts import ArtifactManager

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - optional dependency during migration
    genai = None
    types = None


class VideoGenerationService:
    def __init__(self, artifacts: ArtifactManager) -> None:
        self.artifacts = artifacts
        self.provider = settings.llm_provider.lower()
        self.gemini_api_key = settings.gemini_video_api_key or settings.gemini_api_key
        self.gemini_video_model = settings.gemini_video_model
        self.aspect_ratio = settings.gemini_video_aspect_ratio
        self.resolution = settings.gemini_video_resolution
        self.duration_seconds = settings.gemini_video_duration_seconds
        self.poll_seconds = settings.gemini_video_poll_seconds
        self.timeout_seconds = settings.gemini_video_timeout_seconds
        self.client = None
        if self.gemini_api_key and genai is not None:
            self.client = genai.Client(api_key=self.gemini_api_key)

    def _effective_duration_seconds(self) -> int:
        duration = self.duration_seconds
        model_name = self.gemini_video_model.lower()
        if "veo-3" in model_name:
            if duration in {4, 6, 8}:
                return duration
            return 8
        return duration

    def _mock_payload(
        self,
        run_id: str,
        script_bundle: dict[str, Any],
        visual_bundle: dict[str, Any],
        *,
        status: str,
        warning: str,
        fallback_reason: str,
    ) -> dict[str, Any]:
        payload = {
            "provider": "mock-free-video",
            "status": status,
            "video_url": f"https://mock.local/{run_id}/generated-video.mp4",
            "thumbnail_url": None,
            "script": script_bundle,
            "visual_prompt": visual_bundle.get("prompt"),
            "warning": warning,
            "fallback_reason": fallback_reason,
            "transport": "mock",
            "audio_muxed": False,
            "audio_note": "This pipeline expects Veo native audio. Separate TTS muxing is not used in the simplified two-model flow.",
            "requested_duration_seconds": self.duration_seconds,
            "effective_duration_seconds": self._effective_duration_seconds(),
        }
        artifact_path = self.artifacts.write_json(run_id, "generated_video.json", payload)
        payload["artifact_path"] = str(artifact_path)
        return payload

    def _build_prompt(self, script_bundle: dict[str, Any], visual_bundle: dict[str, Any]) -> str:
        scenes = " ".join(script_bundle.get("scene_plan", []))
        voiceover = script_bundle.get("voiceover", "")
        hook = script_bundle.get("hook", "")
        cta = script_bundle.get("cta", "")
        visual_prompt = str(visual_bundle.get("prompt", "")).strip()
        return (
            f"{hook} "
            f"{scenes} "
            f"Visual direction: {visual_prompt} "
            f'Spoken Korean narration or dialogue: "{voiceover}" '
            "Include native synced audio, clear Korean speech, relevant ambient sound effects, and natural room tone. "
            f"End with CTA: {cta}. "
            "Produce a polished short-form vertical social video."
        ).strip()

    def _extract_video_uri_from_operation(self, operation: dict[str, Any]) -> str:
        error = operation.get("error")
        if isinstance(error, dict) and error:
            message = error.get("message") or "Veo operation finished with an unknown error"
            code = error.get("code")
            status = error.get("status")
            raise RuntimeError(f"Veo operation failed ({status or code or 'unknown'}): {message}")

        response = operation.get("response", {})
        candidates: list[str | None] = [
            response.get("generateVideoResponse", {})
            .get("generatedSamples", [{}])[0]
            .get("video", {})
            .get("uri"),
            response.get("generatedVideo", {}).get("video", {}).get("uri"),
            response.get("generatedVideos", [{}])[0].get("video", {}).get("uri"),
        ]

        for candidate in candidates:
            if candidate:
                return candidate

        raise ValueError("Veo response did not contain a downloadable video URI")

    def _generate_with_sdk(self, run_id: str, prompt: str, visual_bundle: dict[str, Any], script_bundle: dict[str, Any]) -> dict[str, Any]:
        if self.client is None or types is None:
            raise RuntimeError("google-genai SDK is not available")

        config = types.GenerateVideosConfig(
            aspect_ratio=self.aspect_ratio,
            resolution=self.resolution,
            duration_seconds=self._effective_duration_seconds(),
        )
        operation = self.client.models.generate_videos(
            model=self.gemini_video_model,
            prompt=prompt,
            config=config,
        )
        while not operation.done:
            time.sleep(self.poll_seconds)
            operation = self.client.operations.get(operation)

        response = getattr(operation, "response", None)
        if response is None or not getattr(response, "generated_videos", None):
            raise RuntimeError("Veo SDK operation completed without generated videos in the response")

        generated_video = response.generated_videos[0]
        self.client.files.download(file=generated_video.video)
        artifact_path = self.artifacts.run_dir(run_id) / "generated_video.mp4"
        generated_video.video.save(str(artifact_path))
        return {
            "provider": self.gemini_video_model,
            "status": "completed",
            "video_url": getattr(generated_video.video, "uri", None),
            "thumbnail_url": None,
            "script": script_bundle,
            "visual_prompt": visual_bundle.get("prompt"),
            "artifact_path": str(artifact_path),
            "local_video_path": str(artifact_path),
            "operation_name": getattr(operation, "name", None),
            "transport": "google-genai-sdk",
            "audio_muxed": False,
            "audio_note": "Veo was prompted to generate native audio directly in the video.",
            "requested_duration_seconds": self.duration_seconds,
            "effective_duration_seconds": self._effective_duration_seconds(),
        }

    def _start_veo_operation(self, prompt: str) -> str:
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_video_model}:predictLongRunning",
            headers={
                "x-goog-api-key": self.gemini_api_key,
                "Content-Type": "application/json",
            },
            json={
                "instances": [
                    {
                        "prompt": prompt,
                    }
                ],
                "parameters": {
                    "aspectRatio": self.aspect_ratio,
                    "resolution": self.resolution,
                    "durationSeconds": self._effective_duration_seconds(),
                },
            },
            timeout=60.0,
        )
        response.raise_for_status()
        operation_name = response.json().get("name")
        if not operation_name:
            raise ValueError("Veo response did not include an operation name")
        return operation_name

    def _poll_veo_operation(self, operation_name: str) -> dict[str, Any]:
        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            response = httpx.get(
                f"https://generativelanguage.googleapis.com/v1beta/{operation_name}",
                headers={"x-goog-api-key": self.gemini_api_key},
                timeout=60.0,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("done") is True:
                return payload
            time.sleep(self.poll_seconds)
        raise TimeoutError("Timed out waiting for Veo video generation to complete")

    def _download_video(self, video_uri: str) -> bytes:
        response = httpx.get(
            video_uri,
            headers={"x-goog-api-key": self.gemini_api_key},
            follow_redirects=True,
            timeout=240.0,
        )
        response.raise_for_status()
        return response.content

    def create_video(
        self,
        run_id: str,
        script_bundle: dict[str, Any],
        visual_bundle: dict[str, Any],
        dry_run: bool,
        enabled: bool = True,
    ) -> dict[str, Any]:
        if not enabled:
            return {
                "provider": "skipped-video",
                "status": "skipped",
                "video_url": None,
                "thumbnail_url": None,
                "script": script_bundle,
                "visual_prompt": visual_bundle.get("prompt"),
                "transport": "skipped",
            }

        if self.provider == "gemini" and self.gemini_api_key and not dry_run:
            prompt = self._build_prompt(script_bundle, visual_bundle)
            try:
                if self.client is not None and types is not None:
                    return self._generate_with_sdk(run_id, prompt, visual_bundle, script_bundle)

                operation_name = self._start_veo_operation(prompt)
                operation = self._poll_veo_operation(operation_name)
                video_uri = self._extract_video_uri_from_operation(operation)
                video_bytes = self._download_video(video_uri)
                artifact_path = self.artifacts.write_bytes(run_id, "generated_video.mp4", video_bytes)
                return {
                    "provider": self.gemini_video_model,
                    "status": "completed",
                    "video_url": video_uri,
                    "thumbnail_url": None,
                    "script": script_bundle,
                    "visual_prompt": visual_bundle.get("prompt"),
                    "artifact_path": str(artifact_path),
                    "local_video_path": str(artifact_path),
                    "operation_name": operation_name,
                    "transport": "rest",
                    "audio_muxed": False,
                    "audio_note": "Veo was prompted to generate native audio directly in the video.",
                    "requested_duration_seconds": self.duration_seconds,
                    "effective_duration_seconds": self._effective_duration_seconds(),
                }
            except Exception as exc:
                return self._mock_payload(
                    run_id,
                    script_bundle,
                    visual_bundle,
                    status="fallback_mock",
                    warning=str(exc),
                    fallback_reason="veo_request_failed",
                )

        if dry_run:
            return self._mock_payload(
                run_id,
                script_bundle,
                visual_bundle,
                status="completed",
                warning="Video generation did not run against Veo because dry_run was enabled.",
                fallback_reason="dry_run_enabled",
            )

        if self.provider != "gemini":
            return self._mock_payload(
                run_id,
                script_bundle,
                visual_bundle,
                status="completed",
                warning=f"Video generation did not run against Veo because llm_provider is '{self.provider}', not 'gemini'.",
                fallback_reason="provider_not_gemini",
            )

        if not self.gemini_api_key:
            return self._mock_payload(
                run_id,
                script_bundle,
                visual_bundle,
                status="completed",
                warning="Video generation did not run against Veo because GEMINI_VIDEO_API_KEY and GEMINI_API_KEY were both empty.",
                fallback_reason="missing_video_api_key",
            )

        return self._mock_payload(
            run_id,
            script_bundle,
            visual_bundle,
            status="completed",
            warning="Video generation did not run against Veo because the google-genai SDK client was unavailable and the REST path was not selected.",
            fallback_reason="sdk_unavailable",
        )
