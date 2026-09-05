"""add workspace ownership to datasets

Revision ID: 0009_add_dataset_workspace
Revises: 0008_create_auth_workspaces
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_add_dataset_workspace"
down_revision: Union[str, None] = "0008_create_auth_workspaces"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("workspace_id", sa.String(length=64), nullable=True))
    op.create_index("ix_datasets_workspace_id", "datasets", ["workspace_id"], unique=False)
    op.create_foreign_key(
        "fk_datasets_workspace_id_workspaces",
        "datasets",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_datasets_workspace_id_workspaces", "datasets", type_="foreignkey")
    op.drop_index("ix_datasets_workspace_id", table_name="datasets")
    op.drop_column("datasets", "workspace_id")