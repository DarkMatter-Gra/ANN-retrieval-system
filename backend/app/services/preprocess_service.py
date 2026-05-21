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


def load_input_dataset(file_path: str, file_format: str):
    if file_format == "h5ad":
        return sc.read_h5ad(file_path)
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
    dataset = db.query(ExpressionMetadata).filter(ExpressionMetadata.id == dataset_id).first()
    if not task or not dataset:
        raise ValueError("task or dataset not found")

    task.status = "running"
    task.progress = 5
    task.started_at = utcnow_iso()
    dataset.preprocess_status = "running"
    db.commit()

    adata = load_input_dataset(dataset.source_file_path, dataset.file_format)
    task.progress = 20
    db.commit()

    sc.pp.calculate_qc_metrics(adata, inplace=True)
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    n_top = min(2000, max(int(adata.shape[1] * 0.5), 50))
    sc.pp.highly_variable_genes(adata, n_top_genes=n_top, subset=True)
    n_comps = min(50, max(int(min(adata.shape) - 1), 2))
    sc.pp.pca(adata, n_comps=n_comps)
    sc.pp.neighbors(adata)
    sc.tl.umap(adata)
    task.progress = 60
    db.commit()

    vectors = np.asarray(adata.obsm["X_pca"], dtype=np.float32)
    dataset.cell_count = int(adata.n_obs)
    dataset.gene_count = int(adata.n_vars)
    dataset.feature_dim = int(vectors.shape[1])
    dataset.qc_status = "passed"
    dataset.embedding_methods = ["pca", "umap"]

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
                cell_type=str(row["cell_type"]) if "cell_type" in obs_columns else None,
                organ=str(row["organ"]) if "organ" in obs_columns else None,
                sample_id=str(row["sample_id"]) if "sample_id" in obs_columns else None,
                obs_ext={k: _serialize_value(row[k]) for k in obs_columns},
                qc_flags={},
            )
        )

    output_dir = Path(settings.data_path) / "processed" / str(dataset.id)
    output_dir.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(output_dir / "processed.h5ad")
    pd.DataFrame(
        adata.obsm["X_umap"], columns=["umap_x", "umap_y"], index=adata.obs_names
    ).to_csv(output_dir / "umap.csv")

    dataset.preprocess_status = "done"
    task.status = "done"
    task.progress = 100
    task.finished_at = utcnow_iso()
    db.commit()


def _serialize_value(value):
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    try:
        return value.item()
    except AttributeError:
        return str(value)
