"""add dataset_ids to ann_indices for joint indexing

Revision ID: d18e2a3b9b21
Revises: c94893e4f345
Create Date: 2026-06-30 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d18e2a3b9b21"
down_revision: Union[str, None] = "c94893e4f345"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite 不支持带默认值的 JSON 字段，通过 batch_alter_table 兼容
    with op.batch_alter_table("ann_indices") as batch_op:
        batch_op.add_column(
            sa.Column("dataset_ids", sa.JSON(), nullable=True)
        )
    # 旧数据 backfill：dataset_ids = [dataset_id]
    op.execute(
        "UPDATE ann_indices "
        "SET dataset_ids = '[' || CAST(dataset_id AS TEXT) || ']' "
        "WHERE dataset_ids IS NULL OR dataset_ids = ''"
    )


def downgrade() -> None:
    with op.batch_alter_table("ann_indices") as batch_op:
        batch_op.drop_column("dataset_ids")
