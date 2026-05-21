from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthService
from app.utils.response import success

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = AuthService(db).register(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        role=payload.role,
    )
    return success({"user_id": user.id, "username": user.username, "role": user.role})


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return success(AuthService(db).login(payload.username, payload.password))


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return success(
        {
            "user_id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
            "quota": {
                "used": 0,
                "limit": current_user.quota_limit,
            },
            "menus": AuthService.build_menus(current_user.role),
            "dashboard_route": AuthService.dashboard_route(current_user.role),
        }
    )
