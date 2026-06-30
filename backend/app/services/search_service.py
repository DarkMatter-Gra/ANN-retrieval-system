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

        index_id = int(payload["index_id"])
        index_obj = self._validate_index_v2(
            index_id=index_id,
            requested_dataset_id=payload.get("dataset_id"),
            current_user=current_user,
        )
        # 联合索引参与的全部 dataset
        all_index_datasets: list[int] = list(index_obj.dataset_ids or [index_obj.dataset_id])
        # 跨数据集结果过滤：未传 dataset_ids 时不过滤；传 dataset_id 时退化为 [dataset_id]
        if payload.get("dataset_ids"):
            allowed_datasets = [int(d) for d in payload["dataset_ids"] if int(d) in set(all_index_datasets)]
            if not allowed_datasets:
                raise ValidationFailed("dataset_ids not in index")
        elif payload.get("dataset_id") is not None:
            allowed_datasets = [int(payload["dataset_id"])]
        else:
            allowed_datasets = list(all_index_datasets)

        query_vector = self._load_query_vector(index_obj, payload)
        top_k = int(payload.get("top_k", 10))
        mode = payload.get("mode", "ann")
        metric = index_obj.metric_type

        rows = (
            self.db.query(CellVector)
            .filter(
                CellVector.dataset_id.in_(all_index_datasets),
                CellVector.vector_type == "pca",
            )
            .order_by(CellVector.dataset_id.asc(), CellVector.id.asc())
            .all()
        )
        if not rows:
            raise ValidationFailed("no vectors found for dataset")
        rows = self._rows_in_index_order(index_obj, rows)
        self._validate_query_dim(query_vector, rows[0].dim)

        filters = payload.get("filters") or {}
        filtered_rows = self._filter_rows(allowed_datasets, rows, filters)
        if not filtered_rows:
            raise ValidationFailed("no vectors match filters")

        if mode == "exact":
            search_rows = filtered_rows
            distances, nn_idx = self._exact_search(search_rows, query_vector, top_k, metric)
            results = self._build_results(all_index_datasets, search_rows, nn_idx, distances, metric)
            mode_used = "exact"
        else:
            distances, nn_idx = self._approx_search(
                index_obj=index_obj,
                query=query_vector,
                top_k=self._ann_fetch_k(top_k, len(rows), bool(filters) or len(allowed_datasets) < len(all_index_datasets)),
                payload=payload,
            )
            allowed_keys = {(int(row.dataset_id), row.cell_id) for row in filtered_rows}
            results = self._build_results(
                dataset_ids=all_index_datasets,
                rows=rows,
                indices=nn_idx,
                distances=distances,
                metric=metric,
                allowed_keys=allowed_keys,
                limit=top_k,
            )
            mode_used = "ann"
            if len(results) < min(top_k, len(filtered_rows)):
                distances, nn_idx = self._exact_search(filtered_rows, query_vector, top_k, metric)
                results = self._build_results(all_index_datasets, filtered_rows, nn_idx, distances, metric)
                mode_used = "ann_with_exact_filter_fallback"

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        query_id = uuid.uuid4().hex
        primary_dataset_id = int(payload.get("dataset_id") or index_obj.dataset_id)
        highlight_points = self.build_highlight_points(primary_dataset_id, payload, results)

        SearchService._QUERY_CACHE[query_id] = {
            "dataset_id": primary_dataset_id,
            "dataset_ids": all_index_datasets,
            "index_id": index_id,
            "query_cell_id": payload.get("cell_id"),
            "results": results,
            "highlight_points": highlight_points,
        }
        if payload.get("_record_task", True):
            self._record_search_task(
                query_id=query_id,
                current_user=current_user,
                dataset_id=primary_dataset_id,
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
            "index_dataset_ids": all_index_datasets,
        }

    def create_batch_task(self, current_user: User, payload: dict) -> dict:
        from app.tasks.batch_search_tasks import batch_search_task

        index_id = int(payload["index_id"])
        index_obj = self._validate_index_v2(
            index_id=index_id,
            requested_dataset_id=payload.get("dataset_id"),
            current_user=current_user,
        )

        if not payload.get("queries"):
            raise ParamMissingError("queries is required")

        primary_dataset_id = int(payload.get("dataset_id") or index_obj.dataset_id)
        task = SearchTask(
            task_id=uuid.uuid4().hex,
            owner_user_id=current_user.id,
            task_type="batch_search",
            dataset_id=primary_dataset_id,
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
    def _validate_index_v2(
        self,
        index_id: int,
        requested_dataset_id: int | None,
        current_user: User,
    ) -> ANNIndex:
        index_obj = self.db.query(ANNIndex).filter(ANNIndex.id == index_id).first()
        if not index_obj:
            raise IndexNotFoundError()
        if index_obj.build_status != "done":
            raise ConflictError("index unavailable")
        if current_user.role != "admin" and index_obj.owner_user_id != current_user.id:
            raise ResourceForbiddenError()
        if requested_dataset_id is not None:
            index_datasets = set(index_obj.dataset_ids or [index_obj.dataset_id])
            if int(requested_dataset_id) not in index_datasets:
                raise IndexNotFoundError()
        return index_obj

    def _load_query_vector(self, index_obj: ANNIndex, payload: dict) -> np.ndarray:
        if payload["query_type"] == "vector":
            if not payload.get("vector"):
                raise ParamMissingError("vector is required")
            vec = np.asarray(payload["vector"], dtype=np.float32)
            return vec.reshape(1, -1)

        cell_id = payload.get("cell_id")
        if not cell_id:
            raise ParamMissingError("cell_id is required")

        # 跨数据集 cell_id 解析：优先 source_dataset_id → dataset_id → 索引所有 dataset
        candidate_ds_ids: list[int]
        if payload.get("source_dataset_id") is not None:
            candidate_ds_ids = [int(payload["source_dataset_id"])]
        elif payload.get("dataset_id") is not None:
            candidate_ds_ids = [int(payload["dataset_id"])]
        else:
            candidate_ds_ids = list(index_obj.dataset_ids or [index_obj.dataset_id])

        for ds_id in candidate_ds_ids:
            row = (
                self.db.query(CellVector)
                .filter(
                    CellVector.dataset_id == ds_id,
                    CellVector.cell_id == cell_id,
                    CellVector.vector_type == "pca",
                )
                .first()
            )
            if row:
                vec = DataAccessService(self.db).get_vector_by_cell_id(ds_id, cell_id)
                return vec.reshape(1, -1)
        raise ParamMissingError(f"cell_id {cell_id} not found in candidate datasets")

    @staticmethod
    def _validate_query_dim(query: np.ndarray, expected_dim: int) -> None:
        actual_dim = int(query.shape[1])
        if actual_dim != int(expected_dim):
            raise ValidationFailed(f"query vector dim mismatch: expected {expected_dim}, got {actual_dim}")

    def _filter_rows(
        self,
        allowed_dataset_ids: list[int],
        rows: list[CellVector],
        filters: dict[str, Any],
    ) -> list[CellVector]:
        allowed_set = set(int(d) for d in allowed_dataset_ids)
        ds_filtered = [row for row in rows if int(row.dataset_id) in allowed_set]
        normalized = {k: v for k, v in filters.items() if v not in (None, "", [])}
        if not normalized:
            return ds_filtered

        metas = (
            self.db.query(CellMetadata)
            .filter(CellMetadata.dataset_id.in_(list(allowed_set)))
            .all()
        )
        matched_keys = {
            (int(meta.dataset_id), meta.cell_id)
            for meta in metas
            if self._metadata_matches(meta, normalized)
        }
        return [row for row in ds_filtered if (int(row.dataset_id), row.cell_id) in matched_keys]

    @staticmethod
    def _rows_in_index_order(index_obj: ANNIndex, rows: list[CellVector]) -> list[CellVector]:
        entries = ANNEngine.read_id_map_entries(index_obj)
        if not entries or len(entries) != len(rows):
            return rows
        # 多数据集联合索引：通过 (dataset_id, cell_id) 复合键定位避免 cell_id 冲突
        if any(e.get("dataset_id") is not None for e in entries):
            row_map = {(int(row.dataset_id), row.cell_id): row for row in rows}
            ordered = [
                row_map[(int(e["dataset_id"]), e["cell_id"])]
                for e in entries
                if (int(e["dataset_id"]), e["cell_id"]) in row_map
            ]
        else:
            row_map_legacy = {row.cell_id: row for row in rows}
            ordered = [row_map_legacy[e["cell_id"]] for e in entries if e["cell_id"] in row_map_legacy]
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
        dataset_ids: list[int],
        rows: list[CellVector],
        indices,
        distances,
        metric: str,
        allowed_keys: set[tuple[int, str]] | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        result_pairs: list[tuple[CellVector, float]] = []
        for idx, dist in zip(indices, distances):
            i = int(idx)
            if i < 0 or i >= len(rows):
                continue
            row = rows[i]
            if allowed_keys is not None and (int(row.dataset_id), row.cell_id) not in allowed_keys:
                continue
            result_pairs.append((row, float(dist)))
            if limit is not None and len(result_pairs) >= limit:
                break

        # 按 dataset 分组批量取元数据，避免 cell_id 跨数据集冲突
        data_access = DataAccessService(self.db)
        per_ds_cells: dict[int, list[str]] = {}
        for row, _ in result_pairs:
            per_ds_cells.setdefault(int(row.dataset_id), []).append(row.cell_id)
        meta_map: dict[tuple[int, str], dict] = {}
        for ds_id, cell_ids in per_ds_cells.items():
            for item in data_access.get_metadata_by_cell_ids(ds_id, cell_ids):
                meta_map[(ds_id, item["cell_id"])] = item

        results = []
        for rank, (row, dist) in enumerate(result_pairs, start=1):
            meta = meta_map.get((int(row.dataset_id), row.cell_id), {})
            results.append(
                {
                    "rank": rank,
                    "cell_id": row.cell_id,
                    "source_dataset_id": int(row.dataset_id),
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
