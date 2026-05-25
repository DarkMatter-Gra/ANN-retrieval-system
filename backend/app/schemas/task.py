from pydantic import BaseModel, Field


class TaskQuery(BaseModel):
    task_id: str


class ReportRequest(BaseModel):
    query_id: str | None = Field(None, min_length=1, description="搜索查询 ID")
    dataset_id: int | None = Field(None, ge=1, description="数据集 ID")
    index_id: int | None = Field(None, ge=1, description="索引 ID")
    include_umap_snapshot: bool = Field(False, description="是否在报告中嵌入 UMAP 快照")
    include_qc: bool = Field(True, description="是否包含 QC 报告")
    include_performance: bool = Field(True, description="是否包含性能报告")
    title: str | None = Field(None, max_length=200)
    note: str | None = Field(None, max_length=2000)
