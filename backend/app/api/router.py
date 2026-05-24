from fastapi import APIRouter

from app.api.v1 import (
    auth,
    datasets,
    files,
    indexes,
    metrics,
    reports,
    search,
    tasks,
    users,
    visualizations,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(datasets.router)
api_router.include_router(files.router)
api_router.include_router(indexes.router)
api_router.include_router(search.router)
api_router.include_router(tasks.router)
api_router.include_router(visualizations.router)
api_router.include_router(metrics.router)
api_router.include_router(reports.router)
