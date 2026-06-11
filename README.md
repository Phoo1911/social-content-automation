# SNS Workflow

이미지에 있는 자동화 흐름을 기준으로 만든 `FastAPI + Python` 워크플로우 프로젝트입니다.

기본 모드는 `dry-run/mock` 이라서 외부 API 키 없이도 전체 파이프라인을 끝까지 실행해 볼 수 있습니다.

## 포함된 단계

1. 아이디어/입력 수집
2. 참고 이미지 분석 + 이미지 프롬프트 생성 + 이미지 생성
3. 광고용 영상 스크립트 생성
4. 영상 생성 요청 + 결과 아티팩트 저장
5. 여러 SNS 플랫폼으로 자동 배포

## 빠른 실행

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

서버 실행 후:

- `GET /`
- `GET /health`
- `POST /workflows/run`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /docs`

## 예시 요청

```json
{
  "idea": "여름철 피부 관리 팁을 20대 여성 대상으로 짧고 임팩트 있게 홍보",
  "caption_seed": "3초 안에 시선 잡는 뷰티 광고",
  "reference_image_urls": [
    "https://example.com/ref-1.jpg"
  ],
  "reference_video_url": "https://example.com/ref-video.mp4",
  "idea_candidate_count": 6,
  "auto_select_idea": true,
  "platforms": [
    "youtube",
    "instagram",
    "tiktok",
    "facebook"
  ],
  "dry_run": true
}
```

## 응답/저장

- 실행 결과는 `data/runs.jsonl` 에 누적 저장됩니다.
- 생성 산출물 메타데이터는 `artifacts/<run_id>/` 아래에 저장됩니다.

## 아이디어 발상 단계

워크플로우는 입력 아이디어를 바로 쓰지 않고, 중간에 다음 단계를 거칩니다.

1. `idea_candidate_count` 개수만큼 후보 생성
2. 후보별 `hook`, `angle`, `target_audience`, `cta` 생성
3. 자동 점수화 후 최상위 후보 선택
4. 선택된 후보를 이미지 프롬프트와 영상 스크립트에 반영

직접 후보를 고르고 싶으면 `auto_select_idea=false` 와 `selected_idea_index` 를 함께 보내면 됩니다.

## 실제 API 연동

현재 서비스 클래스는 기본적으로 mock 구현입니다.

- `app/services/llm.py`
- `app/services/image_generation.py`
- `app/services/video_generation.py`
- `app/services/publishers.py`

이 파일들에서 외부 API 호출 부분만 교체하면 동일한 워크플로우를 유지한 채 실서비스로 확장할 수 있습니다.

## Gemini 연결

- `LLM_PROVIDER=gemini`
- `GEMINI_API_KEY=...`
- `GEMINI_MODEL=gemini-2.5-flash`
- `GEMINI_IMAGE_MODEL=gemini-2.5-flash-image`
- `GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts`
- `GEMINI_TTS_VOICE=Kore`
- `GEMINI_VIDEO_MODEL=veo-3.1-generate-preview`

현재 기준으로 아이디어 후보 생성과 스크립트 생성은 Gemini를 사용할 수 있고, 키가 없거나 호출이 실패하면 자동으로 mock 로직으로 폴백합니다.

이미지 생성은 `gemini-2.5-flash-image`, 음성 생성은 `gemini-2.5-flash-preview-tts`를 사용하도록 연결되어 있습니다. 이 둘도 키가 없거나 호출이 실패하면 mock 결과로 폴백합니다.
비디오 생성은 `veo-3.1-generate-preview`를 사용하도록 연결되어 있으며, 호출이 실패하면 mock 결과로 폴백합니다.

## 생성 단계

`metadata.generation_stage` 값으로 어디까지 생성할지 고를 수 있습니다.

- `script`: 스크립트까지만 생성
- `image`: 이미지까지 생성
- `audio`: 음성까지 생성
- `video`: 동영상까지 생성
- `full`: 기존 전체 워크플로우와 업로드까지 진행

## YouTube 실제 업로드

YouTube OAuth를 끝내서 프로젝트 루트에 `token.json`이 있다면, `youtube` 플랫폼에 한해 실제 업로드를 시도할 수 있습니다.

- `dry_run`은 `false`여야 합니다.
- 현재 영상 생성 단계는 아직 mock이므로, 실제 업로드할 MP4 경로를 `metadata.video_file_path`에 넣어야 합니다.
- 아이디어 생성, 이미지 생성, 영상 생성은 로컬 테스트용 무료 mock으로 유지됩니다.

예시 요청:

```json
{
  "idea": "여름철 피부 관리 팁을 20대 여성 대상으로 짧고 임팩트 있게 홍보",
  "caption_seed": "3초 안에 시선 잡는 뷰티 광고",
  "platforms": ["youtube"],
  "dry_run": false,
  "metadata": {
    "video_file_path": "D:\\sns\\sample.mp4"
  }
}
```
