import time
import uuid
from pathlib import Path

import faiss
import hnswlib
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    DatasetNotFoundError,
    IndexNotFoundError,
    ParamMissingError,
    ResourceForbiddenError,
    ValidationFailed,
)
from app.models.ann_index import ANNIndex
from app.models.cell_metadata import CellMetadata
from app.models.cell_vector import CellVector
from app.models.dataset import ExpressionMetadata
from app.models.search_task import SearchTask
from app.models.user import User
from app.services import index_service as index_svc
from app.utils.vector_codec import stack_vectors
from app.services.data_access_service import DataAccessService


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

        rows = (
            self.db.query(CellVector)
            .filter(CellVector.dataset_id == dataset_id, CellVector.vector_type == "pca")
            .order_by(CellVector.id.asc())
            .all()
        )
        if not rows:
            raise ValidationFailed("no vectors found for dataset")

        if mode == "exact":
            distances, nn_idx = self._exact_search(rows, query_vector, top_k)
        else:
            distances, nn_idx = self._approx_search(index_obj, query_vector, top_k, payload)

        results = []
        for rank, (idx, dist) in enumerate(zip(nn_idx, distances), start=1):
            i = int(idx)
            if i < 0 or i >= len(rows):
                continue
            row = rows[i]
            # meta = (
            #     self.db.query(CellMetadata)
            #     .filter(CellMetadata.dataset_id == dataset_id, CellMetadata.cell_id == row.cell_id)
            #     .first()
            # )
            meta = DataAccessService(self.db).get_metadata_by_cell_id(dataset_id, row.cell_id)
            results.append(
                {
                    "rank": rank,
                    "cell_id": row.cell_id,
                    "distance": float(dist),
                    "score": float(1.0 / (1.0 + float(dist))),
                    # "cell_type": getattr(meta, "cell_type", None),
                    # "organ": getattr(meta, "organ", None),
                    # "sample_id": getattr(meta, "sample_id", None),
                    "cell_type": meta.get("cell_type"),
                    "organ": meta.get("organ"),
                    "sample_id": meta.get("sample_id"),
                }
            )

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

        return {
            "query_id": query_id,
            "results": results,
            "latency_ms": latency_ms,
            "recall_estimate": index_obj.recall_score,
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

    def _exact_search(self, rows: list[CellVector], query: np.ndarray, top_k: int):
        matrix = stack_vectors([row.vector_blob for row in rows])
        dists = np.linalg.norm(matrix - query, axis=1)
        nn_idx = np.argsort(dists)[:top_k]
        return dists[nn_idx], nn_idx

    def _approx_search(self, index_obj: ANNIndex, query: np.ndarray, top_k: int, payload: dict | None = None):
        cached = index_svc.get_loaded_index(index_obj.id)
        if index_obj.index_type in {"flat", "ivf_pq"}:
            if cached is None:
                cached = faiss.read_index(index_obj.file_path)
                index_svc.cache_index(index_obj.id, cached)
            distances, nn_idx = cached.search(query.astype(np.float32), top_k)
            return distances[0], nn_idx[0]
        if index_obj.index_type == "hnsw":
            if cached is None:
                space = "l2" if index_obj.metric_type == "l2" else "cosine"
                cached = hnswlib.Index(space=space, dim=int(query.shape[1]))
                cached.load_index(index_obj.file_path)
                cached.set_ef(int(index_obj.params_json.get("ef", 64)))
                index_svc.cache_index(index_obj.id, cached)
            ef = (payload or {}).get("ef_search")
            if ef:
                cached.set_ef(int(ef))
            nn_idx, distances = cached.knn_query(query.astype(np.float32), k=top_k)
            return distances[0], nn_idx[0]
        raise ValidationFailed(f"unsupported index type: {index_obj.index_type}")

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
