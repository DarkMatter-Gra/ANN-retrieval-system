from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.user import User
from app.schemas.auth import ResetPasswordRequest, UpdateUserRequest
from app.services.user_service import UserService
from app.utils.response import success

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("")
def list_users(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    role: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    operator: User = Depends(require_roles("admin")),
):
    return success(UserService(db).list_users(page, page_size, keyword, role, status))


@router.patch("/{user_id}")
def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    db: Session = Depends(get_db),
    operator: User = Depends(require_roles("admin")),
):
    return success(
        UserService(db).update(user_id, payload.model_dump(exclude_none=True), operator)
    )


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_user),
):
    return success(
        UserService(db).reset_password(user_id, payload.new_password, operator)
    )


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    operator: User = Depends(require_roles("admin")),
):
    return success(UserService(db).soft_delete(user_id, operator))
