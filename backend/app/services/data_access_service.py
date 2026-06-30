import numpy as np
from sqlalchemy.orm import Session

from app.core.exceptions import DatasetNotFoundError
from app.models.cell_metadata import CellMetadata
from app.models.cell_vector import CellVector
from app.utils.vector_codec import decode_vector


class DataAccessService:
    def __init__(self, db: Session):
        self.db = db

    def get_vector_by_cell_id(self, dataset_id: int, cell_id: str) -> np.ndarray:
        row = (
            self.db.query(CellVector)
            .filter(
                CellVector.dataset_id == dataset_id,
                CellVector.cell_id == cell_id,
                CellVector.vector_type == "pca",
            )
            .first()
        )
        if not row:
            raise DatasetNotFoundError("cell_id not found")
        return decode_vector(row.vector_blob)

    def get_metadata_by_cell_id(self, dataset_id: int, cell_id: str) -> dict:
        row = (
            self.db.query(CellMetadata)
            .filter(
                CellMetadata.dataset_id == dataset_id,
                CellMetadata.cell_id == cell_id,
            )
            .first()
        )
        if not row:
            raise DatasetNotFoundError("cell_id metadata not found")

        return {
            "cell_id": row.cell_id,
            "cell_type": row.cell_type,
            "organ": row.organ,
            "sample_id": row.sample_id,
            "obs_ext": row.obs_ext,
            "qc_flags": row.qc_flags,
        }

    # 保证返回的 cell_ids 与 cell_ids 顺序一致
    def get_metadata_by_cell_ids(
        self, dataset_id: int, cell_ids: list[str]
    ) -> list[dict]:
        if not cell_ids:
            return []

        rows = (
            self.db.query(CellMetadata)
            .filter(
                CellMetadata.dataset_id == dataset_id,
                CellMetadata.cell_id.in_(cell_ids),
            )
            .all()
        )

        row_map = {}
        for row in rows:
            row_map[row.cell_id] = {
                "cell_id": row.cell_id,
                "cell_type": row.cell_type,
                "organ": row.organ,
                "sample_id": row.sample_id,
                "obs_ext": row.obs_ext,
                "qc_flags": row.qc_flags,
            }

        result = []
        for cell_id in cell_ids:
            if cell_id in row_map:
                result.append(row_map[cell_id])

        return result

    # 返回该数据集各主元数据字段的去重取值，供 LLM 解析自然语言时当“词典”用
    # 主字段：cell_type / organ / sample_id
    # 扩展字段：从 obs_ext 中取 EXT_FIELDS（disease / AgeGroup / sex）
    EXT_FIELDS = ("disease", "AgeGroup", "sex")

    def get_field_values(self, dataset_id: int, limit_per_field: int = 50) -> dict:
        rows = (
            self.db.query(
                CellMetadata.cell_type,
                CellMetadata.organ,
                CellMetadata.sample_id,
                CellMetadata.obs_ext,
            )
            .filter(CellMetadata.dataset_id == dataset_id)
            .all()
        )

        cell_types: set[str] = set()
        organs: set[str] = set()
        sample_ids: set[str] = set()
        ext_values: dict[str, set[str]] = {f: set() for f in self.EXT_FIELDS}

        for cell_type, organ, sample_id, obs_ext in rows:
            if cell_type:
                cell_types.add(cell_type)
            if organ:
                organs.add(organ)
            if sample_id:
                sample_ids.add(sample_id)
            obs_ext = obs_ext or {}
            for field in self.EXT_FIELDS:
                value = obs_ext.get(field)
                if value not in (None, ""):
                    ext_values[field].add(str(value))

        result = {
            "cell_type": sorted(cell_types)[:limit_per_field],
            "organ": sorted(organs)[:limit_per_field],
            "sample_id": sorted(sample_ids)[:limit_per_field],
        }
        for field in self.EXT_FIELDS:
            result[field] = sorted(ext_values[field])[:limit_per_field]
        return result

    # 对一批 cell_id 做字段分布统计，作为 AI 解读的“事实依据”，防止幻觉
    def aggregate_metadata(self, dataset_id: int, cell_ids: list[str]) -> dict:
        metas = self.get_metadata_by_cell_ids(dataset_id, cell_ids)

        def count_by(field: str) -> dict:
            counter: dict[str, int] = {}
            for meta in metas:
                value = meta.get(field) or "unknown"
                counter[value] = counter.get(value, 0) + 1
            return dict(sorted(counter.items(), key=lambda kv: kv[1], reverse=True))

        def count_by_ext(field: str) -> dict:
            counter: dict[str, int] = {}
            for meta in metas:
                value = (meta.get("obs_ext") or {}).get(field) or "unknown"
                counter[str(value)] = counter.get(str(value), 0) + 1
            return dict(sorted(counter.items(), key=lambda kv: kv[1], reverse=True))

        stats = {
            "total": len(metas),
            "cell_type": count_by("cell_type"),
            "organ": count_by("organ"),
            "sample_id": count_by("sample_id"),
        }
        for field in self.EXT_FIELDS:
            stats[field] = count_by_ext(field)
        return stats

    # 计算一批 cell_id 对应向量的平均向量（类中心），作为更稳定的检索锚点
    def get_centroid_vector(self, dataset_id: int, cell_ids: list[str]) -> np.ndarray:
        if not cell_ids:
            raise DatasetNotFoundError("no cells to compute centroid")
        rows = (
            self.db.query(CellVector)
            .filter(
                CellVector.dataset_id == dataset_id,
                CellVector.vector_type == "pca",
                CellVector.cell_id.in_(cell_ids),
            )
            .all()
        )
        if not rows:
            raise DatasetNotFoundError("no vectors found for given cells")
        matrix = np.stack([decode_vector(row.vector_blob) for row in rows])
        return matrix.mean(axis=0).astype(np.float32)

    # 按主字段 + obs_ext 扩展字段过滤，返回匹配的 cell_id 列表
    def filter_cell_ids(
        self, dataset_id: int, filters: dict, limit: int | None = None
    ) -> list[str]:
        rows = (
            self.db.query(CellMetadata)
            .filter(CellMetadata.dataset_id == dataset_id)
            .all()
        )
        matched: list[str] = []
        for row in rows:
            if self._row_matches(row, filters):
                matched.append(row.cell_id)
                if limit and len(matched) >= limit:
                    break
        return matched

    @staticmethod
    def _row_matches(row: CellMetadata, filters: dict) -> bool:
        main_fields = {"cell_type", "organ", "sample_id"}
        obs_ext = row.obs_ext or {}
        for key, expected in filters.items():
            if expected in (None, "", []):
                continue
            if key in main_fields:
                actual = getattr(row, key, None)
            else:
                actual = obs_ext.get(key)
            if str(actual) != str(expected):
                return False
        return True
