from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ann-backend",
    broker=settings.redis_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.preprocess_tasks",
        "app.tasks.index_tasks",
        "app.tasks.batch_search_tasks",
        "app.tasks.report_tasks",
    ],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
)
