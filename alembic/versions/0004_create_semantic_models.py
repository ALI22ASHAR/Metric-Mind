"""create semantic_models table

Revision ID: 0004_create_semantic_models
Revises: 0003_create_quality_reports
Create Date: 2026-09-01 03:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_create_semantic_models'
down_revision: Union[str, None] = '0003_create_quality_reports'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'semantic_models',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('dataset_id', sa.String(length=64), nullable=False, comment='Associated dataset ID'),
        sa.Column('domain', sa.String(length=64), nullable=False, comment='Inferred or assigned business domain'),
        sa.Column('dataset_type', sa.String(length=64), nullable=False, comment='Dataset classification'),
        sa.Column('mappings_json', sa.Text(), nullable=False, comment='JSON dictionary of business concept to column name mappings'),
        sa.Column('dimensions_json', sa.Text(), nullable=False, comment='JSON list of categorical dimension columns'),
        sa.Column('measures_json', sa.Text(), nullable=False, comment='JSON list of quantitative measure columns'),
        sa.Column('confidence_json', sa.Text(), nullable=False, comment='JSON dictionary of mapping confidence scores'),
        sa.Column('model_data', sa.Text(), nullable=False, comment='Full JSON-serialized SemanticModelSchema payload'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_semantic_models_id'), 'semantic_models', ['id'], unique=False)
    op.create_index(op.f('ix_semantic_models_dataset_id'), 'semantic_models', ['dataset_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_semantic_models_dataset_id'), table_name='semantic_models')
    op.drop_index(op.f('ix_semantic_models_id'), table_name='semantic_models')
    op.drop_table('semantic_models')
