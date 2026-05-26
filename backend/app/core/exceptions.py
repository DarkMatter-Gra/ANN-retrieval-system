from fastapi import HTTPException, status


class BusinessError(HTTPException):
    def __init__(
        self, code: int, message: str, http_status: int = status.HTTP_400_BAD_REQUEST
    ):
        super().__init__(
            status_code=http_status, detail={"code": code, "message": message}
        )
        self.code = code
        self.message = message


class NotFoundError(BusinessError):
    """通用未找到，默认按用户不存在 40401。优先使用具体子类。"""

    def __init__(self, message: str = "resource not found", code: int = 40401):
        super().__init__(code, message, http_status=status.HTTP_404_NOT_FOUND)


class UserNotFoundError(NotFoundError):
    def __init__(self, message: str = "user not found"):
        super().__init__(message, code=40401)


class DatasetNotFoundError(NotFoundError):
    def __init__(self, message: str = "dataset not found"):
        super().__init__(message, code=40402)


class IndexNotFoundError(NotFoundError):
    def __init__(self, message: str = "index not found"):
        super().__init__(message, code=40403)


class TaskNotFoundError(NotFoundError):
    def __init__(self, message: str = "task not found"):
        super().__init__(message, code=40404)


class PermissionDeniedError(BusinessError):
    def __init__(self, message: str = "forbidden", code: int = 40301):
        super().__init__(code, message, http_status=status.HTTP_403_FORBIDDEN)


class ResourceForbiddenError(PermissionDeniedError):
    def __init__(self, message: str = "resource forbidden"):
        super().__init__(message, code=40302)


class QuotaExceededError(PermissionDeniedError):
    def __init__(self, message: str = "quota exceeded"):
        super().__init__(message, code=40303)


class UnauthorizedError(BusinessError):
    def __init__(self, message: str = "unauthorized", code: int = 40101):
        super().__init__(code, message, http_status=status.HTTP_401_UNAUTHORIZED)


class TokenExpiredError(UnauthorizedError):
    def __init__(self, message: str = "token expired"):
        super().__init__(message, code=40102)


class TokenInvalidError(UnauthorizedError):
    def __init__(self, message: str = "token invalid"):
        super().__init__(message, code=40103)


class ConflictError(BusinessError):
    def __init__(self, message: str = "state conflict", code: int = 40901):
        super().__init__(code, message, http_status=status.HTTP_409_CONFLICT)


class ValidationFailed(BusinessError):
    def __init__(self, message: str = "validation failed", code: int = 40002):
        super().__init__(code, message, http_status=status.HTTP_400_BAD_REQUEST)


class ParamMissingError(ValidationFailed):
    def __init__(self, message: str = "param missing"):
        super().__init__(message, code=40001)


class ParamOutOfRangeError(ValidationFailed):
    def __init__(self, message: str = "param out of range"):
        super().__init__(message, code=40003)
