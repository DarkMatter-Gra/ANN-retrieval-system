import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.exceptions import (
    DatasetNotFoundError,
    IndexNotFoundError,
    ParamMissingError,
    ResourceForbiddenError,
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
    current_user: User = Depends(require_roles("admin", "dev", "user", "auditor")),
):
    """Create an asynchronous diagnostic report task."""
    from app.tasks.report_tasks import generate_report_task

    request_payload = payload.model_dump()
    dataset_id = request_payload.get("dataset_id")
    index_id = request_payload.get("index_id")
    query_id = request_payload.get("query_id")
    report_index_obj: ANNIndex | None = None

    if not dataset_id and not index_id and not query_id:
        raise ParamMissingError("dataset_id or index_id or query_id is required")

    if query_id and not dataset_id and not index_id:
        query_task = db.query(SearchTask).filter(SearchTask.task_id == query_id).first()
        if (
            query_task
            and current_user.role not in {"admin", "auditor"}
            and query_task.owner_user_id != current_user.id
        ):
            raise ResourceForbiddenError()
        snapshot = SearchService.get_query_snapshot(query_id)
        if not snapshot and query_task:
            payload_data = query_task.request_payload or {}
            snapshot = {
                "dataset_id": query_task.dataset_id,
                "index_id": query_task.index_id,
                "query_cell_id": payload_data.get("cell_id"),
                "results": payload_data.get("results", []),
                "highlight_points": payload_data.get("highlight_points")
                or {"query": None, "neighbors": []},
            }
        if not snapshot:
            raise TaskNotFoundError("query result not found")
        request_payload["query_snapshot"] = snapshot
        dataset_id = snapshot.get("dataset_id")
        index_id = snapshot.get("index_id")
        request_payload["dataset_id"] = dataset_id
        request_payload["index_id"] = index_id

    if index_id and not dataset_id:
        report_index_obj = db.query(ANNIndex).filter(ANNIndex.id == int(index_id)).first()
        if not report_index_obj:
            raise IndexNotFoundError()
        dataset_id = report_index_obj.dataset_id
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

    if index_id:
        report_index_obj = report_index_obj or db.query(ANNIndex).filter(ANNIndex.id == int(index_id)).first()
        if not report_index_obj:
            raise IndexNotFoundError()
        if (
            current_user.role not in {"admin", "auditor"}
            and report_index_obj.owner_user_id != current_user.id
            and report_index_obj.publish_status != "published"
        ):
            raise ResourceForbiddenError()

    if (
        current_user.role not in {"admin", "auditor"}
        and dataset.owner_user_id != current_user.id
        and not (report_index_obj and report_index_obj.publish_status == "published")
    ):
        raise ResourceForbiddenError()

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
