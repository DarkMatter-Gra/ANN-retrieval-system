from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    # 联合索引下 dataset_id 可不传；若传则要求该索引包含该 dataset
    dataset_id: int | None = None
    # 跨数据集结果过滤：只返回这些数据集中的细胞；为空表示不过滤
    dataset_ids: list[int] | None = None
    index_id: int
    query_type: str = Field(pattern="^(cell_id|vector)$")
    cell_id: str | None = None
    # cell_id 查询时，cell_id 在多数据集间可能重复，可指定来源 dataset
    source_dataset_id: int | None = None
    vector: list[float] | None = None
    top_k: int = Field(default=10, ge=1, le=1000)
    mode: str = Field(default="ann", pattern="^(exact|ann)$")
    metric: str = Field(default="l2", pattern="^(l2|ip|cosine)$")
    filters: dict[str, Any] = Field(default_factory=dict)
    ef_search: int | None = Field(default=None, ge=1, le=4096)


class BatchSearchRequest(BaseModel):
    dataset_id: int | None = None
    dataset_ids: list[int] | None = None
    index_id: int
    queries: list[dict[str, Any]] = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=1000)
    mode: str = Field(default="ann", pattern="^(exact|ann)$")
    filters: dict[str, Any] = Field(default_factory=dict)
    ef_search: int | None = Field(default=None, ge=1, le=4096)
    export_format: str = Field(default="json", pattern="^(json|csv)$")
