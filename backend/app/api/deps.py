from fastapi import Depends, Header
import jwt
from sqlalchemy.orm import Session

from app.core.exceptions import (
    PermissionDeniedError,
    TokenExpiredError,
    TokenInvalidError,
    UnauthorizedError,
)
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.user import User


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("missing or invalid auth header")

    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except Exception as exc:
        raise TokenInvalidError(f"invalid token: {exc}")

    user_id = int(payload.get("sub", 0))
    user = db.query(User).filter(User.id == user_id, User.status == "active").first()
    if not user:
        raise TokenInvalidError("user not found")
    return user


def require_roles(*roles: str):
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise PermissionDeniedError()
        return current_user

    return checker
