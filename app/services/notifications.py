from __future__ import annotations

from app.models import PublishResult


class NotificationService:
    def build_summary(self, run_id: str, results: list[PublishResult]) -> dict[str, object]:
        success_count = sum(1 for item in results if item.success)
        return {
            "run_id": run_id,
            "success_count": success_count,
            "total_count": len(results),
            "message": f"Workflow {run_id} completed. Published to {success_count}/{len(results)} platforms.",
        }
