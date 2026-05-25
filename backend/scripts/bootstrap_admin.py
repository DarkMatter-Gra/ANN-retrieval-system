"""一键初始化管理员账号。

使用方式（在 backend/ 目录下、激活 .venv 后）：

    python scripts/bootstrap_admin.py                        # 默认 admin / Admin@123
    python scripts/bootstrap_admin.py -u boss -p 'P@ss1234'  # 自定义
    python scripts/bootstrap_admin.py --reset                # 已存在则重置密码

如果数据库 / 表还没创建，会自动跑一次 Base.metadata.create_all。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 让脚本能在 backend/ 目录下直接 `python scripts/bootstrap_admin.py` 运行
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.enums import UserRole, UserStatus  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models import User  # noqa: E402  # 通过 __init__ 触发所有模型注册到 Base.metadata


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)


def upsert_admin(username: str, password: str, email: str, reset: bool) -> str:
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.username == username).first()
        if user is None:
            user = User(
                username=username,
                email=email,
                password_hash=hash_password(password),
                role=UserRole.admin.value,
                quota_limit=999,
                status=UserStatus.active.value,
            )
            session.add(user)
            session.commit()
            return f"created admin user: {username}"

        if not reset:
            return f"user '{username}' already exists; pass --reset to overwrite password/role"

        user.password_hash = hash_password(password)
        user.role = UserRole.admin.value
        user.status = UserStatus.active.value
        user.failed_login_count = 0
        user.lock_until = None
        session.commit()
        return f"reset admin user: {username}"
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap an admin user.")
    parser.add_argument("-u", "--username", default="admin")
    parser.add_argument("-p", "--password", default="Admin@123")
    parser.add_argument("-e", "--email", default="admin@example.com")
    parser.add_argument("--reset", action="store_true", help="reset password if user exists")
    args = parser.parse_args()

    ensure_schema()
    msg = upsert_admin(args.username, args.password, args.email, args.reset)
    print(msg)
    print(f"  username: {args.username}")
    print(f"  password: {args.password}")
    print("login at: http://localhost:5173/login")


if __name__ == "__main__":
    main()
