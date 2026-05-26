"""预处理流水线（同步函数版本，供 Celery Task 调用）。"""

from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
from scipy.io import mmread
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cell_metadata import CellMetadata
from app.models.cell_vector import CellVector
from app.models.dataset import ExpressionMetadata
from app.models.search_task import SearchTask
from app.utils.time import utcnow_iso
from app.utils.vector_codec import encode_vector


def load_input_dataset(file_path: str, file_format: str, max_cells: int = 30_000):
    if file_format == "h5ad":
        # Use backed mode to avoid loading the full matrix into RAM upfront
        adata = sc.read_h5ad(file_path, backed="r")
        if adata.n_obs > max_cells:
            rng = np.random.default_rng(42)
            idx = np.sort(rng.choice(adata.n_obs, max_cells, replace=False))
            adata = adata[idx].to_memory()
        else:
            adata = adata.to_memory()
        return adata
    if file_format == "csv":
        df = pd.read_csv(file_path, index_col=0)
        return ad.AnnData(
            df.values,
            obs=pd.DataFrame(index=df.index),
            var=pd.DataFrame(index=df.columns),
        )
    if file_format == "mtx":
        matrix = mmread(file_path).tocsr()
        return ad.AnnData(matrix)
    raise ValueError(f"unsupported file format: {file_format}")


def run_preprocess(db: Session, task_id: str, dataset_id: int) -> None:
    task = db.query(SearchTask).filter(SearchTask.task_id == task_id).first()
    dataset = (
        db.query(ExpressionMetadata).filter(ExpressionMetadata.id == dataset_id).first()
    )
    if not task or not dataset:
        raise ValueError("task or dataset not found")

    task.status = "running"
    task.progress = 5
    task.started_at = utcnow_iso()
    dataset.preprocess_status = "running"
    db.commit()

    adata = load_input_dataset(dataset.source_file_path, dataset.file_format)
    _validate_adata(adata)
    task.progress = 20
    db.commit()

    # sc.pp.calculate_qc_metrics(adata, inplace=True)
    # sc.pp.normalize_total(adata, target_sum=1e4)
    # sc.pp.log1p(adata)
    # n_top = min(2000, max(int(adata.shape[1] * 0.5), 50))
    # sc.pp.highly_variable_genes(adata, n_top_genes=n_top, subset=True)
    # n_comps = min(50, max(int(min(adata.shape) - 1), 2))
    # sc.pp.pca(adata, n_comps=n_comps)
    # sc.pp.neighbors(adata)
    # sc.tl.umap(adata)
    # task.progress = 60
    # db.commit()

    # vectors = np.asarray(adata.obsm["X_pca"], dtype=np.float32)

    # - 如果 adata.obsm 里已经有 X_pca 直接拿来当 vectors
    # - 如果没有，才重新做归一化、log、HVG、PCA
    if "X_pca" in adata.obsm:
        vectors = np.asarray(adata.obsm["X_pca"], dtype=np.float32)
    else:
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)
        n_top = min(2000, max(int(adata.shape[1] * 0.5), 50))
        sc.pp.highly_variable_genes(adata, n_top_genes=n_top, subset=True)
        n_comps = min(50, max(int(min(adata.shape) - 1), 2))
        sc.pp.pca(adata, n_comps=n_comps)
        vectors = np.asarray(adata.obsm["X_pca"], dtype=np.float32)

    if "X_umap" not in adata.obsm:
        if "X_pca" in adata.obsm:
            sc.pp.neighbors(adata, use_rep="X_pca")
        else:
            sc.pp.neighbors(adata)
        sc.tl.umap(adata)

    task.progress = 60
    db.commit()

    dataset.cell_count = int(adata.n_obs)
    dataset.gene_count = int(adata.n_vars)
    dataset.feature_dim = int(vectors.shape[1])
    dataset.qc_status = "passed"
    dataset.embedding_methods = _collect_embedding_methods(adata)

    # 重新写入向量表与 cell_metadata
    db.query(CellVector).filter(CellVector.dataset_id == dataset.id).delete()
    db.query(CellMetadata).filter(CellMetadata.dataset_id == dataset.id).delete()

    obs_columns = list(adata.obs.columns)
    for idx, cell_name in enumerate(adata.obs_names.tolist()):
        vec = vectors[idx]
        db.add(
            CellVector(
                dataset_id=dataset.id,
                cell_id=str(cell_name),
                vector_type="pca",
                dim=int(vec.shape[0]),
                vector_blob=encode_vector(vec),
                norm_value=float(np.linalg.norm(vec) or 1.0),
            )
        )
        row = adata.obs.iloc[idx]
        db.add(
            CellMetadata(
                dataset_id=dataset.id,
                cell_id=str(cell_name),
                # cell_type=str(row["cell_type"]) if "cell_type" in obs_columns else None,
                # organ=str(row["organ"]) if "organ" in obs_columns else None,
                # sample_id=str(row["sample_id"]) if "sample_id" in obs_columns else None,
                cell_type=_pick_obs_value(row, "cell_type"),
                organ=_pick_obs_value(row, "organ") or _pick_obs_value(row, "tissue"),
                sample_id=_pick_obs_value(row, "sample_id"),
                obs_ext={k: _serialize_value(row[k]) for k in obs_columns},
                qc_flags={},
            )
        )

    output_dir = Path(settings.data_path) / "processed" / str(dataset.id)
    output_dir.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(output_dir / "processed.h5ad")
    # pd.DataFrame(
    #     adata.obsm["X_umap"], columns=["umap_x", "umap_y"], index=adata.obs_names
    # ).to_csv(output_dir / "umap.csv")
    if "X_umap" in adata.obsm:
        _write_embedding_csv(
            output_dir / "umap.csv", adata.obs_names, adata.obsm["X_umap"], "umap"
        )

    if "X_tsne" in adata.obsm:
        _write_embedding_csv(
            output_dir / "tsne.csv", adata.obs_names, adata.obsm["X_tsne"], "tsne"
        )

    dataset.preprocess_status = "done"
    task.status = "done"
    task.progress = 100
    task.finished_at = utcnow_iso()
    db.commit()


# 数据合法性检查
def _validate_adata(adata) -> None:
    if adata.n_obs == 0:
        raise ValueError("dataset has no cells")
    if adata.n_vars == 0:
        raise ValueError("dataset has no genes")
    if adata.obs_names is None or len(adata.obs_names) == 0:
        raise ValueError("obs_names is empty")
    if adata.obs_names.has_duplicates:
        raise ValueError("duplicate cell ids in obs_names")


def _serialize_value(value):
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    try:
        return value.item()
    except AttributeError:
        return str(value)


def _collect_embedding_methods(adata) -> list[str]:
    methods = []
    if "X_pca" in adata.obsm:
        methods.append("pca")
    if "X_umap" in adata.obsm:
        methods.append("umap")
    if "X_tsne" in adata.obsm:
        methods.append("tsne")
    return methods


def _pick_obs_value(row, key: str):
    if key not in row.index:
        return None
    value = row[key]
    if pd.isna(value):
        return None
    return str(value)


# 将二维 embedding 统一导出成csv
def _write_embedding_csv(file_path: Path, index, matrix, prefix: str) -> None:
    arr = np.asarray(matrix)
    if arr.shape[1] < 2:
        raise ValueError("embedding matrix must have at least 2 columns")
    pd.DataFrame(
        arr[:, :2],
        columns=[f"{prefix}_x", f"{prefix}_y"],
        index=index,
    ).to_csv(file_path)
