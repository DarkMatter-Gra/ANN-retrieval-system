from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.exceptions import ParamOutOfRangeError
from app.models.user import User
from app.services.visualization_service import VisualizationService
from app.utils.response import success

router = APIRouter(prefix="/visualizations", tags=["Visualizations"])


@router.get("/{dataset_id}/embedding")
def embedding(
    dataset_id: int,
    method: str = Query("umap", pattern="^(umap|tsne)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(2000, ge=1, le=20000),
    color_by: str | None = None,
    bbox: str | None = Query(None, description="x_min,y_min,x_max,y_max"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bbox_tuple = None
    if bbox:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise ParamOutOfRangeError("bbox must be x_min,y_min,x_max,y_max")
        try:
            bbox_tuple = tuple(float(p) for p in parts)  # type: ignore[assignment]
        except ValueError as exc:
            raise ParamOutOfRangeError("bbox must be 4 floats") from exc

    return success(
        VisualizationService(db).get_embedding(
            dataset_id, method, page, page_size, color_by, current_user, bbox_tuple
        )
    )


@router.get("/{query_id}/highlights")
@router.get("/highlights/{query_id}")
def highlights(
    query_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return success(VisualizationService(db).get_highlights(query_id, current_user))
