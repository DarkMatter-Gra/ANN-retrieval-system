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
    def get_metadata_by_cell_ids(self, dataset_id: int, cell_ids: list[str]) -> list[dict]:
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