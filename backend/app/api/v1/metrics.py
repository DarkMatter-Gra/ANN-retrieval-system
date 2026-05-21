from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.services.metrics_service import MetricsService
from app.utils.response import success

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/search")
def metrics_search(
    index_id: int | None = Query(None, description="过滤指定索引"),
    time_range: str = Query("1h", pattern="^(1h|6h|24h|7d)$"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return success(MetricsService(db).search_metrics(index_id=index_id, time_range=time_range))
