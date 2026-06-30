from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import faiss
import hnswlib
import numpy as np

from app.models.ann_index import ANNIndex
from app.utils.index_io import load_hnsw, read_faiss, write_faiss, write_hnsw
from app.utils.time import utcnow_iso


SUPPORTED_INDEX_TYPES = {"flat", "ivf_pq", "hnsw", "hnsw_rerank"}
SUPPORTED_METRICS = {"l2", "ip", "cosine"}

# hnsw_rerank：召回阶段 fetch_k = top_k * rerank_factor，再用精排数据回算原始距离
DEFAULT_RERANK_FACTOR = 4
MIN_RERANK_FETCH = 32


@dataclass
class IndexBuildResult:
    index_path: str
    id_map_path: str
    meta_path: str
    dim: int
    vector_count: int
    build_seconds: float
    memory_cost_mb: float


class ANNEngine:
    @staticmethod
    def validate_config(
        index_type: str,
        metric: str,
        params: dict[str, Any] | None,
        dim: int,
        vector_count: int,
    ) -> None:
        params = params or {}
        if index_type not in SUPPORTED_INDEX_TYPES:
            raise ValueError(f"unsupported index type: {index_type}")
        if metric not in SUPPORTED_METRICS:
            raise ValueError(f"unsupported metric type: {metric}")
        if dim <= 0:
            raise ValueError("vector dimension must be positive")
        if vector_count <= 0:
            raise ValueError("vector count must be positive")

        if index_type == "ivf_pq":
            nlist = int(params.get("nlist", min(128, max(1, vector_count))))
            m = int(params.get("m", ANNEngine.default_pq_m(dim)))
            nbits = int(params.get("nbits", 8))
            nprobe = int(params.get("nprobe", min(16, nlist)))
            if nlist < 1 or nlist > vector_count:
                raise ValueError("ivf_pq nlist must be between 1 and vector_count")
            if m < 1 or dim % m != 0:
                raise ValueError("ivf_pq m must divide vector dimension")
            if nbits < 4 or nbits > 12:
                raise ValueError("ivf_pq nbits must be between 4 and 12")
            if vector_count < 2**nbits:
                raise ValueError("ivf_pq vector_count must be >= 2**nbits; lower nbits or use flat/hnsw")
            if nprobe < 1 or nprobe > nlist:
                raise ValueError("ivf_pq nprobe must be between 1 and nlist")

        if index_type == "hnsw":
            m = int(params.get("M", 16))
            ef_construction = int(params.get("ef_construction", 200))
            ef = int(params.get("ef", 64))
            if m < 4 or m > 128:
                raise ValueError("hnsw M must be between 4 and 128")
            if ef_construction < m:
                raise ValueError("hnsw ef_construction must be >= M")
            if ef < 1:
                raise ValueError("hnsw ef must be positive")

        if index_type == "hnsw_rerank":
            m = int(params.get("M", 16))
            ef_construction = int(params.get("ef_construction", 200))
            ef = int(params.get("ef", 64))
            rerank_factor = int(params.get("rerank_factor", DEFAULT_RERANK_FACTOR))
            if m < 4 or m > 128:
                raise ValueError("hnsw_rerank M must be between 4 and 128")
            if ef_construction < m:
                raise ValueError("hnsw_rerank ef_construction must be >= M")
            if ef < 1:
                raise ValueError("hnsw_rerank ef must be positive")
            if rerank_factor < 1 or rerank_factor > 64:
                raise ValueError("hnsw_rerank rerank_factor must be between 1 and 64")
            use_fp16 = bool(params.get("use_fp16", True))
            if not isinstance(use_fp16, bool):
                raise ValueError("hnsw_rerank use_fp16 must be boolean")

    @staticmethod
    def default_pq_m(dim: int) -> int:
        for candidate in (16, 12, 10, 8, 6, 5, 4, 3, 2, 1):
            if dim % candidate == 0:
                return candidate
        return 1

    @staticmethod
    def build(index_obj: ANNIndex, vectors: np.ndarray, cell_ids: list[str], dataset_ids: list[int] | None = None) -> IndexBuildResult:
        prepared = ANNEngine.prepare_matrix(vectors)
        if prepared.shape[0] != len(cell_ids):
            raise ValueError("cell_ids length must match vector count")
        if dataset_ids is not None and len(dataset_ids) != len(cell_ids):
            raise ValueError("dataset_ids length must match cell_ids length")
        dim = int(prepared.shape[1])
        vector_count = int(prepared.shape[0])
        params = dict(index_obj.params_json or {})
        ANNEngine.validate_config(index_obj.index_type, index_obj.metric_type, params, dim, vector_count)

        index_path = Path(index_obj.file_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        id_map_path = index_path.with_suffix(".id_map.json")
        meta_path = index_path.with_suffix(".meta.json")

        build_vectors = ANNEngine.prepare_vectors_for_index(
            prepared,
            index_obj.index_type,
            index_obj.metric_type,
        )

        started = time.perf_counter()
        if index_obj.index_type == "flat":
            index = ANNEngine.build_flat(build_vectors, index_obj.metric_type)
            write_faiss(index, str(index_path))
        elif index_obj.index_type == "ivf_pq":
            index = ANNEngine.build_ivf_pq(build_vectors, index_obj.metric_type, params)
            write_faiss(index, str(index_path))
        elif index_obj.index_type == "hnsw":
            index = ANNEngine.build_hnsw(build_vectors, index_obj.metric_type, params)
            write_hnsw(index, str(index_path))
        elif index_obj.index_type == "hnsw_rerank":
            index = ANNEngine.build_hnsw(build_vectors, index_obj.metric_type, params)
            write_hnsw(index, str(index_path))
            # 精排向量：fp16 可节省 50% 内存，精排时回算 float32 距离
            use_fp16 = bool(params.get("use_fp16", True))
            rerank_dtype = np.float16 if use_fp16 else np.float32
            rerank_path = index_path.with_suffix(".rerank.npy")
            np.save(str(rerank_path), build_vectors.astype(rerank_dtype, copy=False))
        else:
            raise ValueError(f"unsupported index type: {index_obj.index_type}")

        build_seconds = round(time.perf_counter() - started, 4)
        ANNEngine.write_id_map(id_map_path, cell_ids, dataset_ids)
        ANNEngine.write_meta(
            meta_path,
            index_obj=index_obj,
            dim=dim,
            vector_count=vector_count,
            params=params,
            build_seconds=build_seconds,
            id_map_path=id_map_path,
        )

        return IndexBuildResult(
            index_path=str(index_path),
            id_map_path=str(id_map_path),
            meta_path=str(meta_path),
            dim=dim,
            vector_count=vector_count,
            build_seconds=build_seconds,
            memory_cost_mb=round(prepared.nbytes / 1024 / 1024, 4),
        )

    @staticmethod
    def prepare_matrix(vectors: np.ndarray) -> np.ndarray:
        arr = np.asarray(vectors, dtype=np.float32)
        if arr.ndim != 2:
            raise ValueError("vectors must be a 2D matrix")
        if arr.shape[0] == 0 or arr.shape[1] == 0:
            raise ValueError("vectors matrix must not be empty")
        if not np.isfinite(arr).all():
            raise ValueError("vectors contain NaN or infinity")
        return np.ascontiguousarray(arr)

    @staticmethod
    def prepare_vectors_for_index(vectors: np.ndarray, index_type: str, metric: str) -> np.ndarray:
        arr = ANNEngine.prepare_matrix(vectors).copy()
        if metric == "cosine" and index_type in {"flat", "ivf_pq"}:
            faiss.normalize_L2(arr)
        return arr

    @staticmethod
    def prepare_query(query: np.ndarray, index_type: str, metric: str) -> np.ndarray:
        arr = np.asarray(query, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.ndim != 2 or arr.shape[0] != 1:
            raise ValueError("query must be a single vector")
        arr = np.ascontiguousarray(arr)
        if metric == "cosine" and index_type in {"flat", "ivf_pq"}:
            arr = arr.copy()
            faiss.normalize_L2(arr)
        return arr

    @staticmethod
    def build_flat(vectors: np.ndarray, metric: str):
        dim = int(vectors.shape[1])
        index = faiss.IndexFlatIP(dim) if metric in {"ip", "cosine"} else faiss.IndexFlatL2(dim)
        index.add(vectors)
        return index

    @staticmethod
    def build_ivf_pq(vectors: np.ndarray, metric: str, params: dict[str, Any]):
        dim = int(vectors.shape[1])
        nlist = int(params.get("nlist", min(128, vectors.shape[0])))
        m = int(params.get("m", ANNEngine.default_pq_m(dim)))
        nbits = int(params.get("nbits", 8))
        nprobe = int(params.get("nprobe", min(16, nlist)))
        quantizer = faiss.IndexFlatIP(dim) if metric in {"ip", "cosine"} else faiss.IndexFlatL2(dim)
        if metric in {"ip", "cosine"}:
            index = faiss.IndexIVFPQ(quantizer, dim, nlist, m, nbits, faiss.METRIC_INNER_PRODUCT)
        else:
            index = faiss.IndexIVFPQ(quantizer, dim, nlist, m, nbits)
        index.train(vectors)
        index.add(vectors)
        index.nprobe = nprobe
        return index

    @staticmethod
    def build_hnsw(vectors: np.ndarray, metric: str, params: dict[str, Any]):
        dim = int(vectors.shape[1])
        index = hnswlib.Index(space=ANNEngine.hnsw_space(metric), dim=dim)
        index.init_index(
            max_elements=int(vectors.shape[0]),
            M=int(params.get("M", 16)),
            ef_construction=int(params.get("ef_construction", 200)),
        )
        index.add_items(vectors, np.arange(vectors.shape[0]))
        index.set_ef(int(params.get("ef", 64)))
        return index

    @staticmethod
    def load(index_obj: ANNIndex, dim: int | None = None):
        if index_obj.index_type in {"flat", "ivf_pq"}:
            return read_faiss(str(index_obj.file_path))
        if index_obj.index_type == "hnsw":
            if dim is None:
                dim = ANNEngine.read_meta_dim(index_obj)
            obj = load_hnsw(
                str(index_obj.file_path),
                space=ANNEngine.hnsw_space(index_obj.metric_type),
                dim=int(dim),
            )
            obj.set_ef(int((index_obj.params_json or {}).get("ef", 64)))
            return obj
        if index_obj.index_type == "hnsw_rerank":
            if dim is None:
                dim = ANNEngine.read_meta_dim(index_obj)
            hnsw_obj = load_hnsw(
                str(index_obj.file_path),
                space=ANNEngine.hnsw_space(index_obj.metric_type),
                dim=int(dim),
            )
            hnsw_obj.set_ef(int((index_obj.params_json or {}).get("ef", 64)))
            rerank_path = Path(index_obj.file_path).with_suffix(".rerank.npy")
            rerank_vectors = np.load(str(rerank_path)) if rerank_path.exists() else None
            return {"hnsw": hnsw_obj, "rerank_vectors": rerank_vectors}
        raise ValueError(f"unsupported index type: {index_obj.index_type}")

    @staticmethod
    def search(index_obj: ANNIndex, loaded_index, query: np.ndarray, top_k: int, params: dict | None = None):
        if top_k <= 0:
            return np.asarray([], dtype=np.float32), np.asarray([], dtype=np.int64)
        query_vec = ANNEngine.prepare_query(query, index_obj.index_type, index_obj.metric_type)
        if index_obj.index_type in {"flat", "ivf_pq"}:
            if index_obj.index_type == "ivf_pq" and params and params.get("nprobe"):
                loaded_index.nprobe = int(params["nprobe"])
            distances, indices = loaded_index.search(query_vec, int(top_k))
            return ANNEngine.canonical_distances(index_obj.metric_type, distances[0]), indices[0]
        if index_obj.index_type == "hnsw":
            if params and params.get("ef_search"):
                loaded_index.set_ef(int(params["ef_search"]))
            indices, distances = loaded_index.knn_query(query_vec, k=int(top_k))
            return distances[0], indices[0]
        if index_obj.index_type == "hnsw_rerank":
            return ANNEngine._search_hnsw_rerank(index_obj, loaded_index, query_vec, int(top_k), params or {})
        raise ValueError(f"unsupported index type: {index_obj.index_type}")

    @staticmethod
    def _search_hnsw_rerank(
        index_obj: ANNIndex,
        loaded_index: dict,
        query_vec: np.ndarray,
        top_k: int,
        params: dict,
    ) -> tuple[np.ndarray, np.ndarray]:
        hnsw_obj = loaded_index["hnsw"]
        rerank_vectors: np.ndarray | None = loaded_index.get("rerank_vectors")
        index_params = dict(index_obj.params_json or {})
        rerank_factor = int(params.get("rerank_factor") or index_params.get("rerank_factor") or DEFAULT_RERANK_FACTOR)
        ef_search = int(params.get("ef_search") or index_params.get("ef", 64))
        hnsw_obj.set_ef(max(ef_search, top_k * rerank_factor))

        total_elements = int(hnsw_obj.get_current_count())
        fetch_k = min(total_elements, max(top_k * rerank_factor, MIN_RERANK_FETCH, top_k))
        cand_indices, cand_distances = hnsw_obj.knn_query(query_vec, k=fetch_k)
        cand_indices = cand_indices[0]
        cand_distances = cand_distances[0]
        if rerank_vectors is None or len(cand_indices) <= top_k:
            return cand_distances[:top_k], cand_indices[:top_k]

        # 精排：在小候选集合内用 float32 重新计算精确距离
        sub = rerank_vectors[cand_indices].astype(np.float32, copy=False)
        metric = index_obj.metric_type
        q = query_vec.reshape(-1).astype(np.float32, copy=False)
        if metric == "cosine":
            sub_norm = sub / np.maximum(np.linalg.norm(sub, axis=1, keepdims=True), 1e-12)
            q_norm = q / max(float(np.linalg.norm(q)), 1e-12)
            exact = 1.0 - np.dot(sub_norm, q_norm)
        elif metric == "ip":
            exact = -np.dot(sub, q)
        else:
            diff = sub - q
            exact = np.einsum("ij,ij->i", diff, diff)
        order = np.argsort(exact)[:top_k]
        return exact[order].astype(np.float32), cand_indices[order].astype(np.int64)

    @staticmethod
    def exact_search(vectors: np.ndarray, query: np.ndarray, metric: str, top_k: int):
        matrix = ANNEngine.prepare_matrix(vectors)
        query_vec = np.asarray(query, dtype=np.float32).reshape(1, -1)
        if metric == "cosine":
            matrix_norm = matrix / np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)
            query_norm = query_vec / max(float(np.linalg.norm(query_vec)), 1e-12)
            distances = 1.0 - np.dot(matrix_norm, query_norm.reshape(-1))
        elif metric == "ip":
            distances = -np.dot(matrix, query_vec.reshape(-1))
        else:
            diff = matrix - query_vec
            distances = np.sum(diff * diff, axis=1)
        indices = np.argsort(distances)[:top_k]
        return distances[indices].astype(np.float32), indices.astype(np.int64)

    @staticmethod
    def canonical_distances(metric: str, distances: np.ndarray) -> np.ndarray:
        if metric == "ip":
            return -distances
        if metric == "cosine":
            return 1.0 - distances
        return distances

    @staticmethod
    def hnsw_space(metric: str) -> str:
        if metric in {"l2", "ip", "cosine"}:
            return metric
        raise ValueError(f"unsupported metric type: {metric}")

    @staticmethod
    def id_map_path(index_obj: ANNIndex) -> Path:
        return Path(index_obj.file_path).with_suffix(".id_map.json")

    @staticmethod
    def meta_path(index_obj: ANNIndex) -> Path:
        return Path(index_obj.file_path).with_suffix(".meta.json")

    @staticmethod
    def write_id_map(path: Path, cell_ids: list[str], dataset_ids: list[int] | None = None) -> None:
        if dataset_ids is not None:
            data = [
                {"position": i, "cell_id": cell_id, "dataset_id": int(dataset_ids[i])}
                for i, cell_id in enumerate(cell_ids)
            ]
        else:
            data = [{"position": i, "cell_id": cell_id} for i, cell_id in enumerate(cell_ids)]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def read_id_map(index_obj: ANNIndex) -> list[str]:
        path = ANNEngine.id_map_path(index_obj)
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return [item["cell_id"] for item in sorted(data, key=lambda item: int(item["position"]))]

    @staticmethod
    def read_id_map_entries(index_obj: ANNIndex) -> list[dict]:
        """同时返回 cell_id 与可选的 dataset_id（用于多数据集联合索引）。"""
        path = ANNEngine.id_map_path(index_obj)
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return [
            {
                "position": int(item["position"]),
                "cell_id": item["cell_id"],
                "dataset_id": int(item["dataset_id"]) if item.get("dataset_id") is not None else None,
            }
            for item in sorted(data, key=lambda item: int(item["position"]))
        ]

    @staticmethod
    def write_meta(
        path: Path,
        index_obj: ANNIndex,
        dim: int,
        vector_count: int,
        params: dict[str, Any],
        build_seconds: float,
        id_map_path: Path,
    ) -> None:
        meta = {
            "index_id": index_obj.id,
            "dataset_id": index_obj.dataset_id,
            "dataset_ids": list(getattr(index_obj, "dataset_ids", None) or [index_obj.dataset_id]),
            "index_name": index_obj.index_name,
            "index_type": index_obj.index_type,
            "metric_type": index_obj.metric_type,
            "dim": dim,
            "vector_count": vector_count,
            "params_json": params,
            "file_path": index_obj.file_path,
            "id_map_path": str(id_map_path),
            "build_seconds": build_seconds,
            "created_at": utcnow_iso(),
        }
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def read_meta_dim(index_obj: ANNIndex) -> int:
        path = ANNEngine.meta_path(index_obj)
        if not path.exists():
            raise ValueError("index meta file missing")
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data["dim"])
