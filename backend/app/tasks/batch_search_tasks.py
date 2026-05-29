import csv
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.search_task import SearchTask
from app.models.user import User
from app.services.search_service import SearchService
from app.tasks.celery_app import celery_app
from app.utils.file_store import ensure_dir
from app.utils.time import utcnow_iso


def _serialize_jsonl(rows: list[dict], target: Path) -> None:
    with target.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _serialize_csv(rows: list[dict], target: Path) -> None:
    if not rows:
        target.write_text("", encoding="utf-8")
        return
    headers = sorted({k for row in rows for k in row.keys()})
    with target.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _normalize_query(query: dict) -> dict:
    if not isinstance(query, dict):
        raise ValueError("each query must be an object")

    normalized = dict(query)
    query_type = normalized.get("query_type")
    if not query_type:
        if normalized.get("vector") is not None:
            query_type = "vector"
        elif normalized.get("cell_id"):
            query_type = "cell_id"
        else:
            raise ValueError("each query requires query_type with cell_id or vector")
        normalized["query_type"] = query_type

    if query_type == "cell_id" and not normalized.get("cell_id"):
        raise ValueError("cell_id query requires cell_id")
    if query_type == "vector" and normalized.get("vector") is None:
        raise ValueError("vector query requires vector")
    if query_type not in {"cell_id", "vector"}:
        raise ValueError("query_type must be cell_id or vector")

    return normalized


@celery_app.task(bind=True, name="batch_search_task")
def batch_search_task(self, task_id: str):
    db: Session = SessionLocal()
    try:
        task = db.query(SearchTask).filter(SearchTask.task_id == task_id).first()
        if not task:
            raise ValueError("task not found")
        owner = db.query(User).filter(User.id == task.owner_user_id).first()
        if not owner:
            raise ValueError("owner not found")

        task.status = "running"
        task.progress = 5
        task.started_at = utcnow_iso()
        db.commit()

        payload = task.request_payload or {}
        queries = list(payload.get("queries", []))
        total = max(1, len(queries))
        service = SearchService(db)

        flat_rows: list[dict] = []
        for idx, query in enumerate(queries, start=1):
            query = _normalize_query(query)
            single_payload = {
                "dataset_id": payload["dataset_id"],
                "index_id": payload["index_id"],
                "top_k": payload.get("top_k", 10),
                "mode": payload.get("mode", "ann"),
                "filters": payload.get("filters", {}),
                "_record_task": False,
                **query,
            }
            if "filters" not in query and payload.get("filters"):
                single_payload["filters"] = payload["filters"]
            if "ef_search" not in query and payload.get("ef_search"):
                single_payload["ef_search"] = payload["ef_search"]
            result = service.search(owner, single_payload)
            for item in result["results"]:
                flat_rows.append(
                    {
                        "query_index": idx,
                        "query_cell_id": query.get("cell_id"),
                        **item,
                    }
                )
            task.progress = min(95, int(idx / total * 90) + 5)
            db.commit()

        export_dir = ensure_dir(settings.export_path)
        out_path = export_dir / f"{task.task_id}.jsonl"
        _serialize_jsonl(flat_rows, out_path)
        _serialize_csv(flat_rows, export_dir / f"{task.task_id}.csv")

        task.result_path = str(out_path)
        task.progress = 100
        task.status = "done"
        task.finished_at = utcnow_iso()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        task = db.query(SearchTask).filter(SearchTask.task_id == task_id).first()
        if task:
            task.status = "failed"
            task.error_message = str(exc)
            task.finished_at = utcnow_iso()
        db.commit()
        raise
    finally:
        db.close()
