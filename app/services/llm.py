from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings


class LLMService:
    provider_name = "mock-free-llm"

    def __init__(self) -> None:
        self.provider = settings.llm_provider.lower()
        self.gemini_api_key = settings.gemini_api_key
        self.gemini_model = settings.gemini_model
        if self.provider == "gemini" and self.gemini_api_key:
            self.provider_name = self.gemini_model

    def _extract_text(self, payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates") or []
        if not candidates:
            raise ValueError("Gemini returned no candidates")

        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [part.get("text", "") for part in parts if isinstance(part, dict)]
        text = "".join(text_parts).strip()
        if not text:
            raise ValueError("Gemini returned an empty response")
        return text

    def _extract_json(self, text: str) -> dict[str, Any]:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("Model response did not contain valid JSON")
        return json.loads(text[start : end + 1])

    def _generate_gemini_json(self, prompt: str) -> dict[str, Any]:
        if not self.gemini_api_key:
            raise RuntimeError("Missing GEMINI_API_KEY")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent"
        response = httpx.post(
            url,
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
                    "temperature": 0.7,
                    "responseMimeType": "application/json",
                },
            },
            timeout=60.0,
        )
        response.raise_for_status()
        text = self._extract_text(response.json())
        return self._extract_json(text)

    def _generate_initial_brief_mock(self, metadata: dict[str, Any]) -> dict[str, str]:
        topic_hint = str(metadata.get("topic_hint", "")).strip()
        audience_hint = str(metadata.get("audience_hint", "")).strip() or "모바일 SNS 사용자"
        channel_hint = str(metadata.get("channel_hint", "")).strip() or "숏폼 정보형 채널"

        if topic_hint:
            idea = f"{topic_hint} {audience_hint} 대상 {channel_hint}"
            caption_seed = f"{topic_hint} 지금 바로 써먹는 핵심 팁"
        else:
            idea = f"{audience_hint}를 위한 실전형 {channel_hint}"
            caption_seed = "지금 바로 반응 오는 숏폼 한 가지"

        self.provider_name = "mock-free-llm"
        return {
            "idea": idea,
            "caption_seed": caption_seed,
        }

    def generate_initial_brief(self, metadata: dict[str, Any]) -> dict[str, str]:
        topic_hint = str(metadata.get("topic_hint", "")).strip()
        audience_hint = str(metadata.get("audience_hint", "")).strip()
        channel_hint = str(metadata.get("channel_hint", "")).strip()

        if self.provider == "gemini" and self.gemini_api_key:
            prompt = f"""
You are creating the starting brief for a Korean short-form social content workflow.
Return strict JSON with this shape:
{{
  "idea": "string",
  "caption_seed": "string"
}}

User input is empty, so you must invent the initial direction.

Hints:
- topic_hint: {topic_hint or "none"}
- audience_hint: {audience_hint or "none"}
- channel_hint: {channel_hint or "none"}

Requirements:
- Write in Korean.
- Make "idea" a concrete short-form content topic, not a generic system phrase.
- Make "caption_seed" a punchy hook seed suitable for the first line of a short-form ad or info clip.
- Avoid placeholders and avoid mentioning that the input was empty.
"""
            try:
                data = self._generate_gemini_json(prompt)
                idea = str(data.get("idea", "")).strip()
                caption_seed = str(data.get("caption_seed", "")).strip()
                if not idea or not caption_seed:
                    raise ValueError("Gemini response missing initial brief fields")
                self.provider_name = self.gemini_model
                return {
                    "idea": idea,
                    "caption_seed": caption_seed,
                }
            except Exception:
                pass

        return self._generate_initial_brief_mock(metadata)

    def _generate_idea_candidates_mock(
        self,
        idea: str,
        caption_seed: str,
        count: int,
    ) -> dict[str, Any]:
        audiences = [
            "busy professionals",
            "budget-conscious shoppers",
            "trend-sensitive Gen Z users",
            "young parents",
            "first-time buyers",
            "beauty-focused mobile users",
            "small business owners",
            "wellness-interested women in their 20s",
            "students who prefer quick tips",
            "impulse-driven social shoppers",
        ]
        angles = [
            "pain-point first",
            "before-after transformation",
            "myth-busting education",
            "fast checklist format",
            "social proof conversion",
            "time-saving shortcut",
            "premium aspiration",
            "budget-friendly hack",
            "seasonal relevance",
            "comparison challenge",
        ]
        ctas = [
            "Save this before your next purchase.",
            "Comment to get the full routine.",
            "Tap follow for the next part.",
            "Try this tonight and compare tomorrow.",
            "Send this to a friend who needs it.",
            "Shop now before the offer ends.",
            "Test this tip for 7 days.",
            "Screenshot this checklist.",
            "Watch until the end for the reveal.",
            "Use this before your next upload.",
        ]

        self.provider_name = "mock-free-llm"
        candidates: list[dict[str, Any]] = []
        for idx in range(count):
            audience = audiences[idx % len(audiences)]
            angle = angles[idx % len(angles)]
            cta = ctas[idx % len(ctas)]
            hook = f"{caption_seed}: {angle} for {audience}"
            candidates.append(
                {
                    "index": idx,
                    "title": f"{idea} concept {idx + 1}",
                    "hook": hook,
                    "angle": angle,
                    "target_audience": audience,
                    "cta": cta,
                    "concept_summary": (
                        f"Present {idea} with a {angle} structure designed for {audience}."
                    ),
                }
            )

        return {"candidates": candidates}

    def generate_idea_candidates(
        self,
        idea: str,
        caption_seed: str,
        count: int,
    ) -> dict[str, Any]:
        if self.provider == "gemini" and self.gemini_api_key:
            prompt = f"""
You are generating short-form social video ideas.
Return strict JSON with this shape:
{{
  "candidates": [
    {{
      "index": 0,
      "title": "string",
      "hook": "string",
      "angle": "string",
      "target_audience": "string",
      "cta": "string",
      "concept_summary": "string"
    }}
  ]
}}

Requirements:
- Generate exactly {count} candidates.
- Topic: {idea}
- Caption seed / hook seed: {caption_seed}
- Focus on punchy hooks and short-form marketing ideas.
- Keep each field concise and usable as-is.
"""
            try:
                data = self._generate_gemini_json(prompt)
                candidates = data.get("candidates")
                if not isinstance(candidates, list) or not candidates:
                    raise ValueError("Gemini response missing candidates")
                normalized = []
                for idx, item in enumerate(candidates[:count]):
                    normalized.append(
                        {
                            "index": idx,
                            "title": str(item.get("title", f"{idea} concept {idx + 1}")),
                            "hook": str(item.get("hook", caption_seed)),
                            "angle": str(item.get("angle", "pain-point first")),
                            "target_audience": str(item.get("target_audience", "short-form viewers")),
                            "cta": str(item.get("cta", "Save this for later.")),
                            "concept_summary": str(
                                item.get(
                                    "concept_summary",
                                    f"Present {idea} as a short-form video concept.",
                                )
                            ),
                        }
                    )
                self.provider_name = self.gemini_model
                return {"candidates": normalized}
            except Exception:
                pass

        return self._generate_idea_candidates_mock(idea, caption_seed, count)

    def score_idea_candidates(
        self,
        candidates: list[dict[str, Any]],
        base_idea: str,
    ) -> dict[str, Any]:
        normalized_idea = base_idea.lower()
        scored: list[dict[str, Any]] = []

        for candidate in candidates:
            angle = str(candidate["angle"])
            audience = str(candidate["target_audience"])
            score = 70

            if "pain" in angle or "transformation" in angle:
                score += 10
            if "Gen Z" in audience or "mobile" in audience:
                score += 8
            if "beauty" in normalized_idea or "skin" in normalized_idea:
                if "beauty" in audience or "women" in audience:
                    score += 7

            scored.append(
                {
                    **candidate,
                    "score": min(score, 100),
                    "reasoning": [
                        "Strong short-form hook structure.",
                        f"Audience fit: {audience}.",
                        f"Angle fit: {angle}.",
                    ],
                }
            )

        ranked = sorted(scored, key=lambda item: item["score"], reverse=True)
        return {"ranked_candidates": ranked, "selected_candidate": ranked[0]}

    def analyze_reference_images(self, image_urls: list[str], idea: str) -> dict[str, Any]:
        normalized = idea.lower()
        mood = (
            "clean beauty campaign"
            if "beauty" in normalized or "skin" in normalized
            else "high-conversion social ad"
        )
        return {
            "summary": f"Reference images suggest a {mood} with a strong hook in the first 3 seconds.",
            "visual_keywords": [
                "bold headline",
                "human-centered framing",
                "mobile-first composition",
                "high contrast CTA",
            ],
            "recommended_style": "cinematic vertical ad",
            "reference_count": len(image_urls),
        }

    def build_image_prompt(
        self,
        idea: str,
        analysis: dict[str, Any],
        caption_seed: str,
        selected_candidate: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        keywords = ", ".join(analysis.get("visual_keywords", []))
        candidate_context = ""
        if selected_candidate:
            candidate_context = (
                f" Audience: {selected_candidate['target_audience']}."
                f" Angle: {selected_candidate['angle']}."
                f" CTA: {selected_candidate['cta']}."
            )

        prompt = (
            "Create a high-performing vertical social ad visual. "
            f"Topic: {idea}. Hook: {caption_seed}. "
            f"Style: {analysis.get('recommended_style', 'social ad')}. "
            f"Keywords: {keywords}.{candidate_context}"
        )
        return {
            "prompt": prompt,
            "negative_prompt": "low contrast, cluttered layout, unreadable text, weak focal point",
        }

    def _generate_video_script_mock(
        self,
        idea: str,
        image_prompt: str,
        caption_seed: str,
        selected_candidate: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.provider_name = "mock-free-llm"
        selected_candidate = selected_candidate or {}
        audience = selected_candidate.get("target_audience", "short-form viewers")
        cta = selected_candidate.get("cta", "Save this for later.")
        angle = selected_candidate.get("angle", "pain-point first")

        return {
            "headline": caption_seed,
            "hook": f"{caption_seed} - show the problem in the first 3 seconds and pivot to the solution fast.",
            "angle": angle,
            "target_audience": audience,
            "cta": cta,
            "scene_plan": [
                "Scene 1: Pain point close-up with bold text overlay",
                "Scene 2: Product or solution reveal with benefit callout",
                "Scene 3: Social proof and urgency CTA",
            ],
            "voiceover": (
                f"Here is the fastest way to position {idea} for {audience}. "
                "Lead with the frustration, show the upgrade, and finish with one concrete action."
            ),
            "caption": f"{caption_seed}\n\n{cta}",
            "image_prompt_used": image_prompt,
        }

    def generate_video_script(
        self,
        idea: str,
        image_prompt: str,
        caption_seed: str,
        selected_candidate: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        selected_candidate = selected_candidate or {}
        if self.provider == "gemini" and self.gemini_api_key:
            prompt = f"""
You are writing a short-form social video script.
Return strict JSON with this shape:
{{
  "headline": "string",
  "hook": "string",
  "angle": "string",
  "target_audience": "string",
  "cta": "string",
  "scene_plan": ["string", "string", "string"],
  "voiceover": "string",
  "caption": "string"
}}

Topic: {idea}
Hook seed: {caption_seed}
Image prompt context: {image_prompt}
Preferred audience: {selected_candidate.get("target_audience", "short-form viewers")}
Preferred angle: {selected_candidate.get("angle", "pain-point first")}
Preferred CTA: {selected_candidate.get("cta", "Save this for later.")}

Requirements:
- Make it suitable for a short vertical video ad.
- Keep the hook punchy.
- Return exactly 3 scene_plan items.
"""
            try:
                data = self._generate_gemini_json(prompt)
                scene_plan = data.get("scene_plan")
                if not isinstance(scene_plan, list) or not scene_plan:
                    raise ValueError("Gemini response missing scene plan")
                self.provider_name = self.gemini_model
                return {
                    "headline": str(data.get("headline", caption_seed)),
                    "hook": str(
                        data.get(
                            "hook",
                            f"{caption_seed} - show the problem in the first 3 seconds and pivot to the solution fast.",
                        )
                    ),
                    "angle": str(data.get("angle", selected_candidate.get("angle", "pain-point first"))),
                    "target_audience": str(
                        data.get("target_audience", selected_candidate.get("target_audience", "short-form viewers"))
                    ),
                    "cta": str(data.get("cta", selected_candidate.get("cta", "Save this for later."))),
                    "scene_plan": [str(item) for item in scene_plan[:3]],
                    "voiceover": str(data.get("voiceover", "")),
                    "caption": str(data.get("caption", caption_seed)),
                    "image_prompt_used": image_prompt,
                }
            except Exception:
                pass

        return self._generate_video_script_mock(idea, image_prompt, caption_seed, selected_candidate)

    def rewrite_caption_for_video(self, script: dict[str, Any]) -> str:
        return f"{script['headline']}\n\n{script['voiceover']}\n\n#shorts #reels #tiktok"
