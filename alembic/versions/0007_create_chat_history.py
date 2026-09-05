"""create chat sessions and messages tables

Revision ID: 0007_create_chat_history
Revises: 0006_create_dashboards
Create Date: 2026-09-01 09:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007_create_chat_history'
down_revision: Union[str, None] = '0006_create_dashboards'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('dataset_id', sa.String(length=64), nullable=False, comment='Associated dataset identifier'),
        sa.Column('title', sa.String(length=255), nullable=False, comment='Session title or topic'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_sessions_dataset_id'), 'chat_sessions', ['dataset_id'], unique=False)
    op.create_index(op.f('ix_chat_sessions_id'), 'chat_sessions', ['id'], unique=False)

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False, comment='Parent chat session identifier'),
        sa.Column('role', sa.String(length=32), nullable=False, comment='Message role: user, assistant, system'),
        sa.Column('content', sa.Text(), nullable=False, comment='Message text content'),
        sa.Column('sql_query', sa.Text(), nullable=True, comment='Executed DuckDB SQL query if applicable'),
        sa.Column('chart_type', sa.String(length=64), nullable=True, comment='Rendered chart visualization type'),
        sa.Column('data_json', sa.Text(), nullable=True, comment='JSON-serialized query result data'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_id'), 'chat_messages', ['id'], unique=False)
    op.create_index(op.f('ix_chat_messages_session_id'), 'chat_messages', ['session_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_chat_messages_session_id'), table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_id'), table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index(op.f('ix_chat_sessions_id'), table_name='chat_sessions')
    op.drop_index(op.f('ix_chat_sessions_dataset_id'), table_name='chat_sessions')
    op.drop_table('chat_sessions')
