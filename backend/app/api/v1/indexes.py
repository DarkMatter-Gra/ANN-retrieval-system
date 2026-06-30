from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.schemas.index import (
    CreateIndexRequest,
    PublishIndexRequest,
    RollbackIndexRequest,
)
from app.services.index_service import IndexService
from app.utils.response import success

router = APIRouter(prefix="/indexes", tags=["Indexes"])


@router.post("")
def create_index(
    payload: CreateIndexRequest,
    db: Session = Depends(get_db),
    operator: User = Depends(require_roles("admin", "dev")),
):
    return success(
        IndexService(db).create_index_task(
            owner=operator,
            dataset_ids=payload.dataset_ids or [payload.dataset_id],
            index_name=payload.index_name,
            index_type=payload.index_type,
            metric=payload.metric,
            params_json=payload.params_json,
        )
    )


@router.get("")
def list_indexes(
    dataset_id: int | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(pending|running|done|failed)$"),
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    operator: User = Depends(require_roles("admin", "dev")),
):
    return success(
        IndexService(db).list_indexes(operator, dataset_id, status, page, page_size)
    )


@router.get("/{index_id}")
def get_index(
    index_id: int,
    db: Session = Depends(get_db),
    operator: User = Depends(require_roles("admin", "dev")),
):
    return success(IndexService(db).get_detail(index_id, operator))


@router.post("/{index_id}/load")
def load_index(
    index_id: int,
    db: Session = Depends(get_db),
    operator: User = Depends(require_roles("admin", "dev")),
):
    return success(IndexService(db).load_into_memory(index_id, operator))


@router.post("/{index_id}/publish")
def publish_index(
    index_id: int,
    payload: PublishIndexRequest,
    db: Session = Depends(get_db),
    operator: User = Depends(require_roles("admin")),
):
    return success(IndexService(db).publish(index_id, payload.audit_comment, operator))


@router.post("/{index_id}/rollback")
def rollback_index(
    index_id: int,
    payload: RollbackIndexRequest,
    db: Session = Depends(get_db),
    operator: User = Depends(require_roles("admin")),
):
    return success(
        IndexService(db).rollback(index_id, payload.target_version, operator)
    )
