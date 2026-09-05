"""create initial datasets table

Revision ID: 0001_create_datasets
Revises: 
Create Date: 2026-09-01 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_create_datasets'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'datasets',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False, comment='Original uploaded filename'),
        sa.Column('file_path', sa.String(length=1024), nullable=False, comment='Local or storage path to the raw dataset file'),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False, comment='Size of uploaded file in bytes'),
        sa.Column('mime_type', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, comment='Lifecycle status: uploaded, processing, ready, failed'),
        sa.Column('row_count', sa.Integer(), nullable=True, comment='Total number of rows detected'),
        sa.Column('column_count', sa.Integer(), nullable=True, comment='Total number of columns detected'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Diagnostic error details if processing fails'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_datasets_id'), 'datasets', ['id'], unique=False)
    op.create_index(op.f('ix_datasets_status'), 'datasets', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_datasets_status'), table_name='datasets')
    op.drop_index(op.f('ix_datasets_id'), table_name='datasets')
    op.drop_table('datasets')
