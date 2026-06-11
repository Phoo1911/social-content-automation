from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.models import WorkflowRequest
from app.models import WorkflowRunListResponse
from app.models import WorkflowRunResponse
from app.workflow import WorkflowEngine


app = FastAPI(title="SNS Workflow API", version="0.1.0")
engine = WorkflowEngine(settings)
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@app.post("/workflows/run", response_model=WorkflowRunResponse)
def run_workflow(request: WorkflowRequest) -> WorkflowRunResponse:
    run = engine.run(request)
    return WorkflowRunResponse(run=run)


@app.get("/runs", response_model=WorkflowRunListResponse)
def list_runs() -> WorkflowRunListResponse:
    return WorkflowRunListResponse(runs=engine.list_runs())


@app.get("/runs/{run_id}", response_model=WorkflowRunResponse)
def get_run(run_id: str) -> WorkflowRunResponse:
    run = engine.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return WorkflowRunResponse(run=run)
