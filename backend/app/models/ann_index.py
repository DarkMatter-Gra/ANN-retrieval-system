from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ANNIndex(Base, TimestampMixin):
    __tablename__ = "ann_indices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("expression_metadata.id", ondelete="CASCADE"), index=True, nullable=False
    )
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    index_name: Mapped[str] = mapped_column(String(128), nullable=False)
    index_type: Mapped[str] = mapped_column(String(32), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(16), nullable=False)
    params_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    build_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    publish_status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    recall_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    memory_cost_mb: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_loaded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
