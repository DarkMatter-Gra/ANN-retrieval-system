from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.exceptions import TaskNotFoundError
from app.models.user import User
from app.services.task_service import TaskService
from app.utils.response import success

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}")
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = TaskService(db).get_task(task_id, current_user)
    return success(TaskService.serialize(task))


@router.get("/{task_id}/export")
def export_task(
    task_id: str,
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = TaskService(db).get_task(task_id, current_user)
    if not task.result_path:
        raise TaskNotFoundError("export not ready")
    file_path = Path(task.result_path)
    if not file_path.exists():
        raise TaskNotFoundError("export file missing")
    download_url = f"/api/v1/files/exports/{task_id}.{format}"
    return success({"download_url": download_url, "format": format})
