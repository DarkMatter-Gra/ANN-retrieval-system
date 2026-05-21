from typing import Any


def success(data: Any = None, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data if data is not None else {}}


def fail(code: int, message: str, data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data if data is not None else {}}
