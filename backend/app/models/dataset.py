from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ExpressionMetadata(Base, TimestampMixin):
    __tablename__ = "expression_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_name: Mapped[str] = mapped_column(String(128), nullable=False)
    file_format: Mapped[str] = mapped_column(String(16), nullable=False)
    source_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False
    )
    cell_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gene_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qc_status: Mapped[str] = mapped_column(
        String(16), default="pending", nullable=False
    )
    preprocess_status: Mapped[str] = mapped_column(
        String(16), default="pending", nullable=False
    )
    feature_dim: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding_methods: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    deleted_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
