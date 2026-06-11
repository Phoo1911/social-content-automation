# Social Content Automation

FastAPI and Python based workflow server for turning a content idea into social-ready assets and distribution steps.

This project is designed for rapid experimentation with short-form social campaigns:

- collect or auto-complete an idea brief
- generate idea candidates and score them
- analyze reference images and build a visual direction
- generate video copy and caption variations
- generate audio and video artifacts
- publish to multiple social platforms

The default mode is `dry_run=true`, so you can test the full pipeline without immediately pushing content to external platforms.

## What It Does

The workflow is centered around `POST /workflows/run`.

Main pipeline stages:

1. `collect_idea`
2. `generate_idea_candidates`
3. `create_image`
4. `generate_script`
5. `generate_audio`
6. `generate_video`
7. `auto_post`

You can also stop the pipeline earlier by setting `metadata.generation_stage`.

Supported generation stages:

- `ideation`: stop after idea candidate generation
- `script`: stop after script generation
- `video`: stop after video generation
- `full`: generate and continue to publishing

Note:

- `create_image` is currently used as a visual-direction stage based on reference analysis
- it does not mean this project is generating final image assets as a core output

## Tech Stack

- Python
- FastAPI
- Pydantic
- Uvicorn
- Google Gemini / Veo integration hooks
- YouTube OAuth upload helper

## Project Structure

```text
app/
  main.py                  FastAPI entry point
  workflow.py              end-to-end workflow orchestration
  models.py                request/response models
  config.py                environment-based settings
  storage.py               run history persistence
  services/
    llm.py                 idea/script/caption generation
    image_generation.py    visual prompt or image integration hooks
    video_generation.py    audio/video generation integration
    publishers.py          multi-platform publishing
    youtube_publisher.py   YouTube upload support
  static/
    index.html             simple web UI

artifacts/                 generated outputs and metadata
data/                      run history storage
youtube_auth.py            YouTube OAuth bootstrap helper
```

## Quick Start

### 1. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```powershell
copy .env.example .env
```

At minimum, the project runs in mock or dry-run mode without filling every API key.

### 3. Start the API server

```powershell
uvicorn app.main:app --reload
```

Default local addresses:

- App: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

## API Endpoints

- `GET /` - static UI
- `GET /health` - health check
- `POST /workflows/run` - start a workflow run
- `GET /runs` - list previous runs
- `GET /runs/{run_id}` - fetch one run
- `GET /docs` - interactive API docs

## Example Request

```json
{
  "idea": "Promote summer skincare tips for women in their 20s with a short, high-impact ad concept.",
  "caption_seed": "A beauty hook that grabs attention within 3 seconds.",
  "reference_image_urls": [
    "https://example.com/ref-1.jpg"
  ],
  "reference_video_url": "https://example.com/ref-video.mp4",
  "platforms": [
    "youtube",
    "instagram",
    "tiktok"
  ],
  "idea_candidate_count": 6,
  "auto_select_idea": true,
  "dry_run": true,
  "metadata": {
    "generation_stage": "full"
  }
}
```

## Request Model Notes

Important request fields:

- `idea`: base campaign or content idea
- `caption_seed`: short hook or copy direction
- `reference_image_urls`: inspiration or style references used to shape visual direction
- `reference_video_url`: optional reference video
- `platforms`: target platforms for publishing
- `idea_candidate_count`: number of idea options to generate, from 1 to 10
- `auto_select_idea`: automatically choose the top-ranked idea
- `selected_idea_index`: use this when `auto_select_idea=false`
- `dry_run`: keep publishing in simulation mode
- `metadata.generation_stage`: stop at `ideation`, `script`, `video`, or run `full`
- `metadata.video_file_path`: local MP4 path used when doing a real YouTube upload

## Output Storage

Run and artifact data are stored locally:

- `data/runs.jsonl`: workflow execution history
- `artifacts/<run_id>/`: generated metadata and media outputs

These paths are intentionally excluded from Git tracking in `.gitignore`.

## Environment Variables

Core app settings from `.env.example`:

```env
APP_NAME=sns-workflow
APP_ENV=local
APP_HOST=127.0.0.1
APP_PORT=8000
WORKFLOW_STORAGE_DIR=./data
WORKFLOW_ARTIFACT_DIR=./artifacts
DEFAULT_PLATFORM_TARGETS=youtube,instagram,tiktok,facebook,linkedin,x,threads,bluesky,pinterest
```

Generation-related settings:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_VIDEO_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts
GEMINI_TTS_VOICE=Kore
GEMINI_TTS_LANGUAGE_CODE=ko-KR
GEMINI_VIDEO_MODEL=veo-3.1-fast-generate-preview
GEMINI_VIDEO_ASPECT_RATIO=9:16
GEMINI_VIDEO_RESOLUTION=720p
GEMINI_VIDEO_DURATION_SECONDS=8
```

Platform and integration tokens:

```env
GOOGLE_DRIVE_FOLDER_ID=
GOOGLE_SHEETS_SPREADSHEET_ID=
YOUTUBE_ACCESS_TOKEN=
META_ACCESS_TOKEN=
LINKEDIN_ACCESS_TOKEN=
X_ACCESS_TOKEN=
TIKTOK_ACCESS_TOKEN=
```

If Gemini or publishing credentials are missing, parts of the workflow can still run using mock or fallback behavior depending on the service path.

## YouTube Upload Setup

This repository includes `youtube_auth.py` for local OAuth bootstrap.

### 1. Add OAuth client secrets

Place your Google OAuth desktop client file at:

- `client_secrets.json`

### 2. Generate `token.json`

```powershell
python youtube_auth.py
```

This opens a local OAuth flow and stores the result in `token.json`.

### 3. Run a real YouTube upload

To attempt a real YouTube upload:

- include `"youtube"` in `platforms`
- set `"dry_run": false`
- provide a valid local MP4 path in `metadata.video_file_path`

Example:

```json
{
  "idea": "Promote summer skincare tips for women in their 20s with a short, high-impact ad concept.",
  "caption_seed": "A beauty hook that grabs attention within 3 seconds.",
  "platforms": ["youtube"],
  "dry_run": false,
  "metadata": {
    "video_file_path": "D:\\sns\\sample.mp4"
  }
}
```

## Development Notes

- This repository is set up to be safe for local experimentation first.
- Secrets such as `.env`, `client_secrets.json`, and `token.json` are excluded from Git.
- Generated outputs in `artifacts/` and execution logs in `data/` are excluded from Git.
- Several service modules are structured so real external API calls can replace mock implementations without rewriting the whole workflow.

## Future Improvements

- add automated tests for workflow stages
- add background job execution for long-running generation
- add richer retry and failure handling for external APIs
- add scheduling and approval flows before publishing
