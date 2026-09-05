"""create dataset_quality_reports table and add clean_file_path to datasets

Revision ID: 0003_create_quality_reports
Revises: 0002_create_dataset_profiles
Create Date: 2026-09-01 02:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_create_quality_reports'
down_revision: Union[str, None] = '0002_create_dataset_profiles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add clean_file_path to datasets table
    op.add_column(
        'datasets',
        sa.Column('clean_file_path', sa.String(length=1024), nullable=True, comment='Local path to clean analytical parquet file')
    )

    # Create dataset_quality_reports table
    op.create_table(
        'dataset_quality_reports',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('dataset_id', sa.String(length=64), nullable=False, comment='Associated dataset ID'),
        sa.Column('quality_score', sa.Float(), nullable=False, comment='Overall dataset health score (0-100)'),
        sa.Column('clean_file_path', sa.String(length=1024), nullable=False, comment='Path to the generated clean parquet file'),
        sa.Column('cleaning_policy', sa.Text(), nullable=False, comment='JSON-serialized cleaning policy configuration'),
        sa.Column('report_data', sa.Text(), nullable=False, comment='JSON-serialized full DataQualityReport payload'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dataset_quality_reports_id'), 'dataset_quality_reports', ['id'], unique=False)
    op.create_index(op.f('ix_dataset_quality_reports_dataset_id'), 'dataset_quality_reports', ['dataset_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_dataset_quality_reports_dataset_id'), table_name='dataset_quality_reports')
    op.drop_index(op.f('ix_dataset_quality_reports_id'), table_name='dataset_quality_reports')
    op.drop_table('dataset_quality_reports')
    op.drop_column('datasets', 'clean_file_path')
