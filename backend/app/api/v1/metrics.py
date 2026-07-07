from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.metrics_service import MetricsService
from app.utils.response import success

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/search")
def metrics_search(
    index_id: int | None = Query(None, description="过滤指定索引"),
    time_range: str = Query("1h", pattern="^(1h|6h|24h|7d)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "dev", "auditor")),
):
    return success(
        MetricsService(db).search_metrics(
            index_id=index_id, time_range=time_range, current_user=current_user
        )
    )
