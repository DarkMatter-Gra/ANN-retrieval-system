from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictError, PermissionDeniedError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register(self, username: str, email: str, password: str, role: str = "user") -> User:
        if self.db.query(User).filter(User.username == username).first():
            raise ConflictError("username already exists")
        if self.db.query(User).filter(User.email == email).first():
            raise ConflictError("email already exists")

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=role,
            quota_limit=5,
            status="active",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def login(self, username: str, password: str) -> dict:
        user = self.db.query(User).filter(User.username == username).first()
        if not user or user.status != "active":
            raise UnauthorizedError("invalid credentials")

        if user.lock_until:
            try:
                lock_until = datetime.fromisoformat(user.lock_until)
            except ValueError:
                lock_until = None
            if lock_until and lock_until > datetime.now(timezone.utc):
                raise PermissionDeniedError("account locked")

        if not verify_password(password, user.password_hash):
            user.failed_login_count += 1
            if user.failed_login_count >= 3:
                user.lock_until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            self.db.commit()
            raise UnauthorizedError("invalid credentials")

        user.failed_login_count = 0
        user.lock_until = None
        self.db.commit()

        expire_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
        token = create_access_token({"sub": str(user.id), "role": user.role}, expire_at)
        return {
            "access_token": token,
            "expire_at": expire_at.isoformat(),
            "role": user.role,
            "dashboard_route": self.dashboard_route(user.role),
        }

    @staticmethod
    def dashboard_route(role: str) -> str:
        mapping = {
            "admin": "/dashboard/admin",
            "dev": "/dashboard/dev",
            "user": "/dashboard/user",
            "readonly": "/dashboard/readonly",
            "service": "/dashboard/service",
            "auditor": "/dashboard/auditor",
        }
        return mapping.get(role, "/dashboard/user")

    @staticmethod
    def build_menus(role: str) -> list[str]:
        if role == "admin":
            return ["dataset", "search", "index", "visualization", "metrics", "user", "audit"]
        if role == "dev":
            return ["dataset", "search", "index", "visualization", "metrics"]
        if role == "user":
            return ["dataset", "search", "visualization"]
        if role == "readonly":
            return ["dataset", "search", "visualization"]
        if role == "service":
            return ["search"]
        if role == "auditor":
            return ["dataset", "search", "visualization", "metrics", "audit"]
        return ["dataset", "search"]
