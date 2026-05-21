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

    task_id = generate_report_task.delay(
        payload.model_dump(),
        current_user.id,
    ).id
    return success({"task_id": task_id, "status": "pending"})
