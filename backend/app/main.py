from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import BusinessError
from app.utils.response import fail

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"persistAuthorization": True},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BusinessError)
async def business_exception_handler(request: Request, exc: BusinessError):
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(exc.code, exc.message),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content=fail(40001, "validation failed", {"errors": exc.errors()}),
    )


@app.exception_handler(Exception)
async def fallback_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=fail(50001, str(exc) or "internal server error"),
    )


@app.get("/health", tags=["Health"])
def health():
    return {"code": 0, "message": "ok", "data": {"status": "healthy"}}


app.include_router(api_router, prefix=settings.api_v1_prefix)

# 暴露任务/报告导出文件目录，供前端 download_url 直接打开
# 例如：GET /api/v1/files/exports/{task_id}.json
app.mount(
    f"{settings.api_v1_prefix}/files/exports",
    StaticFiles(directory=str(settings.export_path)),
    name="exports",
)
