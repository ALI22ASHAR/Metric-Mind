"""create ai_dataset_understandings table

Revision ID: 0005_create_ai_understandings
Revises: 0004_create_semantic_models
Create Date: 2026-09-01 04:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_create_ai_understandings'
down_revision: Union[str, None] = '0004_create_semantic_models'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_dataset_understandings',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('dataset_id', sa.String(length=64), nullable=False, comment='Associated dataset ID'),
        sa.Column('domain', sa.String(length=64), nullable=False, comment='Inferred business domain'),
        sa.Column('business_summary', sa.Text(), nullable=False, comment='AI-generated executive business summary'),
        sa.Column('primary_date_column', sa.String(length=64), nullable=True, comment='Primary time dimension column'),
        sa.Column('confidence_score', sa.Float(), nullable=False, comment='Overall confidence score (0.0 - 1.0)'),
        sa.Column('understanding_json', sa.Text(), nullable=False, comment='Full serialized AIDatasetUnderstanding payload'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_dataset_understandings_id'), 'ai_dataset_understandings', ['id'], unique=False)
    op.create_index(op.f('ix_ai_dataset_understandings_dataset_id'), 'ai_dataset_understandings', ['dataset_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_dataset_understandings_dataset_id'), table_name='ai_dataset_understandings')
    op.drop_index(op.f('ix_ai_dataset_understandings_id'), table_name='ai_dataset_understandings')
    op.drop_table('ai_dataset_understandings')
