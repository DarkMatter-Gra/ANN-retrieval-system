import json
import os
from pathlib import Path

os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")

from fastapi.testclient import TestClient

from app.main import app
from app.services.search_service import SearchService
from scripts.smoke_backend import PASSWORD, USERNAME, seed_smoke_data


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_single_search_filter_and_persistent_highlights():
    dataset_id, index_id = seed_smoke_data()
    client = TestClient(app)
    headers = auth_headers(client)

    response = client.post(
        "/api/v1/search",
        json={
            "dataset_id": dataset_id,
            "index_id": index_id,
            "query_type": "cell_id",
            "cell_id": "cell_a",
            "top_k": 3,
            "mode": "ann",
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert [item["cell_id"] for item in data["results"]] == ["cell_a", "cell_b", "cell_c"]
    assert data["mode_used"] == "ann"

    filtered = client.post(
        "/api/v1/search",
        json={
            "dataset_id": dataset_id,
            "index_id": index_id,
            "query_type": "cell_id",
            "cell_id": "cell_a",
            "top_k": 2,
            "mode": "ann",
            "filters": {"cell_type": ["Myeloid"]},
        },
        headers=headers,
    )
    assert filtered.status_code == 200
    filtered_data = filtered.json()["data"]
    assert [item["cell_id"] for item in filtered_data["results"]] == ["cell_d", "cell_e"]

    SearchService._QUERY_CACHE.clear()
    highlights = client.get(f"/api/v1/visualizations/{data['query_id']}/highlights", headers=headers)
    assert highlights.status_code == 200
    assert highlights.json()["data"]["neighbors"]


def test_batch_export_download_and_metrics():
    dataset_id, index_id = seed_smoke_data()
    client = TestClient(app)
    headers = auth_headers(client)

    batch = client.post(
        "/api/v1/batch-search",
        json={
            "dataset_id": dataset_id,
            "index_id": index_id,
            "top_k": 2,
            "mode": "ann",
            "queries": [
                {"query_type": "cell_id", "cell_id": "cell_a"},
                {"query_type": "cell_id", "cell_id": "cell_d", "filters": {"organ": "lung"}},
            ],
        },
        headers=headers,
    )
    assert batch.status_code == 200
    task_id = batch.json()["data"]["task_id"]

    task = client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    assert task.status_code == 200
    assert task.json()["data"]["status"] == "done"

    export = client.get(f"/api/v1/tasks/{task_id}/export?format=csv", headers=headers)
    assert export.status_code == 200
    download_url = export.json()["data"]["download_url"]
    assert download_url.endswith(".csv")

    downloaded = client.get(download_url, headers=headers)
    assert downloaded.status_code == 200
    assert "cell_id" in downloaded.text

    metrics = client.get(f"/api/v1/metrics/search?index_id={index_id}&time_range=1h", headers=headers)
    assert metrics.status_code == 200
    assert metrics.json()["data"]["indexes_total"] >= 1


def test_index_build_generates_artifacts():
    dataset_id, _ = seed_smoke_data()
    client = TestClient(app)
    headers = auth_headers(client)

    response = client.post(
        "/api/v1/indexes",
        json={
            "dataset_id": dataset_id,
            "index_name": "pytest_flat_l2",
            "index_type": "flat",
            "metric": "l2",
            "params_json": {},
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "done"

    detail = client.get(f"/api/v1/indexes/{data['index_id']}", headers=headers)
    assert detail.status_code == 200
    file_path = Path(detail.json()["data"]["index_meta"]["file_path"])
    assert file_path.exists()
    assert file_path.with_suffix(".id_map.json").exists()
    assert file_path.with_suffix(".meta.json").exists()

    meta = json.loads(file_path.with_suffix(".meta.json").read_text(encoding="utf-8"))
    assert meta["index_type"] == "flat"
    assert meta["vector_count"] == 6


def test_search_rejects_dimension_mismatch():
    dataset_id, index_id = seed_smoke_data()
    client = TestClient(app)
    headers = auth_headers(client)

    response = client.post(
        "/api/v1/search",
        json={
            "dataset_id": dataset_id,
            "index_id": index_id,
            "query_type": "vector",
            "vector": [1.0, 2.0],
            "top_k": 3,
            "mode": "ann",
        },
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["code"] == 40002
