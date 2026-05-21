from typing import Any

from pydantic import BaseModel, Field


class CreateIndexRequest(BaseModel):
    dataset_id: int
    index_name: str = Field(min_length=1, max_length=128)
    index_type: str = Field(pattern="^(flat|ivf_pq|hnsw)$")
    metric: str = Field(default="l2", pattern="^(l2|ip|cosine)$")
    params_json: dict[str, Any] = Field(default_factory=dict)


class PublishIndexRequest(BaseModel):
    audit_comment: str = Field(min_length=1)


class RollbackIndexRequest(BaseModel):
    target_version: int
