from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import ResourceForbiddenError, TaskNotFoundError
from app.models.search_task import SearchTask
from app.models.user import User


class TaskService:
    def __init__(self, db: Session):
        self.db = db

    def update_progress(
        self,
        task_id: str,
        progress: int | None = None,
        status: str | None = None,
        result_path: str | None = None,
        error_message: str | None = None,
    ) -> None:
        task = self.db.query(SearchTask).filter(SearchTask.task_id == task_id).first()
        if not task:
            return
        if progress is not None:
            task.progress = max(0, min(progress, 100))
        if status:
            task.status = status
        if result_path is not None:
            task.result_path = result_path
        if error_message is not None:
            task.error_message = error_message
        self.db.commit()

    def get_task(self, task_id: str, current_user: User) -> SearchTask:
        task = self.db.query(SearchTask).filter(SearchTask.task_id == task_id).first()
        if not task:
            raise TaskNotFoundError()
        if current_user.role != "admin" and task.owner_user_id != current_user.id:
            raise ResourceForbiddenError()
        return task

    @staticmethod
    def serialize(task: SearchTask) -> dict:
        data = {
            "task_id": task.task_id,
            "type": task.task_type,
            "progress": task.progress,
            "status": task.status,
            "result_url": task.result_path,
            "error_message": task.error_message,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
        }
        if task.result_path:
            path = Path(task.result_path)
            if task.task_type == "diagnostic_report":
                data["json_download_url"] = f"/api/v1/files/reports/{path.name}"
                data["download_url"] = f"/api/v1/files/reports/{path.with_suffix('.pdf').name}"
                data["result_url"] = data["json_download_url"]
            elif task.task_type == "batch_search":
                data["result_url"] = f"/api/v1/files/exports/{path.name}"
        return data
