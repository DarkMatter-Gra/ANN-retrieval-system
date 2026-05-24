"""Seed a tiny dataset and exercise the backend core flow.

Run from backend/:
    python scripts/smoke_backend.py
"""

from __future__ import annotations

import shutil
import sys
import os
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.security import hash_password
from app.main import app
from app.db.session import SessionLocal
from app.models.ann_index import ANNIndex
from app.models.cell_metadata import CellMetadata
from app.models.cell_vector import CellVector
from app.models.dataset import ExpressionMetadata
from app.models.search_task import SearchTask
from app.models.user import User
from app.services.ann_engine import ANNEngine
from app.utils.vector_codec import encode_vector


USERNAME = "codex_smoke_user"
PASSWORD = "SmokePass123"
DATASET_NAME = "codex_smoke_cells"

VECTORS = np.asarray(
    [
        [0.00, 0.00, 0.00, 0.00],
        [0.10, 0.00, 0.00, 0.00],
        [0.20, 0.10, 0.00, 0.00],
        [3.00, 3.00, 3.00, 3.00],
        [3.10, 3.00, 3.00, 3.00],
        [0.00, 2.00, 0.00, 0.00],
    ],
    dtype=np.float32,
)

METAS = [
    ("cell_a", "T_cell", "blood", "sample_1"),
    ("cell_b", "T_cell", "blood", "sample_1"),
    ("cell_c", "B_cell", "blood", "sample_2"),
    ("cell_d", "Myeloid", "lung", "sample_3"),
    ("cell_e", "Myeloid", "lung", "sample_3"),
    ("cell_f", "NK_cell", "blood", "sample_4"),
]


def seed_smoke_data() -> tuple[int, int]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == USERNAME).first()
        if not user:
            user = User(
                username=USERNAME,
                email="codex_smoke@example.com",
                password_hash=hash_password(PASSWORD),
                role="dev",
                quota_limit=5,
                status="active",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.role = "dev"
            db.commit()

        old = db.query(ExpressionMetadata).filter(ExpressionMetadata.dataset_name == DATASET_NAME).all()
        old_ids = [dataset.id for dataset in old]
        for dataset in old:
            db.query(SearchTask).filter(SearchTask.dataset_id == dataset.id).delete()
            db.query(ANNIndex).filter(ANNIndex.dataset_id == dataset.id).delete()
            db.query(CellVector).filter(CellVector.dataset_id == dataset.id).delete()
            db.query(CellMetadata).filter(CellMetadata.dataset_id == dataset.id).delete()
            db.delete(dataset)
        db.commit()

        for dataset_id in old_ids:
            shutil.rmtree(settings.index_path / str(dataset_id), ignore_errors=True)
            shutil.rmtree(settings.data_path / "processed" / str(dataset_id), ignore_errors=True)

        dataset = ExpressionMetadata(
            dataset_name=DATASET_NAME,
            file_format="csv",
            source_file_path=str(settings.data_path / "raw" / "codex_smoke.csv"),
            owner_user_id=user.id,
            cell_count=int(VECTORS.shape[0]),
            gene_count=int(VECTORS.shape[1]),
            qc_status="passed",
            preprocess_status="done",
            feature_dim=int(VECTORS.shape[1]),
            embedding_methods=["pca", "umap"],
            deleted_flag=False,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        for idx, (cell_id, cell_type, organ, sample_id) in enumerate(METAS):
            vector = VECTORS[idx]
            db.add(
                CellVector(
                    dataset_id=dataset.id,
                    cell_id=cell_id,
                    vector_type="pca",
                    dim=int(vector.shape[0]),
                    vector_blob=encode_vector(vector),
                    norm_value=float(np.linalg.norm(vector) or 1.0),
                )
            )
            db.add(
                CellMetadata(
                    dataset_id=dataset.id,
                    cell_id=cell_id,
                    cell_type=cell_type,
                    organ=organ,
                    sample_id=sample_id,
                    obs_ext={
                        "cell_type": cell_type,
                        "tissue": organ,
                        "sample_id": sample_id,
                        "batch": "smoke",
                    },
                    qc_flags={},
                )
            )
        db.commit()

        index_dir = settings.index_path / str(dataset.id) / "v1"
        index_dir.mkdir(parents=True, exist_ok=True)
        index_path = index_dir / "flat.index"
        ann_index = ANNIndex(
            dataset_id=dataset.id,
            owner_user_id=user.id,
            index_name="codex_smoke_flat_l2",
            index_type="flat",
            metric_type="l2",
            params_json={},
            file_path=str(index_path),
            version_no=1,
            build_status="done",
            publish_status="published",
            recall_score=1.0,
            memory_cost_mb=round(VECTORS.nbytes / 1024 / 1024, 4),
            is_loaded=False,
        )
        db.add(ann_index)
        db.commit()
        db.refresh(ann_index)
        ANNEngine.build(ann_index, VECTORS, [meta[0] for meta in METAS])

        processed_dir = settings.data_path / "processed" / str(dataset.id)
        processed_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [[0.0, 0.0], [0.1, 0.0], [0.2, 0.1], [3.0, 3.0], [3.1, 3.0], [0.0, 2.0]],
            columns=["umap_x", "umap_y"],
            index=[meta[0] for meta in METAS],
        ).to_csv(processed_dir / "umap.csv")

        return dataset.id, ann_index.id
    finally:
        db.close()


def post_ok(client: TestClient, path: str, payload: dict, headers: dict | None = None) -> dict:
    response = client.post(path, json=payload, headers=headers or {})
    body = response.json()
    assert response.status_code == 200, (path, response.status_code, body)
    assert body["code"] == 0, (path, body)
    return body["data"]


def get_ok(client: TestClient, path: str, headers: dict) -> dict:
    response = client.get(path, headers=headers)
    body = response.json()
    assert response.status_code == 200, (path, response.status_code, body)
    assert body["code"] == 0, (path, body)
    return body["data"]


def main() -> None:
    dataset_id, index_id = seed_smoke_data()
    client = TestClient(app)

    auth = post_ok(client, "/api/v1/auth/login", {"username": USERNAME, "password": PASSWORD})
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    search = post_ok(
        client,
        "/api/v1/search",
        {
            "dataset_id": dataset_id,
            "index_id": index_id,
            "query_type": "cell_id",
            "cell_id": "cell_a",
            "top_k": 3,
            "mode": "ann",
        },
        headers,
    )
    assert [item["cell_id"] for item in search["results"]] == ["cell_a", "cell_b", "cell_c"]

    filtered = post_ok(
        client,
        "/api/v1/search",
        {
            "dataset_id": dataset_id,
            "index_id": index_id,
            "query_type": "cell_id",
            "cell_id": "cell_a",
            "top_k": 2,
            "mode": "ann",
            "filters": {"cell_type": ["Myeloid"]},
        },
        headers,
    )
    assert [item["cell_id"] for item in filtered["results"]] == ["cell_d", "cell_e"]

    batch = post_ok(
        client,
        "/api/v1/batch-search",
        {
            "dataset_id": dataset_id,
            "index_id": index_id,
            "top_k": 2,
            "mode": "ann",
            "queries": [
                {"query_type": "cell_id", "cell_id": "cell_a"},
                {"query_type": "cell_id", "cell_id": "cell_d", "filters": {"organ": "lung"}},
            ],
        },
        headers,
    )
    task = get_ok(client, f"/api/v1/tasks/{batch['task_id']}", headers)
    assert task["status"] == "done"
    export_info = get_ok(client, f"/api/v1/tasks/{batch['task_id']}/export?format=csv", headers)
    export_response = client.get(export_info["download_url"], headers=headers)
    assert export_response.status_code == 200, export_response.text
    assert "cell_id" in export_response.text

    highlights = get_ok(client, f"/api/v1/visualizations/{search['query_id']}/highlights", headers)
    assert highlights["neighbors"]

    metrics = get_ok(client, f"/api/v1/metrics/search?index_id={index_id}&time_range=1h", headers)
    assert metrics["indexes_total"] >= 1

    report = post_ok(
        client,
        "/api/v1/reports/diagnostic",
        {"query_id": search["query_id"], "title": "Smoke diagnostic"},
        headers,
    )
    assert report["status"] == "done"

    print(
        {
            "status": "ok",
            "username": USERNAME,
            "password": PASSWORD,
            "dataset_id": dataset_id,
            "index_id": index_id,
            "query_id": search["query_id"],
            "batch_task_id": batch["task_id"],
        }
    )


if __name__ == "__main__":
    main()
