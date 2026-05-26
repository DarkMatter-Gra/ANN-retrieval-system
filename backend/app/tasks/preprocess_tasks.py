from app.db.session import SessionLocal
from app.models.dataset import ExpressionMetadata
from app.models.search_task import SearchTask
from app.services.preprocess_service import run_preprocess
from app.tasks.celery_app import celery_app
from app.utils.time import utcnow_iso


@celery_app.task(bind=True, name="preprocess_dataset_task")
def preprocess_dataset_task(self, task_id: str, dataset_id: int, user_id: int):
    db = SessionLocal()
    try:
        run_preprocess(db, task_id, dataset_id)
    except Exception as exc:  # noqa: BLE001
        task = db.query(SearchTask).filter(SearchTask.task_id == task_id).first()
        dataset = (
            db.query(ExpressionMetadata)
            .filter(ExpressionMetadata.id == dataset_id)
            .first()
        )
        if task:
            task.status = "failed"
            task.error_message = str(exc)
            task.finished_at = utcnow_iso()
        if dataset:
            dataset.preprocess_status = "failed"
            dataset.qc_status = "failed"
        db.commit()
        raise
    finally:
        db.close()
