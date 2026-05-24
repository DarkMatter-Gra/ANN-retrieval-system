from sqlalchemy.orm import Session

from app.core.exceptions import ResourceForbiddenError, UserNotFoundError
from app.core.security import hash_password
from app.models.user import User
from app.utils.audit import write_audit


class UserService:
    # 文档字段名为 quota，DB 字段为 quota_limit；做一次映射
    FIELD_MAP = {"role": "role", "quota": "quota_limit", "status": "status"}

    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise UserNotFoundError()
        return user

    def update(self, user_id: int, payload: dict, operator: User) -> dict:
        user = self.get(user_id)
        updated_fields = []
        for key, value in payload.items():
            if value is None:
                continue
            attr = self.FIELD_MAP.get(key)
            if attr:
                setattr(user, attr, value)
                updated_fields.append(key)
        self.db.commit()
        write_audit(operator.id, "update_user", "user", str(user_id), {"fields": updated_fields})
        return {"user_id": user.id, "updated_fields": updated_fields}

    def reset_password(self, user_id: int, new_password: str, operator: User) -> dict:
        if operator.role != "admin" and operator.id != user_id:
            raise ResourceForbiddenError()
        user = self.get(user_id)
        user.password_hash = hash_password(new_password)
        self.db.commit()
        write_audit(operator.id, "reset_password", "user", str(user_id))
        return {"user_id": user.id, "result": "success"}

    def soft_delete(self, user_id: int, operator: User) -> dict:
        user = self.get(user_id)
        user.status = "deleted"
        self.db.commit()
        write_audit(operator.id, "delete_user", "user", str(user_id))
        return {"user_id": user.id, "deleted": True}

    def list_users(
        self,
        page: int,
        page_size: int,
        keyword: str | None,
        role: str | None,
        status: str | None,
    ) -> dict:
        query = self.db.query(User)
        if keyword:
            query = query.filter(
                User.username.contains(keyword) | User.email.contains(keyword)
            )
        if role:
            query = query.filter(User.role == role)
        if status:
            query = query.filter(User.status == status)
        else:
            query = query.filter(User.status != "deleted")
        total = query.count()
        users = (
            query.order_by(User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "list": [
                {
                    "user_id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "role": u.role,
                    "status": u.status,
                    "quota_limit": u.quota_limit,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
