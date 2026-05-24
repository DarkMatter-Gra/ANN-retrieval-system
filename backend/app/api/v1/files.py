from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.exceptions import ResourceForbiddenError, TaskNotFoundError, ValidationFailed
from app.models.search_task import SearchTask
from app.models.user import User

router = APIRouter(prefix="/files", tags=["Files"])


@router.get("/exports/{filename}")
def download_export(
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if "/" in filename or "\\" in filename:
        raise ValidationFailed("invalid filename")

    path = (settings.export_path / filename).resolve()
    export_root = settings.export_path.resolve()
    if export_root not in path.parents and path != export_root:
        raise ValidationFailed("invalid export path")
    if not path.exists() or not path.is_file():
        raise TaskNotFoundError("export file missing")

    task_id = path.stem
    if path.suffix == ".jsonl":
        task_id = path.with_suffix("").name
    task = db.query(SearchTask).filter(SearchTask.task_id == task_id).first()
    if not task:
        raise TaskNotFoundError()
    if current_user.role != "admin" and task.owner_user_id != current_user.id:
        raise ResourceForbiddenError()

    media_type = "text/csv" if path.suffix == ".csv" else "application/x-ndjson"
    return FileResponse(path, media_type=media_type, filename=path.name)
