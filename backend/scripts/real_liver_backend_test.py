"""Run an end-to-end backend test on the teacher-provided liver.h5ad dataset.

Run from backend/:
    python scripts/real_liver_backend_test.py ..\..\liver.h5ad
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.ann_index import ANNIndex
from app.models.cell_metadata import CellMetadata
from app.models.cell_vector import CellVector
from app.models.dataset import ExpressionMetadata
from app.models.search_task import SearchTask
from app.models.user import User
from app.services.preprocess_service import run_preprocess


USERNAME = "liver_real_test_user"
PASSWORD = "LiverTest123"
DATASET_NAME = "liver_real_test"


def log(message: str, **data) -> None:
    payload = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "message": message, **data}
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def reset_existing_dataset(db) -> None:
    old = db.query(ExpressionMetadata).filter(ExpressionMetadata.dataset_name == DATASET_NAME).all()
    for dataset in old:
        dataset_id = dataset.id
        db.query(SearchTask).filter(SearchTask.dataset_id == dataset_id).delete()
        db.query(ANNIndex).filter(ANNIndex.dataset_id == dataset_id).delete()
        db.query(CellVector).filter(CellVector.dataset_id == dataset_id).delete()
        db.query(CellMetadata).filter(CellMetadata.dataset_id == dataset_id).delete()
        db.delete(dataset)
    db.commit()


def prepare_user(db) -> User:
    user = db.query(User).filter(User.username == USERNAME).first()
    if user:
        user.role = "dev"
        user.status = "active"
        db.commit()
        return user
    user = User(
        username=USERNAME,
        email="liver_real_test@example.com",
        password_hash=hash_password(PASSWORD),
        role="dev",
        quota_limit=20,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_dataset_and_preprocess(h5ad_path: Path) -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = prepare_user(db)
        reset_existing_dataset(db)
        dataset = ExpressionMetadata(
            dataset_name=DATASET_NAME,
            file_format="h5ad",
            source_file_path=str(h5ad_path.resolve()),
            owner_user_id=user.id,
            qc_status="pending",
            preprocess_status="pending",
            embedding_methods=[],
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        task_id = uuid.uuid4().hex
        task = SearchTask(
            task_id=task_id,
            owner_user_id=user.id,
            task_type="preprocess_dataset",
            dataset_id=dataset.id,
            status="pending",
            progress=0,
            request_payload={"dataset_id": dataset.id, "source": str(h5ad_path)},
        )
        db.add(task)
        db.commit()

        log("preprocess_start", dataset_id=dataset.id, source=str(h5ad_path), size_mb=round(h5ad_path.stat().st_size / 1024 / 1024, 2))
        started = time.perf_counter()
        run_preprocess(db, task_id, dataset.id)
        elapsed = round(time.perf_counter() - started, 2)
        db.refresh(dataset)
        log(
            "preprocess_done",
            dataset_id=dataset.id,
            seconds=elapsed,
            cell_count=dataset.cell_count,
            gene_count=dataset.gene_count,
            feature_dim=dataset.feature_dim,
            embedding_methods=dataset.embedding_methods,
        )
        return dataset.id, task_id
    finally:
        db.close()


def post_ok(client: TestClient, path: str, payload: dict, headers: dict | None = None) -> dict:
    response = client.post(path, json=payload, headers=headers or {})
    body = response.json()
    if response.status_code != 200 or body.get("code") != 0:
        raise RuntimeError(f"POST {path} failed: {response.status_code} {body}")
    return body["data"]


def get_ok(client: TestClient, path: str, headers: dict) -> dict:
    response = client.get(path, headers=headers)
    body = response.json()
    if response.status_code != 200 or body.get("code") != 0:
        raise RuntimeError(f"GET {path} failed: {response.status_code} {body}")
    return body["data"]


def run_api_checks(dataset_id: int) -> dict:
    client = TestClient(app)
    auth = post_ok(client, "/api/v1/auth/login", {"username": USERNAME, "password": PASSWORD})
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    log("index_build_start", dataset_id=dataset_id, index_type="hnsw", metric="l2")
    started = time.perf_counter()
    index = post_ok(
        client,
        "/api/v1/indexes",
        {
            "dataset_id": dataset_id,
            "index_name": "liver_hnsw_l2_real_test",
            "index_type": "hnsw",
            "metric": "l2",
            "params_json": {"M": 16, "ef_construction": 100, "ef": 64},
        },
        headers,
    )
    index_seconds = round(time.perf_counter() - started, 2)
    index_id = index["index_id"]
    detail = get_ok(client, f"/api/v1/indexes/{index_id}", headers)
    log("index_build_done", index_id=index_id, seconds=index_seconds, status=index["status"], meta=detail["index_meta"])

    embedding = get_ok(client, f"/api/v1/visualizations/{dataset_id}/embedding?method=umap&page=1&page_size=5&color_by=cell_type", headers)
    first_cell_id = embedding["points"][0]["cell_id"]
    first_cell_type = embedding["points"][0].get("cell_type")
    log("embedding_ok", total=embedding["total"], first_cell_id=first_cell_id, first_cell_type=first_cell_type)

    search_payload = {
        "dataset_id": dataset_id,
        "index_id": index_id,
        "query_type": "cell_id",
        "cell_id": first_cell_id,
        "top_k": 10,
        "mode": "ann",
        "ef_search": 128,
    }
    ann_search = post_ok(client, "/api/v1/search", search_payload, headers)
    log("ann_search_ok", query_id=ann_search["query_id"], latency_ms=ann_search["latency_ms"], first_results=[r["cell_id"] for r in ann_search["results"][:3]])

    exact_search = post_ok(client, "/api/v1/search", {**search_payload, "mode": "exact", "top_k": 5}, headers)
    log("exact_search_ok", query_id=exact_search["query_id"], latency_ms=exact_search["latency_ms"], first_results=[r["cell_id"] for r in exact_search["results"][:3]])

    filtered = post_ok(
        client,
        "/api/v1/search",
        {**search_payload, "top_k": 5, "filters": {"cell_type": [first_cell_type]} if first_cell_type else {}},
        headers,
    )
    log("filtered_search_ok", query_id=filtered["query_id"], latency_ms=filtered["latency_ms"], cell_type=first_cell_type, result_count=len(filtered["results"]))

    highlights = get_ok(client, f"/api/v1/visualizations/{ann_search['query_id']}/highlights", headers)
    log("highlights_ok", neighbor_count=len(highlights["neighbors"]))

    batch = post_ok(
        client,
        "/api/v1/batch-search",
        {
            "dataset_id": dataset_id,
            "index_id": index_id,
            "top_k": 5,
            "mode": "ann",
            "queries": [
                {"query_type": "cell_id", "cell_id": first_cell_id},
                {"query_type": "cell_id", "cell_id": ann_search["results"][1]["cell_id"]},
            ],
        },
        headers,
    )
    task = get_ok(client, f"/api/v1/tasks/{batch['task_id']}", headers)
    export = get_ok(client, f"/api/v1/tasks/{batch['task_id']}/export?format=csv", headers)
    download = client.get(export["download_url"], headers=headers)
    if download.status_code != 200:
        raise RuntimeError(f"export download failed: {download.status_code}")
    log("batch_export_ok", task_id=batch["task_id"], status=task["status"], bytes=len(download.content))

    metrics = get_ok(client, f"/api/v1/metrics/search?index_id={index_id}&time_range=1h", headers)
    log("metrics_ok", metrics=metrics)

    report = post_ok(client, "/api/v1/reports/diagnostic", {"query_id": ann_search["query_id"], "title": "Liver real data diagnostic"}, headers)
    pdf = client.get(report["download_url"], headers=headers)
    if pdf.status_code != 200 or not pdf.content.startswith(b"%PDF"):
        raise RuntimeError(f"report pdf download failed: {pdf.status_code}")
    log("report_ok", report=report, pdf_bytes=len(pdf.content))

    return {
        "dataset_id": dataset_id,
        "index_id": index_id,
        "first_cell_id": first_cell_id,
        "first_cell_type": first_cell_type,
        "ann_query_id": ann_search["query_id"],
        "ann_latency_ms": ann_search["latency_ms"],
        "exact_latency_ms": exact_search["latency_ms"],
        "filtered_latency_ms": filtered["latency_ms"],
        "batch_task_id": batch["task_id"],
        "metrics": metrics,
        "report": report,
    }


def main() -> None:
    h5ad_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../../liver.h5ad")
    if not h5ad_path.exists():
        raise FileNotFoundError(h5ad_path)
    dataset_id, preprocess_task_id = create_dataset_and_preprocess(h5ad_path)
    result = run_api_checks(dataset_id)
    result["preprocess_task_id"] = preprocess_task_id

    out_path = settings.report_path / "liver_real_test_summary.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log("real_liver_test_done", summary_path=str(out_path), result=result)


if __name__ == "__main__":
    main()
