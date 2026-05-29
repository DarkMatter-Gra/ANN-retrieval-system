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

conf_kwargs = dict(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
)

# Support a local filesystem queue so the project can run without Redis.
if settings.redis_url.startswith("filesystem://"):
    _broker_dir = str(settings.data_path / "celery-broker" / "in")
    conf_kwargs["broker_transport_options"] = {
        "data_folder_in": _broker_dir,
        "data_folder_out": _broker_dir,
        "processed_folder": str(settings.data_path / "celery-broker" / "processed"),
    }

celery_app.conf.update(**conf_kwargs)
