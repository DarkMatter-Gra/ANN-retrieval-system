from datetime import datetime
from typing import Any

import bcrypt
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    try:
        return password_hasher.hash(password)
    except Exception:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        if password_hash.startswith("$argon2"):
            password_hasher.verify(password_hash, password)
            return True
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (VerifyMismatchError, ValueError):
        return False


def create_access_token(data: dict[str, Any], expire_at: datetime) -> str:
    payload = data.copy()
    payload["exp"] = expire_at
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
