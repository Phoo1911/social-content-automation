from __future__ import annotations

from datetime import datetime
from typing import Any

from app.config import Settings
from app.models import RunStatus
from app.models import StepResult
from app.models import StepStatus
from app.models import WorkflowRequest
from app.models import WorkflowRun
from app.models import WorkflowStep
from app.services.artifacts import ArtifactManager
from app.services.inputs import InputCollector
from app.services.llm import LLMService
from app.services.logging_targets import GoogleDriveUploader
from app.services.logging_targets import GoogleSheetsLogger
from app.services.notifications import NotificationService
from app.services.publishers import MultiPlatformPublisher
from app.services.video_generation import VideoGenerationService
from app.storage import RunStorage


class WorkflowEngine:
    def __init__(self, settings: Settings) -> None:
        artifacts = ArtifactManager(settings.workflow_artifact_dir)
        self.settings = settings
        self.storage = RunStorage(settings.workflow_storage_dir)
        self.inputs = InputCollector()
        self.llm = LLMService()
        self.sheets = GoogleSheetsLogger()
        self.drive = GoogleDriveUploader()
        self.videos = VideoGenerationService(artifacts)
        self.publisher = MultiPlatformPublisher(settings)
        self.notifications = NotificationService()

    def list_runs(self) -> list[WorkflowRun]:
        return self.storage.load_all()

    def get_run(self, run_id: str) -> WorkflowRun | None:
        return self.storage.get(run_id)

    def _execute_step(self, run: WorkflowRun, step: WorkflowStep, fn):
        step_result = next(item for item in run.steps if item.step == step)
        step_result.status = StepStatus.running
        step_result.started_at = datetime.utcnow()
        run.updated_at = datetime.utcnow()
        self.storage.save(run)

        try:
            data = fn()
            step_result.status = StepStatus.completed
            step_result.data = data
            step_result.finished_at = datetime.utcnow()
            run.updated_at = datetime.utcnow()
            self.storage.save(run)
            return data
        except Exception as exc:
            step_result.status = StepStatus.failed
            step_result.error = str(exc)
            step_result.finished_at = datetime.utcnow()
            run.updated_at = datetime.utcnow()
            self.storage.save(run)
            raise

    def _collect_idea_bound(self, request: WorkflowRequest) -> dict[str, Any]:
        collected = self.inputs.collect(request)
        if not collected["idea"] or not collected["caption_seed"]:
            initial_brief = self.llm.generate_initial_brief(collected["metadata"])
            collected["idea"] = collected["idea"] or initial_brief["idea"]
            collected["caption_seed"] = collected["caption_seed"] or initial_brief["caption_seed"]
            collected["initial_brief"] = initial_brief
            collected["idea_source"] = self.llm.provider_name
        else:
            collected["initial_brief"] = {
                "idea": collected["idea"],
                "caption_seed": collected["caption_seed"],
            }
            collected["idea_source"] = "user_input"
        return collected

    def _generate_idea_candidates(
        self,
        request: WorkflowRequest,
        collected: dict[str, Any],
    ) -> dict[str, Any]:
        raw = self.llm.generate_idea_candidates(
            collected["idea"],
            collected["caption_seed"],
            request.idea_candidate_count,
        )
        scored = self.llm.score_idea_candidates(raw["candidates"], collected["idea"])
        ranked_candidates = scored["ranked_candidates"]

        if request.auto_select_idea or request.selected_idea_index is None:
            selected_candidate = scored["selected_candidate"]
            selection_mode = "auto"
        else:
            selected_candidate = next(
                (
                    candidate
                    for candidate in ranked_candidates
                    if candidate["index"] == request.selected_idea_index
                ),
                scored["selected_candidate"],
            )
            selection_mode = "manual"

        sheet_log = self.sheets.append(
            "idea_candidates",
            {
                "candidate_count": len(ranked_candidates),
                "selected_index": selected_candidate["index"],
                "selection_mode": selection_mode,
            },
        )
        return {
            "candidate_count": len(ranked_candidates),
            "ranked_candidates": ranked_candidates,
            "selected_candidate": selected_candidate,
            "selection_mode": selection_mode,
            "sheet_log": sheet_log,
        }

    def _prepare_visual_direction(self, collected: dict[str, Any]) -> dict[str, Any]:
        selected_candidate = collected.get("selected_candidate")
        analysis = self.llm.analyze_reference_images(
            collected["reference_image_urls"],
            collected["idea"],
        )
        prompt_bundle = self.llm.build_image_prompt(
            collected["idea"],
            analysis,
            collected["caption_seed"],
            selected_candidate,
        )
        drive_log = self.drive.upload_reference_images(collected["reference_image_urls"])
        sheet_log = self.sheets.append(
            "visual_direction",
            {
                "analysis": analysis,
                "prompt": prompt_bundle,
                "drive": drive_log,
                "selected_candidate": selected_candidate,
            },
        )
        return {
            "analysis": analysis,
            "prompt_bundle": prompt_bundle,
            "selected_candidate": selected_candidate,
            "drive_log": drive_log,
            "sheet_log": sheet_log,
        }

    def _generate_script(
        self,
        collected: dict[str, Any],
        visual_bundle: dict[str, Any],
    ) -> dict[str, Any]:
        script = self.llm.generate_video_script(
            collected["idea"],
            visual_bundle["prompt_bundle"]["prompt"],
            collected["caption_seed"],
            collected.get("selected_candidate"),
        )
        sheet_log = self.sheets.append("video_script", script)
        return {
            "script": script,
            "sheet_log": sheet_log,
        }

    def _generate_video(
        self,
        run: WorkflowRun,
        script_bundle: dict[str, Any],
        visual_bundle: dict[str, Any],
    ) -> dict[str, Any]:
        video_result = self.videos.create_video(
            run.run_id,
            script_bundle["script"],
            visual_bundle["prompt_bundle"],
            run.request.dry_run,
            enabled=True,
        )
        rewritten_caption = self.llm.rewrite_caption_for_video(script_bundle["script"])
        sheet_log = self.sheets.append(
            "video_generation",
            {
                "video_result": video_result,
                "rewritten_caption": rewritten_caption,
            },
        )
        return {
            "video_result": video_result,
            "rewritten_caption": rewritten_caption,
            "sheet_log": sheet_log,
        }

    def _generation_stage(self, request: WorkflowRequest) -> str:
        stage = "full"
        if isinstance(request.metadata, dict):
            stage = str(request.metadata.get("generation_stage", "full")).lower()
        if stage not in {"ideation", "script", "video", "full"}:
            return "full"
        return stage

    def _finish_run(
        self,
        run: WorkflowRun,
        *,
        outputs: dict[str, Any],
        publish_results: list[Any] | None = None,
        notification: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        final_outputs = dict(outputs)
        if notification is not None:
            final_outputs["notification"] = notification
        run.outputs = final_outputs
        run.publish_results = publish_results or []
        run.status = RunStatus.completed
        run.updated_at = datetime.utcnow()
        self.storage.save(run)
        return run

    def _auto_post(
        self,
        run: WorkflowRun,
        request: WorkflowRequest,
        script_bundle: dict[str, Any],
        video_bundle: dict[str, Any],
    ) -> dict[str, Any]:
        platforms = request.platforms or self.settings.platform_targets
        script = script_bundle["script"]
        video_result = video_bundle["video_result"]
        video_path = video_result.get("local_video_path")
        if isinstance(request.metadata, dict):
            video_path = request.metadata.get("video_file_path") or video_path

        publish_results = self.publisher.publish(
            run.run_id,
            platforms,
            script["headline"],
            video_bundle["rewritten_caption"],
            video_result["video_url"],
            video_path=video_path,
            dry_run=request.dry_run,
        )
        notification = self.notifications.build_summary(run.run_id, publish_results)
        return {
            "publish_results": publish_results,
            "notification": notification,
        }

    def run(self, request: WorkflowRequest) -> WorkflowRun:
        run = WorkflowRun(
            request=request,
            steps=[StepResult(step=step) for step in WorkflowStep],
        )
        run.status = RunStatus.running
        run.updated_at = datetime.utcnow()
        self.storage.save(run)

        try:
            collected = self._execute_step(
                run,
                WorkflowStep.collect_idea,
                lambda: self._collect_idea_bound(request),
            )
            ideation_bundle = self._execute_step(
                run,
                WorkflowStep.generate_idea_candidates,
                lambda: self._generate_idea_candidates(request, collected),
            )
            collected = {
                **collected,
                "selected_candidate": ideation_bundle["selected_candidate"],
                "ranked_candidates": ideation_bundle["ranked_candidates"],
            }
            stage = self._generation_stage(request)
            if stage == "ideation":
                return self._finish_run(
                    run,
                    outputs={
                        "collected": collected,
                        "ideation": ideation_bundle,
                    },
                )
            visual_bundle = self._execute_step(
                run,
                WorkflowStep.create_image,
                lambda: self._prepare_visual_direction(collected),
            )
            script_bundle = self._execute_step(
                run,
                WorkflowStep.generate_script,
                lambda: self._generate_script(collected, visual_bundle),
            )
            base_outputs = {
                "collected": collected,
                "ideation": ideation_bundle,
                "visual_direction": visual_bundle,
                "script": script_bundle,
            }
            if stage == "script":
                return self._finish_run(run, outputs=base_outputs)

            video_bundle = self._execute_step(
                run,
                WorkflowStep.generate_video,
                lambda: self._generate_video(run, script_bundle, visual_bundle),
            )
            base_outputs["video"] = video_bundle

            if stage == "video":
                return self._finish_run(run, outputs=base_outputs)

            publish_bundle = self._execute_step(
                run,
                WorkflowStep.auto_post,
                lambda: self._auto_post(run, request, script_bundle, video_bundle),
            )

            return self._finish_run(
                run,
                outputs={
                    **base_outputs,
                },
                publish_results=publish_bundle["publish_results"],
                notification=publish_bundle["notification"],
            )
        except Exception as exc:
            run.status = RunStatus.failed
            run.error = str(exc)
            run.updated_at = datetime.utcnow()
            self.storage.save(run)
            raise
