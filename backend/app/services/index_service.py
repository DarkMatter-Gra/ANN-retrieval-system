import uuid

from sqlalchemy import String, func
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
        index_name: str,
        index_type: str,
        metric: str,
        params_json: dict,
        dataset_ids: list[int] | None = None,
        dataset_id: int | None = None,  # 单数据集旧入参，保留兼容
    ) -> dict:
        from app.tasks.index_tasks import build_index_task

        # 归一化 dataset_ids
        if dataset_ids:
            ds_id_list = [int(d) for d in dataset_ids if d is not None]
        elif dataset_id is not None:
            ds_id_list = [int(dataset_id)]
        else:
            raise ValidationFailed("dataset_id or dataset_ids is required")
        # 保序去重
        seen: set[int] = set()
        ordered_ds_ids: list[int] = []
        for d in ds_id_list:
            if d not in seen:
                seen.add(d)
                ordered_ds_ids.append(d)
        if not ordered_ds_ids:
            raise ValidationFailed("dataset_ids is empty")
        primary_dataset_id = ordered_ds_ids[0]

        datasets = (
            self.db.query(ExpressionMetadata)
            .filter(ExpressionMetadata.id.in_(ordered_ds_ids))
            .all()
        )
        if len(datasets) != len(ordered_ds_ids):
            raise DatasetNotFoundError()
        for ds in datasets:
            if ds.deleted_flag:
                raise DatasetNotFoundError()
            if owner.role != "admin" and ds.owner_user_id != owner.id:
                raise ResourceForbiddenError()
            if ds.preprocess_status != "done":
                raise ConflictError(f"dataset {ds.id} preprocess not done")

        # 联合索引要求所有数据集 PCA 维度一致
        sample_rows = (
            self.db.query(CellVector.dataset_id, CellVector.dim, func.count(CellVector.id))
            .filter(CellVector.dataset_id.in_(ordered_ds_ids), CellVector.vector_type == "pca")
            .group_by(CellVector.dataset_id, CellVector.dim)
            .all()
        )
        if not sample_rows:
            raise ConflictError("no pca vectors available across selected datasets")
        dims = {int(dim) for _, dim, _ in sample_rows}
        if len(dims) != 1:
            raise ConflictError(f"pca dim mismatch across datasets: {sorted(dims)}")
        sample_dim = next(iter(dims))
        per_dataset_count = {int(ds_id): int(cnt) for ds_id, _, cnt in sample_rows}
        for ds_id in ordered_ds_ids:
            if per_dataset_count.get(ds_id, 0) <= 0:
                raise ConflictError(f"dataset {ds_id} has no pca vectors")
        vector_count = sum(per_dataset_count.values())

        try:
            ANNEngine.validate_config(index_type, metric, params_json, int(sample_dim), int(vector_count))
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc

        latest_version = (
            self.db.query(func.coalesce(func.max(ANNIndex.version_no), 0))
            .filter(ANNIndex.dataset_id == primary_dataset_id)
            .scalar()
        )
        version_no = int(latest_version or 0) + 1
        index_dir = ensure_dir(self.index_root / str(primary_dataset_id) / f"v{version_no}")

        index_obj = ANNIndex(
            dataset_id=primary_dataset_id,
            dataset_ids=ordered_ds_ids,
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
            dataset_id=primary_dataset_id,
            index_id=index_obj.id,
            status="pending",
            progress=0,
            request_payload={
                "dataset_id": primary_dataset_id,
                "dataset_ids": ordered_ds_ids,
                "index_type": index_type,
                "metric": metric,
                "params_json": params_json,
            },
        )
        self.db.add(task)
        self.db.commit()

        write_audit(
            owner.id,
            "create_index",
            "index",
            str(index_obj.id),
            {"type": index_type, "dataset_ids": ordered_ds_ids},
        )
        build_index_task.delay(task.task_id, ordered_ds_ids, index_obj.id)
        self.db.refresh(task)
        self.db.refresh(index_obj)
        return {
            "index_id": index_obj.id,
            "task_id": task.task_id,
            "status": task.status,
            "dataset_ids": ordered_ds_ids,
        }

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
            # 联合索引：主 dataset_id 命中，或 dataset_ids JSON 中包含该值
            like_token = f"%{int(dataset_id)}%"
            query = query.filter(
                (ANNIndex.dataset_id == dataset_id)
                | (ANNIndex.dataset_ids.cast(String).like(like_token))
            )
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
            "dataset_ids": list(r.dataset_ids or [r.dataset_id]),
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
