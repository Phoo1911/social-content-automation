from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ArtifactManager:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        path = self.root_dir / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, run_id: str, name: str, payload: dict[str, Any]) -> Path:
        path = self.run_dir(run_id) / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def write_bytes(self, run_id: str, name: str, payload: bytes) -> Path:
        path = self.run_dir(run_id) / name
        path.write_bytes(payload)
        return path
