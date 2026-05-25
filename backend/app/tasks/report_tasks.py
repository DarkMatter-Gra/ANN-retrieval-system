import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.ann_index import ANNIndex
from app.models.dataset import ExpressionMetadata
from app.models.search_task import SearchTask
from app.tasks.celery_app import celery_app
from app.utils.file_store import ensure_dir
from app.utils.time import utcnow_iso


@celery_app.task(bind=True, name="generate_report_task")
def generate_report_task(self, task_id: str):
    db: Session = SessionLocal()
    try:
        task = db.query(SearchTask).filter(SearchTask.task_id == task_id).first()
        if not task:
            raise ValueError("task not found")

        task.status = "running"
        task.progress = 10
        task.started_at = utcnow_iso()
        db.commit()

        payload = task.request_payload or {}
        dataset_id = int(payload.get("dataset_id"))
        index_id = payload.get("index_id")
        include_qc = bool(payload.get("include_qc", True))
        include_performance = bool(payload.get("include_performance", True))
        include_umap_snapshot = bool(payload.get("include_umap_snapshot", False))
        query_id = payload.get("query_id")
        query_snapshot = payload.get("query_snapshot") or {}

        dataset = db.query(ExpressionMetadata).filter(ExpressionMetadata.id == dataset_id).first()
        if not dataset:
            raise ValueError("dataset not found")

        index_query = db.query(ANNIndex).filter(ANNIndex.dataset_id == dataset_id)
        if index_id:
            index_query = index_query.filter(ANNIndex.id == int(index_id))
        indexes = index_query.all()

        report: dict = {
            "meta": {
                "task_id": task_id,
                "dataset_id": dataset_id,
                "index_id": int(index_id) if index_id else None,
                "query_id": query_id,
                "title": payload.get("title"),
                "note": payload.get("note"),
                "created_at": utcnow_iso(),
            }
        }

        if include_qc:
            report["qc"] = {
                "dataset": {
                    "id": dataset.id,
                    "name": dataset.dataset_name,
                    "cell_count": dataset.cell_count,
                    "gene_count": dataset.gene_count,
                    "feature_dim": dataset.feature_dim,
                    "qc_status": dataset.qc_status,
                    "preprocess_status": dataset.preprocess_status,
                }
            }

        if include_performance:
            report["performance"] = {
                "indexes": [
                    {
                        "id": i.id,
                        "type": i.index_type,
                        "metric": i.metric_type,
                        "version": i.version_no,
                        "build_status": i.build_status,
                        "publish_status": i.publish_status,
                        "recall": i.recall_score,
                        "memory_mb": i.memory_cost_mb,
                    }
                    for i in indexes
                ]
            }

        if include_umap_snapshot:
            report["umap_snapshot"] = {
                "highlight_points": query_snapshot.get("highlight_points"),
                "query_cell_id": query_snapshot.get("query_cell_id"),
                "neighbors": query_snapshot.get("results"),
            }

        export_dir = ensure_dir(settings.export_path)
        out_path = export_dir / f"{task_id}.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        task.result_path = str(out_path)
        task.progress = 100
        task.status = "done"
        task.finished_at = utcnow_iso()
        db.commit()

        return str(out_path)
    except Exception as exc:
        task = db.query(SearchTask).filter(SearchTask.task_id == task_id).first()
        if task:
            task.status = "failed"
            task.error_message = str(exc)
            task.finished_at = utcnow_iso()
            db.commit()
        raise
    finally:
        db.close()
