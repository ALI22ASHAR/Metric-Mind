"""create dashboards table

Revision ID: 0006_create_dashboards
Revises: 0005_create_ai_understandings
Create Date: 2026-09-01 05:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006_create_dashboards'
down_revision: Union[str, None] = '0005_create_ai_understandings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dashboards',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('dataset_id', sa.String(length=64), nullable=False, comment='Associated dataset ID'),
        sa.Column('title', sa.String(length=255), nullable=False, comment='Dashboard title'),
        sa.Column('subtitle', sa.Text(), nullable=True, comment='Dashboard subtitle or description'),
        sa.Column('theme', sa.String(length=32), nullable=False, comment='Visual theme (dark / light)'),
        sa.Column('is_default', sa.Boolean(), nullable=False, comment='Whether this is primary default dashboard'),
        sa.Column('spec_json', sa.Text(), nullable=False, comment='Full JSON-serialized DashboardSpec payload'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dashboards_id'), 'dashboards', ['id'], unique=False)
    op.create_index(op.f('ix_dashboards_dataset_id'), 'dashboards', ['dataset_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dashboards_dataset_id'), table_name='dashboards')
    op.drop_index(op.f('ix_dashboards_id'), table_name='dashboards')
    op.drop_table('dashboards')
