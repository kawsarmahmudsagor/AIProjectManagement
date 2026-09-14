"""add llm_usage_logs table

Revision ID: a3f7c1e9b2d4
Revises: e2d6b8a1c4f7
Create Date: 2026-09-08 00:00:00.000000

Reuses the existing `provider_name` Postgres TYPE (create_type=False), same reasoning
as every other job table that references it. `session_id` is a nullable FK with
ON DELETE SET NULL (not CASCADE) — deleting a chat session must not erase its cost
history. `operation` is a plain indexed String, not a Postgres enum: this set of tags
(chat/chat_title/chat_compaction/extract/rewrite/breakdown/brag_document) will grow and
only this app's own code ever writes it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a3f7c1e9b2d4'
down_revision: Union[str, None] = 'e2d6b8a1c4f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    provider_name = postgresql.ENUM('GEMINI', 'OPENAI', name='provider_name', create_type=False)

    op.create_table(
        'llm_usage_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('provider', provider_name, nullable=False),
        sa.Column('model', sa.String(length=120), nullable=False),
        sa.Column('operation', sa.String(length=32), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False),
        sa.Column('output_tokens', sa.Integer(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_llm_usage_logs_user_id', 'llm_usage_logs', ['user_id'])
    op.create_index('ix_llm_usage_logs_operation', 'llm_usage_logs', ['operation'])
    op.create_index('ix_llm_usage_logs_created_at', 'llm_usage_logs', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_llm_usage_logs_created_at', table_name='llm_usage_logs')
    op.drop_index('ix_llm_usage_logs_operation', table_name='llm_usage_logs')
    op.drop_index('ix_llm_usage_logs_user_id', table_name='llm_usage_logs')
    op.drop_table('llm_usage_logs')
