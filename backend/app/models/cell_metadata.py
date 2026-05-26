from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CellMetadata(Base):
    __tablename__ = "cell_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("expression_metadata.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    cell_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    cell_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    organ: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sample_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    obs_ext: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    qc_flags: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
