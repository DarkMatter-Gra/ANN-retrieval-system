import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    DatasetNotFoundError,
    IndexNotFoundError,
    ResourceForbiddenError,
    ValidationFailed,
)
from app.models.ann_index import ANNIndex
from app.models.cell_vector import CellVector
from app.models.dataset import ExpressionMetadata
from app.models.search_task import SearchTask
from app.models.user import User
from app.services.ann_engine import ANNEngine
from app.utils.audit import write_audit
from app.utils.file_store import ensure_dir


# 进程内索引缓存
_LOADED_INDEXES: dict[int, object] = {}


def get_loaded_index(index_id: int) -> object | None:
    return _LOADED_INDEXES.get(index_id)


def cache_index(index_id: int, obj: object) -> None:
    _LOADED_INDEXES[index_id] = obj


def evict_index(index_id: int) -> None:
    _LOADED_INDEXES.pop(index_id, None)


class IndexService:
    def __init__(self, db: Session):
        self.db = db
        self.index_root = ensure_dir(settings.index_path)

    # ----------------------------- 创建任务 -----------------------------
    def create_index_task(
        self,
        owner: User,
        dataset_id: int,
        index_name: str,
        index_type: str,
        metric: str,
        params_json: dict,
    ) -> dict:
        from app.tasks.index_tasks import build_index_task

        dataset = self.db.query(ExpressionMetadata).filter(ExpressionMetadata.id == dataset_id).first()
        if not dataset or dataset.deleted_flag:
            raise DatasetNotFoundError()
        if owner.role != "admin" and dataset.owner_user_id != owner.id:
            raise ResourceForbiddenError()
        if dataset.preprocess_status != "done":
            raise ConflictError("dataset preprocess not done")
        sample = (
            self.db.query(CellVector)
            .filter(CellVector.dataset_id == dataset_id, CellVector.vector_type == "pca")
            .first()
        )
        vector_count = (
            self.db.query(CellVector)
            .filter(CellVector.dataset_id == dataset_id, CellVector.vector_type == "pca")
            .count()
        )
        if not sample or vector_count <= 0:
            raise ConflictError("dataset has no pca vectors")
        try:
            ANNEngine.validate_config(index_type, metric, params_json, int(sample.dim), int(vector_count))
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc

        latest_version = (
            self.db.query(func.coalesce(func.max(ANNIndex.version_no), 0))
            .filter(ANNIndex.dataset_id == dataset_id)
            .scalar()
        )
        version_no = int(latest_version or 0) + 1
        index_dir = ensure_dir(self.index_root / str(dataset_id) / f"v{version_no}")

        index_obj = ANNIndex(
            dataset_id=dataset_id,
            owner_user_id=owner.id,
            index_name=index_name,
            index_type=index_type,
            metric_type=metric,
            params_json=params_json,
            file_path=str(index_dir / f"{index_type}.index"),
            version_no=version_no,
            build_status="pending",
            publish_status="draft",
        )
        self.db.add(index_obj)
        self.db.commit()
        self.db.refresh(index_obj)

        task = SearchTask(
            task_id=uuid.uuid4().hex,
            owner_user_id=owner.id,
            task_type="build_index",
            dataset_id=dataset_id,
            index_id=index_obj.id,
            status="pending",
            progress=0,
            request_payload={
                "dataset_id": dataset_id,
                "index_type": index_type,
                "metric": metric,
                "params_json": params_json,
            },
        )
        self.db.add(task)
        self.db.commit()

        write_audit(owner.id, "create_index", "index", str(index_obj.id), {"type": index_type})
        build_index_task.delay(task.task_id, dataset_id, index_obj.id)
        self.db.refresh(task)
        self.db.refresh(index_obj)
        return {"index_id": index_obj.id, "task_id": task.task_id, "status": task.status}

    # ----------------------------- 列表/详情 -----------------------------
    def list_indexes(
        self,
        current_user: User,
        dataset_id: int | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> dict:
        query = self.db.query(ANNIndex)
        if dataset_id is not None:
            query = query.filter(ANNIndex.dataset_id == dataset_id)
        if status is not None:
            query = query.filter(ANNIndex.build_status == status)
        if current_user.role != "admin":
            query = query.filter(ANNIndex.owner_user_id == current_user.id)
        total = query.count()
        rows = (
            query.order_by(ANNIndex.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = [self._serialize(r) for r in rows]
        return {"list": items, "total": total}

    def get_detail(self, index_id: int, current_user: User) -> dict:
        index_obj = self._get_or_404(index_id, current_user)
        return {
            "index_meta": self._serialize(index_obj),
            "version": index_obj.version_no,
            "recall": index_obj.recall_score,
            "memory_usage": index_obj.memory_cost_mb,
        }

    # ----------------------------- 发布/回滚/加载 -----------------------------
    def publish(self, index_id: int, audit_comment: str, operator: User) -> dict:
        index_obj = self._get_or_404(index_id, operator)
        if index_obj.build_status != "done":
            raise ConflictError("index not ready")
        # 同 dataset 下其他 published 设为 approved
        self.db.query(ANNIndex).filter(
            ANNIndex.dataset_id == index_obj.dataset_id,
            ANNIndex.id != index_obj.id,
            ANNIndex.publish_status == "published",
        ).update({"publish_status": "approved"}, synchronize_session=False)
        index_obj.publish_status = "published"
        self.db.commit()
        write_audit(
            operator.id,
            "publish_index",
            "index",
            str(index_obj.id),
            {"comment": audit_comment, "version": index_obj.version_no},
        )
        return {"index_id": index_obj.id, "published": True}

    def rollback(self, index_id: int, target_version: int, operator: User) -> dict:
        current = self._get_or_404(index_id, operator)
        target = (
            self.db.query(ANNIndex)
            .filter(
                ANNIndex.dataset_id == current.dataset_id,
                ANNIndex.version_no == target_version,
                ANNIndex.build_status == "done",
            )
            .first()
        )
        if not target:
            raise IndexNotFoundError("target version not found")
        self.db.query(ANNIndex).filter(ANNIndex.dataset_id == current.dataset_id).update(
            {"publish_status": "approved"}, synchronize_session=False
        )
        target.publish_status = "published"
        self.db.commit()
        # 失效缓存以避免使用旧对象
        evict_index(current.id)
        evict_index(target.id)
        write_audit(operator.id, "rollback_index", "index", str(target.id))
        return {"index_id": target.id, "active_version": target.version_no}

    def load_into_memory(self, index_id: int, operator: User) -> dict:
        index_obj = self._get_or_404(index_id, operator)
        if index_obj.build_status != "done":
            raise ConflictError("index not ready")
        loaded = self._load_index_object(index_obj)
        cache_index(index_obj.id, loaded)
        index_obj.is_loaded = True
        self.db.commit()
        write_audit(operator.id, "load_index", "index", str(index_obj.id))
        return {"index_id": index_obj.id, "loaded": True, "memory_slot": id(loaded)}

    def _load_index_object(self, index_obj: ANNIndex):
        sample = (
            self.db.query(CellVector)
            .filter(CellVector.dataset_id == index_obj.dataset_id, CellVector.vector_type == "pca")
            .first()
        )
        return ANNEngine.load(index_obj, dim=sample.dim if sample else None)

    # ----------------------------- 内部 -----------------------------
    def _get_or_404(self, index_id: int, current_user: User) -> ANNIndex:
        index_obj = self.db.query(ANNIndex).filter(ANNIndex.id == index_id).first()
        if not index_obj:
            raise IndexNotFoundError()
        if current_user.role != "admin" and index_obj.owner_user_id != current_user.id:
            raise ResourceForbiddenError()
        return index_obj

    @staticmethod
    def _serialize(r: ANNIndex) -> dict:
        return {
            "index_id": r.id,
            "dataset_id": r.dataset_id,
            "index_name": r.index_name,
            "index_type": r.index_type,
            "metric_type": r.metric_type,
            "params_json": r.params_json,
            "file_path": r.file_path,
            "version_no": r.version_no,
            "build_status": r.build_status,
            "publish_status": r.publish_status,
            "recall_score": r.recall_score,
            "memory_cost_mb": r.memory_cost_mb,
            "is_loaded": r.is_loaded,
        }
