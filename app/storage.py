from __future__ import annotations

import json
from pathlib import Path

from app.models import WorkflowRun


class RunStorage:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.runs_file = self.base_dir / "runs.jsonl"

    def save(self, run: WorkflowRun) -> None:
        runs = {item.run_id: item for item in self.load_all()}
        runs[run.run_id] = run
        with self.runs_file.open("w", encoding="utf-8") as handle:
            for item in runs.values():
                handle.write(item.model_dump_json())
                handle.write("\n")

    def load_all(self) -> list[WorkflowRun]:
        if not self.runs_file.exists():
            return []
        items: list[WorkflowRun] = []
        with self.runs_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                items.append(WorkflowRun.model_validate(json.loads(line)))
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def get(self, run_id: str) -> WorkflowRun | None:
        for run in self.load_all():
            if run.run_id == run_id:
                return run
        return None
