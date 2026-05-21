from pydantic import BaseModel, Field


class UploadInitRequest(BaseModel):
    filename: str
    size: int
    format: str = Field(pattern="^(h5ad|mtx|csv)$")


class UploadCompleteRequest(BaseModel):
    upload_id: str
