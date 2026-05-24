from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    dataset_id: int
    index_id: int
    query_type: str = Field(pattern="^(cell_id|vector)$")
    cell_id: str | None = None
    vector: list[float] | None = None
    top_k: int = Field(default=10, ge=1, le=1000)
    mode: str = Field(default="ann", pattern="^(exact|ann)$")
    metric: str = Field(default="l2", pattern="^(l2|ip|cosine)$")
    filters: dict[str, Any] = Field(default_factory=dict)
    ef_search: int | None = Field(default=None, ge=1, le=4096)


class BatchSearchRequest(BaseModel):
    dataset_id: int
    index_id: int
    queries: list[dict[str, Any]] = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=1000)
    mode: str = Field(default="ann", pattern="^(exact|ann)$")
    filters: dict[str, Any] = Field(default_factory=dict)
    ef_search: int | None = Field(default=None, ge=1, le=4096)
    export_format: str = Field(default="json", pattern="^(json|csv)$")
