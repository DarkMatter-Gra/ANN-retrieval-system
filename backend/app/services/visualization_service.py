from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    DatasetNotFoundError,
    NotFoundError,
    ResourceForbiddenError,
)
from app.models.cell_metadata import CellMetadata
from app.models.dataset import ExpressionMetadata
from app.models.search_task import SearchTask
from app.models.user import User
from app.services.search_service import SearchService


class VisualizationService:
    def __init__(self, db: Session):
        self.db = db

    def _ensure_dataset(self, dataset_id: int, current_user: User) -> ExpressionMetadata:
        dataset = self.db.query(ExpressionMetadata).filter(ExpressionMetadata.id == dataset_id).first()
        if not dataset or dataset.deleted_flag:
            raise DatasetNotFoundError()
        if current_user.role != "admin" and dataset.owner_user_id != current_user.id:
            raise ResourceForbiddenError()
        return dataset

    def get_embedding(
        self,
        dataset_id: int,
        method: str,
        page: int,
        page_size: int,
        color_by: str | None,
        current_user: User,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> dict:
        self._ensure_dataset(dataset_id, current_user)

        file_path = Path(settings.data_path) / "processed" / str(dataset_id) / f"{method}.csv"
        if not file_path.exists():
            raise NotFoundError("embedding not found")

        df = pd.read_csv(file_path, index_col=0)

        if bbox is not None and df.shape[1] >= 2:
            x_min, y_min, x_max, y_max = bbox
            x_col, y_col = df.columns[0], df.columns[1]
            df = df[
                (df[x_col] >= x_min)
                & (df[x_col] <= x_max)
                & (df[y_col] >= y_min)
                & (df[y_col] <= y_max)
            ]

        total = int(df.shape[0])
        start = (page - 1) * page_size
        end = start + page_size
        chunk = df.iloc[start:end].copy()
        chunk["cell_id"] = chunk.index

        legend: list = []
        if color_by in {"cell_type", "organ", "sample_id"}:
            metas = (
                self.db.query(CellMetadata)
                .filter(CellMetadata.dataset_id == dataset_id)
                .all()
            )
            meta_map = {m.cell_id: getattr(m, color_by) for m in metas}
            chunk[color_by] = chunk["cell_id"].map(meta_map)
            legend = sorted({v for v in chunk[color_by].dropna().unique().tolist()})

        points = chunk.to_dict(orient="records")
        return {"points": points, "total": total, "legend": legend, "method": method}

    def get_highlights(self, query_id: str, current_user: User) -> dict:
        snapshot = SearchService.get_query_snapshot(query_id)
        if not snapshot:
            task = self.db.query(SearchTask).filter(SearchTask.task_id == query_id).first()
            if not task or task.task_type != "search":
                raise NotFoundError("query_id not found or expired")
            payload = task.request_payload or {}
            snapshot = {
                "dataset_id": task.dataset_id,
                "index_id": task.index_id,
                "query_cell_id": payload.get("cell_id"),
                "results": payload.get("results", []),
                "highlight_points": payload.get("highlight_points") or {"query": None, "neighbors": []},
            }

        dataset_id = int(snapshot["dataset_id"])
        self._ensure_dataset(dataset_id, current_user)

        highlight = snapshot.get("highlight_points") or {"query": None, "neighbors": []}
        return {
            "query_id": query_id,
            "dataset_id": dataset_id,
            "query_cell_id": snapshot.get("query_cell_id"),
            "query": highlight.get("query"),
            "neighbors": highlight.get("neighbors", []),
        }
