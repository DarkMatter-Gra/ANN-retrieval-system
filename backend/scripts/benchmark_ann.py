"""Benchmark ANN search quality and latency on vectors stored in the backend DB.

Run from backend/:
    python scripts/benchmark_ann.py --dataset-id 1 --queries 200 --top-k 10
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import hnswlib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.cell_vector import CellVector
from app.models.dataset import ExpressionMetadata
from app.utils.file_store import ensure_dir
from app.utils.vector_codec import stack_vectors


HNSW_CONFIGS = [
    {
        "name": "hnsw_fast",
        "params": {"M": 8, "ef_construction": 80},
        "ef_search_values": [16, 32, 64],
    },
    {
        "name": "hnsw_balanced",
        "params": {"M": 16, "ef_construction": 120},
        "ef_search_values": [32, 64, 128],
    },
    {
        "name": "hnsw_quality",
        "params": {"M": 32, "ef_construction": 200},
        "ef_search_values": [64, 128, 256],
    },
]

# hnsw_rerank：HNSW 召回 + float32 精排。rerank_factor 控制候选放大倍数。
HNSW_RERANK_CONFIGS = [
    {
        "name": "hnsw_rerank_fp32",
        "params": {"M": 16, "ef_construction": 120},
        "ef_search_values": [32, 64],
        "rerank_factors": [2, 4, 8],
        "use_fp16": False,
    },
    {
        "name": "hnsw_rerank_fp16",
        "params": {"M": 16, "ef_construction": 120},
        "ef_search_values": [32, 64],
        "rerank_factors": [4, 8],
        "use_fp16": True,
    },
]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    arr = sorted(values)
    idx = min(len(arr) - 1, max(0, int(round((len(arr) - 1) * p))))
    return round(arr[idx], 4)


def load_dataset(dataset_id: int) -> tuple[ExpressionMetadata, np.ndarray, list[str]]:
    db = SessionLocal()
    try:
        dataset = db.query(ExpressionMetadata).filter(ExpressionMetadata.id == dataset_id).first()
        if not dataset:
            raise ValueError(f"dataset {dataset_id} not found")
        rows = (
            db.query(CellVector)
            .filter(CellVector.dataset_id == dataset_id, CellVector.vector_type == "pca")
            .order_by(CellVector.id.asc())
            .all()
        )
        if not rows:
            raise ValueError(f"dataset {dataset_id} has no PCA vectors")
        matrix = stack_vectors([row.vector_blob for row in rows])
        cell_ids = [row.cell_id for row in rows]
        return dataset, np.ascontiguousarray(matrix, dtype=np.float32), cell_ids
    finally:
        db.close()


def choose_queries(total: int, query_count: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    size = min(int(query_count), int(total))
    return np.sort(rng.choice(total, size=size, replace=False))


def exact_l2(matrix: np.ndarray, queries: np.ndarray, top_k: int) -> tuple[list[list[int]], dict]:
    result_indices: list[list[int]] = []
    latencies: list[float] = []
    k = min(int(top_k), int(matrix.shape[0]))
    for query in queries:
        started = time.perf_counter()
        diff = matrix - query.reshape(1, -1)
        distances = np.einsum("ij,ij->i", diff, diff)
        candidate_idx = np.argpartition(distances, kth=k - 1)[:k]
        ordered = candidate_idx[np.argsort(distances[candidate_idx])]
        latencies.append((time.perf_counter() - started) * 1000)
        result_indices.append([int(i) for i in ordered])
    return result_indices, summarize_latencies(latencies)


def build_hnsw(matrix: np.ndarray, params: dict) -> tuple[hnswlib.Index, float]:
    index = hnswlib.Index(space="l2", dim=int(matrix.shape[1]))
    started = time.perf_counter()
    index.init_index(
        max_elements=int(matrix.shape[0]),
        M=int(params["M"]),
        ef_construction=int(params["ef_construction"]),
    )
    index.add_items(matrix, np.arange(matrix.shape[0]))
    return index, round(time.perf_counter() - started, 4)


def query_hnsw(index: hnswlib.Index, queries: np.ndarray, top_k: int, ef_search: int) -> tuple[list[list[int]], dict]:
    index.set_ef(int(ef_search))
    result_indices: list[list[int]] = []
    latencies: list[float] = []
    for query in queries:
        started = time.perf_counter()
        labels, _distances = index.knn_query(query.reshape(1, -1), k=int(top_k))
        latencies.append((time.perf_counter() - started) * 1000)
        result_indices.append([int(i) for i in labels[0]])
    return result_indices, summarize_latencies(latencies)


def query_hnsw_rerank(
    index: hnswlib.Index,
    rerank_vectors: np.ndarray,
    queries: np.ndarray,
    top_k: int,
    ef_search: int,
    rerank_factor: int,
) -> tuple[list[list[int]], dict]:
    """HNSW 召回 top_k * rerank_factor 个候选后，用 float32 重排，模拟 ann_engine.hnsw_rerank。"""
    fetch_k = max(top_k * int(rerank_factor), top_k)
    fetch_k = min(fetch_k, int(rerank_vectors.shape[0]))
    index.set_ef(max(int(ef_search), fetch_k))
    result_indices: list[list[int]] = []
    latencies: list[float] = []
    for query in queries:
        started = time.perf_counter()
        cand_labels, _ = index.knn_query(query.reshape(1, -1), k=fetch_k)
        cand = cand_labels[0]
        sub = rerank_vectors[cand].astype(np.float32, copy=False)
        diff = sub - query.reshape(1, -1)
        exact = np.einsum("ij,ij->i", diff, diff)
        order = np.argsort(exact)[:top_k]
        latencies.append((time.perf_counter() - started) * 1000)
        result_indices.append([int(cand[i]) for i in order])
    return result_indices, summarize_latencies(latencies)


def rerank_memory_mb(matrix: np.ndarray, use_fp16: bool) -> float:
    nbytes = matrix.shape[0] * matrix.shape[1] * (2 if use_fp16 else 4)
    return round(nbytes / 1024 / 1024, 4)


def summarize_latencies(values: list[float]) -> dict:
    if not values:
        return {"avg_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}
    return {
        "avg_ms": round(statistics.fmean(values), 4),
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "p99_ms": percentile(values, 0.99),
    }


def recall_at_k(exact: list[list[int]], approx: list[list[int]], top_k: int) -> float:
    if not exact:
        return 0.0
    total = 0.0
    for exact_row, approx_row in zip(exact, approx):
        exact_set = set(exact_row[:top_k])
        approx_set = set(approx_row[:top_k])
        total += len(exact_set & approx_set) / max(1, min(top_k, len(exact_set)))
    return round(total / len(exact), 4)


def run_benchmark(dataset_id: int, query_count: int, top_k: int, seed: int) -> dict:
    dataset, matrix, _cell_ids = load_dataset(dataset_id)
    query_indices = choose_queries(matrix.shape[0], query_count, seed)
    queries = matrix[query_indices]

    exact_results, exact_latency = exact_l2(matrix, queries, top_k)
    records = [
        {
            "name": "flat_exact",
            "index_type": "flat",
            "params": {},
            "build_seconds": 0.0,
            "ef_search": None,
            "rerank_factor": None,
            "use_fp16": None,
            "memory_mb": round(matrix.nbytes / 1024 / 1024, 4),
            "recall_at_k": 1.0,
            **exact_latency,
        }
    ]

    for config in HNSW_CONFIGS:
        index, build_seconds = build_hnsw(matrix, config["params"])
        for ef_search in config["ef_search_values"]:
            hnsw_results, latency = query_hnsw(index, queries, top_k, ef_search)
            records.append(
                {
                    "name": config["name"],
                    "index_type": "hnsw",
                    "params": config["params"],
                    "build_seconds": build_seconds,
                    "ef_search": ef_search,
                    "rerank_factor": None,
                    "use_fp16": None,
                    "memory_mb": 0.0,
                    "recall_at_k": recall_at_k(exact_results, hnsw_results, top_k),
                    **latency,
                }
            )

    # hnsw_rerank：HNSW 召回 + 精排向量重排；可选 fp16 节省内存
    for cfg in HNSW_RERANK_CONFIGS:
        index, build_seconds = build_hnsw(matrix, cfg["params"])
        rerank_dtype = np.float16 if cfg["use_fp16"] else np.float32
        rerank_vectors = matrix.astype(rerank_dtype, copy=False)
        mem_mb = rerank_memory_mb(matrix, cfg["use_fp16"])
        for ef_search in cfg["ef_search_values"]:
            for rf in cfg["rerank_factors"]:
                results_idx, latency = query_hnsw_rerank(index, rerank_vectors, queries, top_k, ef_search, rf)
                records.append(
                    {
                        "name": cfg["name"],
                        "index_type": "hnsw_rerank",
                        "params": cfg["params"],
                        "build_seconds": build_seconds,
                        "ef_search": ef_search,
                        "rerank_factor": rf,
                        "use_fp16": cfg["use_fp16"],
                        "memory_mb": mem_mb,
                        "recall_at_k": recall_at_k(exact_results, results_idx, top_k),
                        **latency,
                    }
                )

    best = max(
        [item for item in records if item["index_type"] != "flat"],
        key=lambda item: (item["recall_at_k"], -item["p95_ms"]),
    )
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": {
            "id": dataset.id,
            "name": dataset.dataset_name,
            "cell_count": dataset.cell_count,
            "gene_count": dataset.gene_count,
            "feature_dim": dataset.feature_dim,
        },
        "benchmark": {
            "metric": "l2",
            "top_k": top_k,
            "query_count": int(len(query_indices)),
            "seed": seed,
        },
        "records": records,
        "recommendation": {
            "name": best["name"],
            "index_type": best.get("index_type"),
            "params": best["params"],
            "ef_search": best["ef_search"],
            "rerank_factor": best.get("rerank_factor"),
            "use_fp16": best.get("use_fp16"),
            "memory_mb": best.get("memory_mb"),
            "recall_at_k": best["recall_at_k"],
            "p95_ms": best["p95_ms"],
            "reason": "highest recall@k, then lower p95 latency",
        },
    }


def write_outputs(result: dict) -> tuple[Path, Path]:
    report_dir = ensure_dir(settings.report_path)
    dataset_id = result["dataset"]["id"]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = report_dir / f"ann_benchmark_{dataset_id}_{stamp}.json"
    md_path = report_dir / f"ann_benchmark_{dataset_id}_{stamp}.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(result), encoding="utf-8")
    return json_path, md_path


def render_markdown(result: dict) -> str:
    dataset = result["dataset"]
    benchmark = result["benchmark"]
    lines = [
        "# ANN Benchmark Report",
        "",
        f"- Generated at: {result['generated_at']}",
        f"- Dataset: {dataset['name']} (id={dataset['id']})",
        f"- Cells: {dataset['cell_count']}",
        f"- Genes: {dataset['gene_count']}",
        f"- Feature dimension: {dataset['feature_dim']}",
        f"- Metric: {benchmark['metric']}",
        f"- Top-K: {benchmark['top_k']}",
        f"- Query count: {benchmark['query_count']}",
        "",
        "| Name | Type | Params | ef_search | rerank | fp16 | Mem(MB) | Build(s) | Recall@K | Avg(ms) | P50(ms) | P95(ms) | P99(ms) |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in result["records"]:
        lines.append(
            "| {name} | {itype} | `{params}` | {ef} | {rf} | {fp16} | {mem:.4f} | {build:.4f} | {recall:.4f} | {avg:.4f} | {p50:.4f} | {p95:.4f} | {p99:.4f} |".format(
                name=item["name"],
                itype=item.get("index_type", "-"),
                params=json.dumps(item["params"], ensure_ascii=False),
                ef=item["ef_search"] if item["ef_search"] is not None else "-",
                rf=item.get("rerank_factor") if item.get("rerank_factor") is not None else "-",
                fp16="Y" if item.get("use_fp16") else ("N" if item.get("use_fp16") is False else "-"),
                mem=float(item.get("memory_mb", 0.0)),
                build=float(item["build_seconds"]),
                recall=float(item["recall_at_k"]),
                avg=float(item["avg_ms"]),
                p50=float(item["p50_ms"]),
                p95=float(item["p95_ms"]),
                p99=float(item["p99_ms"]),
            )
        )
    rec = result["recommendation"]
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"Use `{rec['name']}` with params `{json.dumps(rec['params'], ensure_ascii=False)}` and `ef_search={rec['ef_search']}`.",
            f"This run reached recall@K={rec['recall_at_k']:.4f}, p95={rec['p95_ms']:.4f} ms.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-id", type=int, default=1)
    parser.add_argument("--queries", type=int, default=200)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = run_benchmark(args.dataset_id, args.queries, args.top_k, args.seed)
    json_path, md_path = write_outputs(result)
    print(json.dumps({"status": "ok", "json_path": str(json_path), "md_path": str(md_path), "recommendation": result["recommendation"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
