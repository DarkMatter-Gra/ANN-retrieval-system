from pydantic import BaseModel, Field


class AISearchRequest(BaseModel):
    dataset_id: int
    index_id: int
    question: str = Field(min_length=1, max_length=500)
