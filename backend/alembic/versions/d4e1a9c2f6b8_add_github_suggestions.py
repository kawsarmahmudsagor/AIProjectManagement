"""add github repo cache and repo suggestions tables

Revision ID: d4e1a9c2f6b8
Revises: 46f274f3644d
Create Date: 2026-08-31 00:00:00.000001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd4e1a9c2f6b8'
down_revision: Union[str, None] = '46f274f3644d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'github_repo_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('technology', sa.String(length=40), nullable=False),
        sa.Column('repos', sa.JSON(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        'ix_github_repo_cache_technology', 'github_repo_cache', ['technology'], unique=True
    )

    suggestion_source = sa.Enum('DASHBOARD', 'CHAT', name='suggestion_source')

    op.create_table(
        'repo_suggestions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('technology', sa.String(length=40), nullable=False),
        sa.Column('technology_display', sa.String(length=40), nullable=False),
        sa.Column('repo_full_name', sa.String(length=255), nullable=False),
        sa.Column('repo', sa.JSON(), nullable=False),
        sa.Column('source', suggestion_source, nullable=False, server_default='DASHBOARD'),
        sa.Column('rank', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('dismissed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint(
            'user_id', 'technology', 'repo_full_name', name='uq_repo_suggestions_user_tech_repo'
        ),
    )
    op.create_index('ix_repo_suggestions_user_id', 'repo_suggestions', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_repo_suggestions_user_id', table_name='repo_suggestions')
    op.drop_table('repo_suggestions')
    sa.Enum(name='suggestion_source').drop(op.get_bind())

    op.drop_index('ix_github_repo_cache_technology', table_name='github_repo_cache')
    op.drop_table('github_repo_cache')
