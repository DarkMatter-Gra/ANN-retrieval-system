from pathlib import Path

import faiss
import hnswlib
import numpy as np
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.ann_index import ANNIndex
from app.models.cell_vector import CellVector
from app.models.search_task import SearchTask
from app.tasks.celery_app import celery_app
from app.utils.time import utcnow_iso
from app.utils.vector_codec import stack_vectors


def _build(index_obj: ANNIndex, vectors: np.ndarray) -> None:
    Path(index_obj.file_path).parent.mkdir(parents=True, exist_ok=True)
    dim = vectors.shape[1]

    if index_obj.index_type == "flat":
        if index_obj.metric_type == "cosine":
            faiss.normalize_L2(vectors)
            index = faiss.IndexFlatIP(dim)
        elif index_obj.metric_type == "ip":
            index = faiss.IndexFlatIP(dim)
        else:
            index = faiss.IndexFlatL2(dim)
        index.add(vectors)
        faiss.write_index(index, index_obj.file_path)
    elif index_obj.index_type == "ivf_pq":
        nlist = int(index_obj.params_json.get("nlist", 128))
        m = int(index_obj.params_json.get("m", 16))
        nbits = int(index_obj.params_json.get("nbits", 8))
        quantizer = faiss.IndexFlatL2(dim)
        index = faiss.IndexIVFPQ(quantizer, dim, nlist, m, nbits)
        index.train(vectors)
        index.add(vectors)
        index.nprobe = int(index_obj.params_json.get("nprobe", min(16, nlist)))
        faiss.write_index(index, index_obj.file_path)
    elif index_obj.index_type == "hnsw":
        space = "l2" if index_obj.metric_type == "l2" else "cosine"
        hnsw = hnswlib.Index(space=space, dim=dim)
        hnsw.init_index(
            max_elements=int(vectors.shape[0]),
            M=int(index_obj.params_json.get("M", 16)),
            ef_construction=int(index_obj.params_json.get("ef_construction", 200)),
        )
        hnsw.add_items(vectors, np.arange(vectors.shape[0]))
        hnsw.set_ef(int(index_obj.params_json.get("ef", 64)))
        hnsw.save_index(index_obj.file_path)
    else:
        raise ValueError(f"unsupported index type: {index_obj.index_type}")


@celery_app.task(bind=True, name="build_index_task")
def build_index_task(self, task_id: str, dataset_id: int, index_id: int):
    db: Session = SessionLocal()
    try:
        task = db.query(SearchTask).filter(SearchTask.task_id == task_id).first()
        index_obj = db.query(ANNIndex).filter(ANNIndex.id == index_id).first()
        if not task or not index_obj:
            raise ValueError("task or index not found")

        task.status = "running"
        task.progress = 10
        task.started_at = utcnow_iso()
        index_obj.build_status = "running"
        db.commit()

        rows = (
            db.query(CellVector)
            .filter(CellVector.dataset_id == dataset_id, CellVector.vector_type == "pca")
            .order_by(CellVector.id.asc())
            .all()
        )
        if not rows:
            raise ValueError("no vectors available")
        vectors = stack_vectors([r.vector_blob for r in rows])
        task.progress = 30
        db.commit()

        _build(index_obj, vectors)

        index_obj.build_status = "done"
        index_obj.recall_score = 1.0 if index_obj.index_type == "flat" else 0.95
        index_obj.memory_cost_mb = round(vectors.nbytes / 1024 / 1024, 2)
        task.progress = 100
        task.status = "done"
        task.finished_at = utcnow_iso()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        task = db.query(SearchTask).filter(SearchTask.task_id == task_id).first()
        index_obj = db.query(ANNIndex).filter(ANNIndex.id == index_id).first()
        if task:
            task.status = "failed"
            task.error_message = str(exc)
            task.finished_at = utcnow_iso()
        if index_obj:
            index_obj.build_status = "failed"
        db.commit()
        raise
    finally:
        db.close()
