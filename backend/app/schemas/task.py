from pydantic import BaseModel, Field


class TaskQuery(BaseModel):
    task_id: str


class ReportRequest(BaseModel):
    query_id: str = Field(..., min_length=1, description="搜索查询 ID")
    include_umap_snapshot: bool = Field(False, description="是否在报告中嵌入 UMAP 快照")
    title: str | None = Field(None, max_length=200)
    note: str | None = Field(None, max_length=2000)
