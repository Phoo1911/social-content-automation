from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class StepStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class WorkflowStep(str, Enum):
    collect_idea = "collect_idea"
    generate_idea_candidates = "generate_idea_candidates"
    create_image = "create_image"
    generate_script = "generate_script"
    generate_audio = "generate_audio"
    generate_video = "generate_video"
    auto_post = "auto_post"


class WorkflowRequest(BaseModel):
    idea: str = Field(default="")
    caption_seed: str | None = None
    reference_image_urls: list[str] = Field(default_factory=list)
    reference_video_url: str | None = None
    platforms: list[str] = Field(default_factory=list)
    idea_candidate_count: int = Field(default=5, ge=1, le=10)
    selected_idea_index: int | None = Field(default=None, ge=0, le=9)
    auto_select_idea: bool = True
    dry_run: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class StepResult(BaseModel):
    step: WorkflowStep
    status: StepStatus = StepStatus.pending
    started_at: datetime | None = None
    finished_at: datetime | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class PublishResult(BaseModel):
    platform: str
    success: bool
    external_id: str | None = None
    permalink: str | None = None
    error: str | None = None


class WorkflowRun(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid4().hex)
    status: RunStatus = RunStatus.pending
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    request: WorkflowRequest
    steps: list[StepResult] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)
    publish_results: list[PublishResult] = Field(default_factory=list)
    error: str | None = None


class WorkflowRunResponse(BaseModel):
    run: WorkflowRun


class WorkflowRunListResponse(BaseModel):
    runs: list[WorkflowRun]
