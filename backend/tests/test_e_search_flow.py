import json
import os
from pathlib import Path

os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from app.services.search_service import SearchService
from scripts.smoke_backend import PASSWORD, USERNAME, seed_smoke_data


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def auth_headers_for(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def ensure_user(username: str, password: str, role: str = "dev") -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            user.password_hash = hash_password(password)
            user.role = role
            user.status = "active"
        else:
            db.add(
                User(
                    username=username,
                    email=f"{username}@example.com",
                    password_hash=hash_password(password),
                    role=role,
                    quota_limit=5,
                    status="active",
                )
            )
        db.commit()
    finally:
        db.close()


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


def test_diagnostic_report_generates_pdf_download():
    dataset_id, index_id = seed_smoke_data()
    client = TestClient(app)
    headers = auth_headers(client)

    search = client.post(
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
    assert search.status_code == 200
    query_id = search.json()["data"]["query_id"]

    report = client.post(
        "/api/v1/reports/diagnostic",
        json={"query_id": query_id, "title": "Pytest diagnostic"},
        headers=headers,
    )
    assert report.status_code == 200
    report_data = report.json()["data"]
    assert report_data["status"] == "done"
    assert report_data["download_url"].endswith(".pdf")
    assert report_data["json_download_url"].endswith(".json")

    pdf = client.get(report_data["download_url"], headers=headers)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    json_report = client.get(report_data["json_download_url"], headers=headers)
    assert json_report.status_code == 200
    assert json_report.json()["query"]["query_id"] == query_id


def test_file_download_rejects_path_traversal_and_foreign_report_access():
    dataset_id, index_id = seed_smoke_data()
    client = TestClient(app)
    owner_headers = auth_headers(client)

    bad_export = client.get("/api/v1/files/exports/..%5Csecret.csv", headers=owner_headers)
    assert bad_export.status_code == 400
    assert bad_export.json()["code"] == 40002

    bad_report = client.get("/api/v1/files/reports/diagnostic.bad.exe", headers=owner_headers)
    assert bad_report.status_code == 400
    assert bad_report.json()["code"] == 40002

    search = client.post(
        "/api/v1/search",
        json={
            "dataset_id": dataset_id,
            "index_id": index_id,
            "query_type": "cell_id",
            "cell_id": "cell_a",
            "top_k": 3,
            "mode": "ann",
        },
        headers=owner_headers,
    )
    assert search.status_code == 200
    report = client.post(
        "/api/v1/reports/diagnostic",
        json={"query_id": search.json()["data"]["query_id"], "title": "Permission diagnostic"},
        headers=owner_headers,
    )
    assert report.status_code == 200
    download_url = report.json()["data"]["download_url"]

    ensure_user("codex_other_user", "OtherPass123", role="dev")
    other_headers = auth_headers_for(client, "codex_other_user", "OtherPass123")
    forbidden = client.get(download_url, headers=other_headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == 40302
