import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.exceptions import (
    DatasetNotFoundError,
    IndexNotFoundError,
    ParamMissingError,
    TaskNotFoundError,
)
from app.models.ann_index import ANNIndex
from app.models.dataset import ExpressionMetadata
from app.models.search_task import SearchTask
from app.models.user import User
from app.schemas.task import ReportRequest
from app.services.search_service import SearchService
from app.utils.response import success

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("/diagnostic")
def create_diagnostic_report(
    payload: ReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an asynchronous diagnostic report task."""
    from app.tasks.report_tasks import generate_report_task

    request_payload = payload.model_dump()
    dataset_id = request_payload.get("dataset_id")
    index_id = request_payload.get("index_id")
    query_id = request_payload.get("query_id")

    if not dataset_id and not index_id and not query_id:
        raise ParamMissingError("dataset_id or index_id or query_id is required")

    if query_id and not dataset_id and not index_id:
        snapshot = SearchService.get_query_snapshot(query_id)
        if not snapshot:
            raise TaskNotFoundError("query result not found")
        request_payload["query_snapshot"] = snapshot
        dataset_id = snapshot.get("dataset_id")
        index_id = snapshot.get("index_id")
        request_payload["dataset_id"] = dataset_id
        request_payload["index_id"] = index_id

    if index_id and not dataset_id:
        index_obj = db.query(ANNIndex).filter(ANNIndex.id == int(index_id)).first()
        if not index_obj:
            raise IndexNotFoundError()
        dataset_id = index_obj.dataset_id
        request_payload["dataset_id"] = dataset_id

    if not dataset_id:
        raise ParamMissingError("dataset_id is required")

    dataset = (
        db.query(ExpressionMetadata)
        .filter(
            ExpressionMetadata.id == int(dataset_id),
            ExpressionMetadata.deleted_flag.is_(False),
        )
        .first()
    )
    if not dataset:
        raise DatasetNotFoundError()

    task = SearchTask(
        task_id=uuid.uuid4().hex,
        owner_user_id=current_user.id,
        task_type="diagnostic_report",
        dataset_id=int(dataset_id),
        index_id=int(index_id) if index_id else None,
        status="pending",
        progress=0,
        request_payload=request_payload,
    )
    db.add(task)
    db.commit()

    task_result = generate_report_task.delay(task.task_id)
    db.refresh(task)

    data = {"task_id": task.task_id, "status": task.status}
    if task.result_path:
        json_path = Path(task.result_path)
        data["json_download_url"] = f"/api/v1/files/reports/{json_path.name}"
        pdf_path = json_path.with_suffix(".pdf")
        if pdf_path.exists():
            data["download_url"] = f"/api/v1/files/reports/{pdf_path.name}"
        if getattr(task_result, "result", None) and isinstance(task_result.result, dict):
            data.update(task_result.result)
    return success(data)
