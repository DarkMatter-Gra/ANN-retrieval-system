import json

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


@router.get("/reports/{filename}")
def download_report(
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if "/" in filename or "\\" in filename:
        raise ValidationFailed("invalid filename")

    path = (settings.report_path / filename).resolve()
    report_root = settings.report_path.resolve()
    if report_root not in path.parents and path != report_root:
        raise ValidationFailed("invalid report path")
    if path.suffix not in {".json", ".pdf"}:
        raise ValidationFailed("unsupported report file")
    if not path.exists() or not path.is_file():
        raise TaskNotFoundError("report file missing")

    json_path = path if path.suffix == ".json" else path.with_suffix(".json")
    if not json_path.exists() or not json_path.is_file():
        raise TaskNotFoundError("report metadata missing")

    report = json.loads(json_path.read_text(encoding="utf-8"))
    owner_user_id = report.get("owner_user_id")
    if owner_user_id is not None:
        if current_user.role != "admin" and int(owner_user_id) != current_user.id:
            raise ResourceForbiddenError()
        media_type = "application/pdf" if path.suffix == ".pdf" else "application/json"
        return FileResponse(path, media_type=media_type, filename=path.name)

    query_id = (report.get("query") or {}).get("query_id")
    task = db.query(SearchTask).filter(SearchTask.task_id == query_id).first()
    if not task:
        raise TaskNotFoundError()
    if current_user.role != "admin" and task.owner_user_id != current_user.id:
        raise ResourceForbiddenError()

    media_type = "application/pdf" if path.suffix == ".pdf" else "application/json"
    return FileResponse(path, media_type=media_type, filename=path.name)
