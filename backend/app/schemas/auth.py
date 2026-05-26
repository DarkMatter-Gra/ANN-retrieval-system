from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=64)
    email: EmailStr
    role: str = Field(
        default="user", pattern="^(admin|dev|user|readonly|service|auditor)$"
    )


class LoginRequest(BaseModel):
    username: str
    password: str


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=64)


class UpdateUserRequest(BaseModel):
    role: str | None = Field(
        default=None, pattern="^(admin|dev|user|readonly|service|auditor)$"
    )
    quota: int | None = None
    status: str | None = Field(default=None, pattern="^(active|disabled|locked)$")
