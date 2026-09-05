"""create dataset_profiles table

Revision ID: 0002_create_dataset_profiles
Revises: 0001_create_datasets
Create Date: 2026-09-01 01:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_create_dataset_profiles'
down_revision: Union[str, None] = '0001_create_datasets'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dataset_profiles',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('dataset_id', sa.String(length=64), nullable=False, comment='Associated dataset ID'),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('column_count', sa.Integer(), nullable=False),
        sa.Column('duplicate_rows', sa.Integer(), nullable=False),
        sa.Column('quality_warnings_count', sa.Integer(), nullable=False),
        sa.Column('profile_data', sa.Text(), nullable=False, comment='JSON-serialized full profile payload'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dataset_profiles_id'), 'dataset_profiles', ['id'], unique=False)
    op.create_index(op.f('ix_dataset_profiles_dataset_id'), 'dataset_profiles', ['dataset_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_dataset_profiles_dataset_id'), table_name='dataset_profiles')
    op.drop_index(op.f('ix_dataset_profiles_id'), table_name='dataset_profiles')
    op.drop_table('dataset_profiles')
