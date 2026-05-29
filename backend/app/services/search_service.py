import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    IndexNotFoundError,
    ParamMissingError,
    ResourceForbiddenError,
    ValidationFailed,
)
from app.models.ann_index import ANNIndex
from app.models.cell_metadata import CellMetadata
from app.models.cell_vector import CellVector
from app.models.search_task import SearchTask
from app.models.user import User
from app.services import index_service as index_svc
from app.services.ann_engine import ANNEngine
from app.services.data_access_service import DataAccessService
from app.utils.time import utcnow_iso
from app.utils.vector_codec import stack_vectors


class SearchService:
    # 进程内查询结果缓存：query_id -> {dataset_id, query_cell_id, results}
    _QUERY_CACHE: dict[str, dict] = {}

    @classmethod
    def get_query_snapshot(cls, query_id: str) -> dict | None:
        return cls._QUERY_CACHE.get(query_id)

    def __init__(self, db: Session):
        self.db = db

    # ----------------------------- 入口 -----------------------------
    def search(self, current_user: User, payload: dict) -> dict:
        start = time.perf_counter()

        dataset_id = int(payload["dataset_id"])
        index_id = int(payload["index_id"])
        index_obj = self._validate_index(index_id, dataset_id, current_user)

        query_vector = self._load_query_vector(dataset_id, payload)
        top_k = int(payload.get("top_k", 10))
        mode = payload.get("mode", "ann")
        metric = index_obj.metric_type

        rows = (
            self.db.query(CellVector)
            .filter(CellVector.dataset_id == dataset_id, CellVector.vector_type == "pca")
            .order_by(CellVector.id.asc())
            .all()
        )
        if not rows:
            raise ValidationFailed("no vectors found for dataset")
        rows = self._rows_in_index_order(index_obj, rows)
        self._validate_query_dim(query_vector, rows[0].dim)

        filters = payload.get("filters") or {}
        filtered_rows = self._filter_rows_by_metadata(dataset_id, rows, filters)
        if not filtered_rows:
            raise ValidationFailed("no vectors match filters")

        if mode == "exact":
            search_rows = filtered_rows
            distances, nn_idx = self._exact_search(search_rows, query_vector, top_k, metric)
            results = self._build_results(dataset_id, search_rows, nn_idx, distances, metric)
            mode_used = "exact"
        else:
            distances, nn_idx = self._approx_search(
                index_obj=index_obj,
                query=query_vector,
                top_k=self._ann_fetch_k(top_k, len(rows), bool(filters)),
                payload=payload,
            )
            allowed_ids = {row.cell_id for row in filtered_rows}
            results = self._build_results(
                dataset_id=dataset_id,
                rows=rows,
                indices=nn_idx,
                distances=distances,
                metric=metric,
                allowed_cell_ids=allowed_ids,
                limit=top_k,
            )
            mode_used = "ann"
            if len(results) < min(top_k, len(filtered_rows)):
                distances, nn_idx = self._exact_search(filtered_rows, query_vector, top_k, metric)
                results = self._build_results(dataset_id, filtered_rows, nn_idx, distances, metric)
                mode_used = "ann_with_exact_filter_fallback"

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        query_id = uuid.uuid4().hex
        highlight_points = self.build_highlight_points(dataset_id, payload, results)

        SearchService._QUERY_CACHE[query_id] = {
            "dataset_id": dataset_id,
            "index_id": index_id,
            "query_cell_id": payload.get("cell_id"),
            "results": results,
            "highlight_points": highlight_points,
        }
        if payload.get("_record_task", True):
            self._record_search_task(
                query_id=query_id,
                current_user=current_user,
                dataset_id=dataset_id,
                index_id=index_id,
                payload=payload,
                latency_ms=latency_ms,
                result_count=len(results),
                mode_used=mode_used,
                results=results,
                highlight_points=highlight_points,
            )

        return {
            "query_id": query_id,
            "results": results,
            "latency_ms": latency_ms,
            "recall_estimate": index_obj.recall_score,
            "mode_used": mode_used,
            "highlight_points": highlight_points,
        }

    def create_batch_task(self, current_user: User, payload: dict) -> dict:
        from app.tasks.batch_search_tasks import batch_search_task

        dataset_id = int(payload["dataset_id"])
        index_id = int(payload["index_id"])
        self._validate_index(index_id, dataset_id, current_user)

        if not payload.get("queries"):
            raise ParamMissingError("queries is required")

        task = SearchTask(
            task_id=uuid.uuid4().hex,
            owner_user_id=current_user.id,
            task_type="batch_search",
            dataset_id=dataset_id,
            index_id=index_id,
            status="pending",
            progress=0,
            request_payload=payload,
        )
        self.db.add(task)
        self.db.commit()
        batch_search_task.delay(task.task_id)
        self.db.refresh(task)
        return {"task_id": task.task_id, "status": task.status}

    # ----------------------------- 内部 -----------------------------
    def _validate_index(self, index_id: int, dataset_id: int, current_user: User) -> ANNIndex:
        index_obj = (
            self.db.query(ANNIndex)
            .filter(ANNIndex.id == index_id, ANNIndex.dataset_id == dataset_id)
            .first()
        )
        if not index_obj:
            raise IndexNotFoundError()
        if index_obj.build_status != "done":
            raise ConflictError("index unavailable")
        if current_user.role != "admin" and index_obj.owner_user_id != current_user.id:
            raise ResourceForbiddenError()
        return index_obj

    def _load_query_vector(self, dataset_id: int, payload: dict) -> np.ndarray:
        if payload["query_type"] == "vector":
            if not payload.get("vector"):
                raise ParamMissingError("vector is required")
            vec = np.asarray(payload["vector"], dtype=np.float32)
            return vec.reshape(1, -1)

        # cell_id = payload.get("cell_id")
        # if not cell_id:
        #     raise ParamMissingError("cell_id is required")
        # row = (
        #     self.db.query(CellVector)
        #     .filter(
        #         CellVector.dataset_id == dataset_id,
        #         CellVector.cell_id == cell_id,
        #         CellVector.vector_type == "pca",
        #     )
        #     .first()
        # )
        # if not row:
        #     raise DatasetNotFoundError("cell_id not found")
        # return np.frombuffer(row.vector_blob, dtype=np.float32).reshape(1, -1)

        cell_id = payload.get("cell_id")
        if not cell_id:
            raise ParamMissingError("cell_id is required")

        vector = DataAccessService(self.db).get_vector_by_cell_id(dataset_id, cell_id)
        return vector.reshape(1, -1)

    @staticmethod
    def _validate_query_dim(query: np.ndarray, expected_dim: int) -> None:
        actual_dim = int(query.shape[1])
        if actual_dim != int(expected_dim):
            raise ValidationFailed(f"query vector dim mismatch: expected {expected_dim}, got {actual_dim}")

    def _filter_rows_by_metadata(
        self,
        dataset_id: int,
        rows: list[CellVector],
        filters: dict[str, Any],
    ) -> list[CellVector]:
        normalized = {k: v for k, v in filters.items() if v not in (None, "", [])}
        if not normalized:
            return rows

        metas = (
            self.db.query(CellMetadata)
            .filter(CellMetadata.dataset_id == dataset_id)
            .all()
        )
        matched_ids = {
            meta.cell_id
            for meta in metas
            if self._metadata_matches(meta, normalized)
        }
        return [row for row in rows if row.cell_id in matched_ids]

    @staticmethod
    def _rows_in_index_order(index_obj: ANNIndex, rows: list[CellVector]) -> list[CellVector]:
        cell_ids = ANNEngine.read_id_map(index_obj)
        if not cell_ids or len(cell_ids) != len(rows):
            return rows
        row_map = {row.cell_id: row for row in rows}
        ordered = [row_map[cell_id] for cell_id in cell_ids if cell_id in row_map]
        return ordered if len(ordered) == len(rows) else rows

    @staticmethod
    def _metadata_matches(meta: CellMetadata, filters: dict[str, Any]) -> bool:
        for key, expected in filters.items():
            actual = getattr(meta, key, None)
            if actual is None:
                obs_ext = meta.obs_ext or {}
                actual = obs_ext.get(key)
                if actual is None and key.startswith("obs_ext."):
                    actual = obs_ext.get(key.split(".", 1)[1])
            if isinstance(expected, list):
                expected_values = {str(v) for v in expected}
                if str(actual) not in expected_values:
                    return False
            elif str(actual) != str(expected):
                return False
        return True

    @staticmethod
    def _ann_fetch_k(top_k: int, total: int, has_filters: bool) -> int:
        if total <= 0:
            return 0
        if not has_filters:
            return min(top_k, total)
        return min(total, max(top_k, top_k * 20))

    def _exact_search(self, rows: list[CellVector], query: np.ndarray, top_k: int, metric: str):
        matrix = stack_vectors([row.vector_blob for row in rows])
        return ANNEngine.exact_search(matrix, query, metric, top_k)

    def _approx_search(
        self,
        index_obj: ANNIndex,
        query: np.ndarray,
        top_k: int,
        payload: dict | None = None,
    ):
        cached = index_svc.get_loaded_index(index_obj.id)
        if cached is None:
            try:
                cached = ANNEngine.load(index_obj, dim=int(query.shape[1]))
            except ValueError as exc:
                raise ValidationFailed(str(exc)) from exc
            index_svc.cache_index(index_obj.id, cached)
        try:
            return ANNEngine.search(index_obj, cached, query, top_k, payload or {})
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc

    def _build_results(
        self,
        dataset_id: int,
        rows: list[CellVector],
        indices,
        distances,
        metric: str,
        allowed_cell_ids: set[str] | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        result_pairs: list[tuple[CellVector, float]] = []
        for idx, dist in zip(indices, distances):
            i = int(idx)
            if i < 0 or i >= len(rows):
                continue
            row = rows[i]
            if allowed_cell_ids is not None and row.cell_id not in allowed_cell_ids:
                continue
            result_pairs.append((row, float(dist)))
            if limit is not None and len(result_pairs) >= limit:
                break

        data_access = DataAccessService(self.db)
        meta_map = {
            item["cell_id"]: item
            for item in data_access.get_metadata_by_cell_ids(
                dataset_id,
                [row.cell_id for row, _ in result_pairs],
            )
        }

        results = []
        for rank, (row, dist) in enumerate(result_pairs, start=1):
            meta = meta_map.get(row.cell_id, {})
            results.append(
                {
                    "rank": rank,
                    "cell_id": row.cell_id,
                    "distance": float(dist),
                    "score": self._score_from_distance(metric, float(dist)),
                    "cell_type": meta.get("cell_type"),
                    "organ": meta.get("organ"),
                    "sample_id": meta.get("sample_id"),
                }
            )
        return results

    @staticmethod
    def _score_from_distance(metric: str, distance: float) -> float:
        if metric in {"ip", "cosine"}:
            return float(-distance if metric == "ip" else 1.0 - distance)
        return float(1.0 / (1.0 + max(distance, 0.0)))

    def _record_search_task(
        self,
        query_id: str,
        current_user: User,
        dataset_id: int,
        index_id: int,
        payload: dict,
        latency_ms: float,
        result_count: int,
        mode_used: str,
        results: list[dict],
        highlight_points: dict,
    ) -> None:
        task_payload = {
            **{k: v for k, v in payload.items() if not k.startswith("_")},
            "latency_ms": latency_ms,
            "result_count": result_count,
            "mode_used": mode_used,
            "results": results,
            "highlight_points": highlight_points,
        }
        now = utcnow_iso()
        self.db.add(
            SearchTask(
                task_id=query_id,
                owner_user_id=current_user.id,
                task_type="search",
                dataset_id=dataset_id,
                index_id=index_id,
                status="done",
                progress=100,
                request_payload=task_payload,
                started_at=now,
                finished_at=now,
            )
        )
        self.db.commit()

    def build_highlight_points(self, dataset_id: int, payload: dict, results: list[dict]) -> dict:
        umap_path = Path(settings.data_path) / "processed" / str(dataset_id) / "umap.csv"
        if not umap_path.exists():
            return {"query": None, "neighbors": []}
        umap = pd.read_csv(umap_path, index_col=0)
        query_point = None
        if payload.get("cell_id") and payload["cell_id"] in umap.index:
            query_point = umap.loc[payload["cell_id"]].tolist()
        neighbors = []
        for item in results:
            if item["cell_id"] in umap.index:
                point = umap.loc[item["cell_id"]].tolist()
                neighbors.append({"cell_id": item["cell_id"], "point": point})
        return {"query": query_point, "neighbors": neighbors}
