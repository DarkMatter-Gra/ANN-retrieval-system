import json
import uuid
import math
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    DatasetNotFoundError,
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
from app.utils.audit import write_audit
from app.utils.file_store import ensure_dir, merge_chunks, remove_dir


SUPPORTED_FORMATS = {"h5ad", "mtx", "csv"}


class DatasetService:
    def __init__(self, db: Session):
        self.db = db
        self.upload_root = ensure_dir(settings.data_path / "raw" / "uploads")

    # ----------------------------- 上传链路 -----------------------------
    def init_upload(self, user_id: int, filename: str, size: int, fmt: str) -> tuple[str, int]:
        if fmt not in SUPPORTED_FORMATS:
            raise ValidationFailed("unsupported file format")
        upload_id = uuid.uuid4().hex
        session_dir = self.upload_root / str(user_id) / upload_id
        ensure_dir(session_dir)
        meta = {
            "filename": filename,
            "size": size,
            "format": fmt,
            "chunk_size": settings.upload_chunk_size,
            "expected_chunks": math.ceil(size / settings.upload_chunk_size),
            "received_chunks": [],
        }
        (session_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        return upload_id, settings.upload_chunk_size

    async def save_chunk(
        self, user_id: int, upload_id: str, chunk_index: int, chunk_file: UploadFile
    ) -> int:
        session_dir = self.upload_root / str(user_id) / upload_id
        if not session_dir.exists():
            raise DatasetNotFoundError("upload session not found")
        
        meta_path = session_dir / "meta.json"
        if not meta_path.exists():
            raise DatasetNotFoundError("upload session not found")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        chunk_path = session_dir / f"chunk_{chunk_index:06d}.part"
        with chunk_path.open("wb") as f:
            while content := await chunk_file.read(1024 * 1024):
                f.write(content)
    # 去重
        received_chunks = set(meta.get("received_chunks", []))
        received_chunks.add(chunk_index)
        meta["received_chunks"] = sorted(received_chunks)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

        return chunk_index + 1

    def complete_upload(self, user_id: int, upload_id: str) -> dict:
        from app.tasks.preprocess_tasks import preprocess_dataset_task

        session_dir = self.upload_root / str(user_id) / upload_id
        meta_path = session_dir / "meta.json"
        if not meta_path.exists():
            raise DatasetNotFoundError("upload session not found")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

        expected_chunks = int(meta.get("expected_chunks", 0))
        received_chunks = meta.get("received_chunks", [])

        if expected_chunks <= 0:
            raise ValidationFailed("invalid expected chunk count")

        missing_chunks = [i for i in range(expected_chunks) if i not in received_chunks]
        if missing_chunks:
            raise ValidationFailed(f"missing chunks: {missing_chunks}")

        merged_path = session_dir / meta["filename"]
        chunk_files = sorted(session_dir.glob("chunk_*.part"))
        if not chunk_files:
            raise ValidationFailed("no chunks uploaded")
        merge_chunks(chunk_files, merged_path)

        dataset = ExpressionMetadata(
            dataset_name=Path(meta["filename"]).stem,
            file_format=meta["format"],
            source_file_path=str(merged_path),
            owner_user_id=user_id,
            qc_status="pending",
            preprocess_status="pending",
            embedding_methods=[],
        )
        self.db.add(dataset)
        self.db.commit()
        self.db.refresh(dataset)

        task = SearchTask(
            task_id=uuid.uuid4().hex,
            owner_user_id=user_id,
            task_type="preprocess_dataset",
            dataset_id=dataset.id,
            status="pending",
            progress=0,
            request_payload={"dataset_id": dataset.id},
        )
        self.db.add(task)
        self.db.commit()

        write_audit(user_id, "upload_dataset", "dataset", str(dataset.id), {"format": meta["format"]})
        preprocess_dataset_task.delay(task.task_id, dataset.id, user_id)
        return {"dataset_id": dataset.id, "task_id": task.task_id, "status": "pending"}

    # ----------------------------- 查询/删除 -----------------------------
    def list_datasets(
        self,
        current_user: User,
        page: int,
        page_size: int,
        keyword: str | None = None,
    ) -> dict:
        query = self.db.query(ExpressionMetadata).filter(ExpressionMetadata.deleted_flag.is_(False))
        if current_user.role != "admin":
            query = query.filter(ExpressionMetadata.owner_user_id == current_user.id)
        if keyword:
            query = query.filter(ExpressionMetadata.dataset_name.ilike(f"%{keyword}%"))
        total = query.count()
        rows = (
            query.order_by(ExpressionMetadata.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = [
            {
                "dataset_id": r.id,
                "dataset_name": r.dataset_name,
                "file_format": r.file_format,
                "cell_count": r.cell_count,
                "gene_count": r.gene_count,
                "feature_dim": r.feature_dim,
                "qc_status": r.qc_status,
                "preprocess_status": r.preprocess_status,
                "embedding_methods": r.embedding_methods,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
        return {"list": items, "total": total}

    def _check_owner(self, dataset: ExpressionMetadata, current_user: User) -> None:
        if current_user.role == "admin":
            return
        if dataset.owner_user_id != current_user.id:
            raise ResourceForbiddenError()

    def get_detail(self, dataset_id: int, current_user: User) -> dict:
        dataset = self.db.query(ExpressionMetadata).filter(ExpressionMetadata.id == dataset_id).first()
        if not dataset or dataset.deleted_flag:
            raise DatasetNotFoundError()
        self._check_owner(dataset, current_user)
        return {
            "dataset_info": {
                "dataset_id": dataset.id,
                "dataset_name": dataset.dataset_name,
                "file_format": dataset.file_format,
                "cell_count": dataset.cell_count,
                "gene_count": dataset.gene_count,
                "feature_dim": dataset.feature_dim,
                "embedding_methods": dataset.embedding_methods,
                "owner_user_id": dataset.owner_user_id,
            },
            "qc_report": {
                "cells_before": getattr(dataset, "cells_before", None),
                "cells_after": dataset.cell_count,
                "mt_ratio_threshold": getattr(dataset, "mt_ratio_threshold", None),
                "doublet_removed": getattr(dataset, "doublet_removed", None),
            },
            "qc_status": dataset.qc_status,
            "preprocess_status": dataset.preprocess_status,
        }

    def delete_dataset(self, dataset_id: int, current_user: User) -> dict:
        dataset = self.db.query(ExpressionMetadata).filter(ExpressionMetadata.id == dataset_id).first()
        if not dataset or dataset.deleted_flag:
            raise DatasetNotFoundError()
        self._check_owner(dataset, current_user)

        # 级联清理 DB 资源（统计数量）
        cell_meta_count = self.db.query(CellMetadata).filter(CellMetadata.dataset_id == dataset_id).count()
        cell_vec_count = self.db.query(CellVector).filter(CellVector.dataset_id == dataset_id).count()
        ann_count = self.db.query(ANNIndex).filter(ANNIndex.dataset_id == dataset_id).count()

        self.db.query(CellVector).filter(CellVector.dataset_id == dataset_id).delete()
        self.db.query(CellMetadata).filter(CellMetadata.dataset_id == dataset_id).delete()
        self.db.query(ANNIndex).filter(ANNIndex.dataset_id == dataset_id).delete()
        self.db.query(SearchTask).filter(SearchTask.dataset_id == dataset_id).delete()
        dataset.deleted_flag = True
        self.db.commit()

        # 级联清理磁盘
        remove_dir(settings.data_path / "processed" / str(dataset_id))
        remove_dir(settings.index_path / str(dataset_id))
        write_audit(current_user.id, "delete_dataset", "dataset", str(dataset_id))
        return {
            "dataset_id": dataset_id,
            "cascade_deleted": {
                "cell_metadata": cell_meta_count,
                "cell_vectors": cell_vec_count,
                "ann_indices": ann_count,
            },
        }

    def get_logs(self, dataset_id: int, current_user: User) -> dict:
        dataset = self.db.query(ExpressionMetadata).filter(ExpressionMetadata.id == dataset_id).first()
        if not dataset or dataset.deleted_flag:
            raise DatasetNotFoundError()
        self._check_owner(dataset, current_user)
        tasks = (
            self.db.query(SearchTask)
            .filter(SearchTask.dataset_id == dataset_id)
            .order_by(SearchTask.id.desc())
            .all()
        )
        steps = [
            {
                "step": t.task_type,
                "status": t.status,
                "duration_ms": t.progress,
            }
            for t in tasks
        ]
        warnings = [t.error_message for t in tasks if t.status == "failed" and t.error_message]
        errors = warnings
        return {"steps": steps, "warnings": warnings, "errors": errors}
