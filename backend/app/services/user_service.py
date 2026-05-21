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
