from sqlalchemy import Float, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CellVector(Base):
    __tablename__ = "cell_vectors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("expression_metadata.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    cell_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    vector_type: Mapped[str] = mapped_column(String(32), default="pca", nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    vector_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    norm_value: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
