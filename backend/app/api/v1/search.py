from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.search import BatchSearchRequest, SearchRequest
from app.services.search_service import SearchService
from app.utils.response import success

router = APIRouter(tags=["Search"])


@router.post("/search")
def search(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return success(SearchService(db).search(current_user, payload.model_dump()))


@router.post("/batch-search")
def batch_search(
    payload: BatchSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return success(
        SearchService(db).create_batch_task(current_user, payload.model_dump())
    )
