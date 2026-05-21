from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.dataset import UploadCompleteRequest, UploadInitRequest
from app.services.dataset_service import DatasetService
from app.utils.response import success

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.post("/upload/init")
def upload_init(
    payload: UploadInitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    upload_id, chunk_size = DatasetService(db).init_upload(
        current_user.id, payload.filename, payload.size, payload.format
    )
    return success({"upload_id": upload_id, "chunk_size": chunk_size})


@router.post("/upload/chunk")
async def upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    chunk_data: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    next_chunk = await DatasetService(db).save_chunk(
        user_id=current_user.id,
        upload_id=upload_id,
        chunk_index=chunk_index,
        chunk_file=chunk_data,
    )
    return success({"received": True, "next_chunk": next_chunk})


@router.post("/upload/complete")
def upload_complete(
    payload: UploadCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return success(DatasetService(db).complete_upload(current_user.id, payload.upload_id))


@router.get("")
def list_datasets(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return success(DatasetService(db).list_datasets(current_user, page, page_size, keyword))


@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return success(DatasetService(db).get_detail(dataset_id, current_user))


@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return success(DatasetService(db).delete_dataset(dataset_id, current_user))


@router.get("/{dataset_id}/logs")
def dataset_logs(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return success(DatasetService(db).get_logs(dataset_id, current_user))
