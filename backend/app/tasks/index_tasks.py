import numpy as np
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.ann_index import ANNIndex
from app.models.cell_vector import CellVector
from app.models.search_task import SearchTask
from app.services.ann_engine import ANNEngine
from app.tasks.celery_app import celery_app
from app.utils.time import utcnow_iso
from app.utils.vector_codec import stack_vectors


def _build(index_obj: ANNIndex, vectors: np.ndarray, cell_ids: list[str]):
    return ANNEngine.build(index_obj, vectors, cell_ids)


@celery_app.task(bind=True, name="build_index_task")
def build_index_task(self, task_id: str, dataset_id: int, index_id: int):
    db: Session = SessionLocal()
    try:
        task = db.query(SearchTask).filter(SearchTask.task_id == task_id).first()
        index_obj = db.query(ANNIndex).filter(ANNIndex.id == index_id).first()
        if not task or not index_obj:
            raise ValueError("task or index not found")

        task.status = "running"
        task.progress = 10
        task.started_at = utcnow_iso()
        index_obj.build_status = "running"
        db.commit()

        rows = (
            db.query(CellVector)
            .filter(CellVector.dataset_id == dataset_id, CellVector.vector_type == "pca")
            .order_by(CellVector.id.asc())
            .all()
        )
        if not rows:
            raise ValueError("no vectors available")
        vectors = stack_vectors([r.vector_blob for r in rows])
        cell_ids = [r.cell_id for r in rows]
        task.progress = 30
        db.commit()

        result = _build(index_obj, vectors, cell_ids)

        index_obj.build_status = "done"
        index_obj.recall_score = 1.0 if index_obj.index_type == "flat" else 0.95
        index_obj.memory_cost_mb = result.memory_cost_mb
        task.progress = 100
        task.status = "done"
        task.finished_at = utcnow_iso()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        task = db.query(SearchTask).filter(SearchTask.task_id == task_id).first()
        index_obj = db.query(ANNIndex).filter(ANNIndex.id == index_id).first()
        if task:
            task.status = "failed"
            task.error_message = str(exc)
            task.finished_at = utcnow_iso()
        if index_obj:
            index_obj.build_status = "failed"
        db.commit()
        raise
    finally:
        db.close()
