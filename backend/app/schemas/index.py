from typing import Any

from pydantic import BaseModel, Field, model_validator


class CreateIndexRequest(BaseModel):
    dataset_id: int | None = None
    # 多数据集联合索引：提供 dataset_ids 时主 dataset_id 默认取列表首元素
    dataset_ids: list[int] | None = None
    index_name: str = Field(min_length=1, max_length=128)
    index_type: str = Field(pattern="^(flat|ivf_pq|hnsw|hnsw_rerank)$")
    metric: str = Field(default="l2", pattern="^(l2|ip|cosine)$")
    params_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _normalize_dataset_fields(self) -> "CreateIndexRequest":
        if self.dataset_ids:
            # 去重保序
            seen: set[int] = set()
            ordered: list[int] = []
            for ds_id in self.dataset_ids:
                if ds_id not in seen:
                    seen.add(ds_id)
                    ordered.append(int(ds_id))
            self.dataset_ids = ordered
            if self.dataset_id is None:
                self.dataset_id = ordered[0]
        elif self.dataset_id is not None:
            self.dataset_ids = [int(self.dataset_id)]
        else:
            raise ValueError("dataset_id or dataset_ids is required")
        return self


class PublishIndexRequest(BaseModel):
    audit_comment: str = Field(min_length=1)


class RollbackIndexRequest(BaseModel):
    target_version: int
