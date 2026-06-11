from __future__ import annotations

import base64
import io
import wave
from typing import Any

import httpx

from app.config import settings
from app.services.artifacts import ArtifactManager


class AudioGenerationService:
    def __init__(self, artifacts: ArtifactManager) -> None:
        self.artifacts = artifacts
        self.provider = settings.llm_provider.lower()
        self.gemini_api_key = settings.gemini_api_key
        self.gemini_tts_model = settings.gemini_tts_model
        self.gemini_tts_voice = settings.gemini_tts_voice
        self.gemini_tts_language_code = settings.gemini_tts_language_code

    def _pcm_to_wav_bytes(self, pcm_data: bytes) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(24000)
            wav_file.writeframes(pcm_data)
        return buffer.getvalue()

    def _generate_gemini_tts(self, text: str) -> bytes:
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_tts_model}:generateContent",
            headers={
                "x-goog-api-key": self.gemini_api_key,
                "Content-Type": "application/json",
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": text,
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": self.gemini_tts_voice,
                            }
                        },
                        "languageCode": self.gemini_tts_language_code,
                    },
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
                pcm_bytes = base64.b64decode(inline["data"])
                return self._pcm_to_wav_bytes(pcm_bytes)
        raise ValueError("Gemini TTS response did not contain audio data")

    def create_audio(
        self,
        run_id: str,
        script_bundle: dict[str, Any],
        dry_run: bool,
        enabled: bool = True,
    ) -> dict[str, Any]:
        script = script_bundle["script"]
        text = script["voiceover"]

        if not enabled:
            return {
                "provider": "skipped-audio",
                "status": "skipped",
                "text": text,
                "audio_url": None,
            }

        if self.provider == "gemini" and self.gemini_api_key and not dry_run:
            try:
                wav_bytes = self._generate_gemini_tts(text)
                artifact_path = self.artifacts.write_bytes(run_id, "generated_audio.wav", wav_bytes)
                return {
                    "provider": self.gemini_tts_model,
                    "status": "completed",
                    "text": text,
                    "voice": self.gemini_tts_voice,
                    "language_code": self.gemini_tts_language_code,
                    "audio_url": None,
                    "artifact_path": str(artifact_path),
                    "mime_type": "audio/wav",
                }
            except Exception as exc:
                payload = {
                    "provider": "mock-free-tts",
                    "status": "fallback_mock",
                    "text": text,
                    "voice": self.gemini_tts_voice,
                    "language_code": self.gemini_tts_language_code,
                    "audio_url": f"https://mock.local/{run_id}/generated-audio.wav",
                    "warning": str(exc),
                }
                artifact_path = self.artifacts.write_json(run_id, "generated_audio.json", payload)
                payload["artifact_path"] = str(artifact_path)
                return payload

        payload = {
            "provider": "mock-free-tts",
            "status": "completed",
            "text": text,
            "voice": self.gemini_tts_voice,
            "language_code": self.gemini_tts_language_code,
            "audio_url": f"https://mock.local/{run_id}/generated-audio.wav",
        }
        artifact_path = self.artifacts.write_json(run_id, "generated_audio.json", payload)
        payload["artifact_path"] = str(artifact_path)
        return payload
