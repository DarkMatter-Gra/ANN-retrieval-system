"""诊断报告任务（占位实现）。

正式版本可接 weasyprint / playwright 渲染 HTML 模板，这里先输出 JSON 便于演示。
"""

import json
from pathlib import Path

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.ann_index import ANNIndex
from app.models.dataset import ExpressionMetadata
from app.models.search_task import SearchTask
from app.tasks.celery_app import celery_app
from app.utils.file_store import ensure_dir


@celery_app.task(bind=True, name="generate_report_task")
def generate_report_task(self, payload: dict, user_id: int):
    db = SessionLocal()
    try:
        query_id = payload.get("query_id")
        query_task = db.query(SearchTask).filter(SearchTask.task_id == query_id).first()
        if not query_task:
            raise ValueError("query_id not found")

        dataset_id = int(query_task.dataset_id)
        dataset = db.query(ExpressionMetadata).filter(ExpressionMetadata.id == dataset_id).first()
        indexes = db.query(ANNIndex).filter(ANNIndex.dataset_id == dataset_id).all()

        report = {
            "title": payload.get("title") or "ANN Search Diagnostic Report",
            "note": payload.get("note"),
            "query": {
                "query_id": query_id,
                "index_id": query_task.index_id,
                "payload": query_task.request_payload,
                "status": query_task.status,
            },
            "dataset": {
                "id": dataset_id,
                "name": getattr(dataset, "dataset_name", None),
                "cell_count": getattr(dataset, "cell_count", 0),
                "gene_count": getattr(dataset, "gene_count", 0),
                "feature_dim": getattr(dataset, "feature_dim", 0),
                "qc_status": getattr(dataset, "qc_status", None),
            },
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
            ],
            "operator_user_id": user_id,
        }

        report_dir = ensure_dir(settings.report_path)
        out_path = report_dir / f"diagnostic_{dataset_id}_{self.request.id}.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(out_path)
    finally:
        db.close()
