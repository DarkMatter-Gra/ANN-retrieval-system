from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.task import ReportRequest
from app.utils.response import success

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("/diagnostic")
def create_diagnostic_report(
    payload: ReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成诊断报告（异步）。"""
    from app.tasks.report_tasks import generate_report_task

    task_result = generate_report_task.delay(
        payload.model_dump(),
        current_user.id,
    )
    data = {
        "task_id": task_result.id,
        "status": "done" if task_result.ready() else "pending",
    }
    if task_result.ready():
        if isinstance(task_result.result, dict):
            data.update(task_result.result)
            data["result_path"] = task_result.result.get("json_path")
        else:
            data["result_path"] = task_result.result
    return success(data)
