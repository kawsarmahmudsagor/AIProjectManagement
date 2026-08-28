"""add chat, profile, and user name/chatbot fields

Revision ID: c7a2f4d8b915
Revises: 99fed415a0eb
Create Date: 2026-08-28 00:00:00.000001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c7a2f4d8b915'
down_revision: Union[str, None] = '99fed415a0eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # --- users: structured name + chatbot preference columns ---
    op.add_column('users', sa.Column('first_name', sa.String(length=80), nullable=True))
    op.add_column('users', sa.Column('middle_name', sa.String(length=80), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(length=80), nullable=True))
    op.add_column('users', sa.Column('preferred_name', sa.String(length=80), nullable=True))

    # Backfill any pre-existing rows from the email local-part — this is a greenfield dev
    # app, so a rough backfill (not a real name-parsing attempt) is fine; every new
    # registration provides a real first_name going forward.
    op.execute("UPDATE users SET first_name = split_part(email, '@', 1) WHERE first_name IS NULL")
    op.alter_column('users', 'first_name', nullable=False)

    chat_provider = sa.Enum('GEMINI', 'OLLAMA', name='chat_provider')
    chat_provider.create(bind)
    op.add_column(
        'users',
        sa.Column('chat_provider', chat_provider, nullable=False, server_default='GEMINI'),
    )
    op.add_column(
        'users',
        sa.Column(
            'chatbot_preemptive_github_suggestions',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # --- user_profiles: 1:1 CV-style content, every field but the FK is optional ---
    op.create_table(
        'user_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('photo_path', sa.String(length=500), nullable=True),
        sa.Column('designation', sa.String(length=150), nullable=True),
        sa.Column('team', sa.String(length=150), nullable=True),
        sa.Column('organization', sa.String(length=150), nullable=True),
        sa.Column('speciality', sa.String(length=150), nullable=True),
        sa.Column('primary_skills', postgresql.ARRAY(sa.String(length=60)), nullable=False, server_default='{}'),
        sa.Column('secondary_skills', postgresql.ARRAY(sa.String(length=60)), nullable=False, server_default='{}'),
        sa.Column('professional_biography', sa.Text(), nullable=False, server_default=''),
        sa.Column('work_experience_summary', sa.Text(), nullable=False, server_default=''),
        sa.Column('career_objective', sa.Text(), nullable=False, server_default=''),
        sa.Column('key_strengths', sa.Text(), nullable=False, server_default=''),
        sa.Column('responsibilities', sa.Text(), nullable=False, server_default=''),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', name='uq_user_profiles_user_id'),
    )
    op.create_index('ix_user_profiles_user_id', 'user_profiles', ['user_id'])

    # Auto-create an empty profile row for any pre-existing user, matching the invariant
    # that every user has exactly one profile row from registration onward.
    op.execute(
        "INSERT INTO user_profiles (id, user_id, created_at, updated_at) "
        "SELECT gen_random_uuid(), id, now(), now() FROM users"
    )

    # --- chat_sessions / chat_messages ---
    # Unlike chat_provider/agent_persona above (added via op.add_column, which needs an
    # explicit .create() first), op.create_table's own DDL compiler creates an enum
    # column's type itself — calling .create() here too raises a duplicate-type error.
    chat_role = sa.Enum('USER', 'ASSISTANT', 'TOOL', name='chat_role')

    op.create_table(
        'chat_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False, server_default='New chat'),
        sa.Column('last_message_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_chat_sessions_user_id', 'chat_sessions', ['user_id'])

    op.create_table(
        'chat_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', chat_role, nullable=False),
        sa.Column('content', sa.Text(), nullable=False, server_default=''),
        sa.Column('tool_calls', postgresql.JSONB(), nullable=True),
        sa.Column('tool_call_id', sa.String(length=64), nullable=True),
        sa.Column('tool_name', sa.String(length=64), nullable=True),
        sa.Column('tool_result', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])


def downgrade() -> None:
    op.drop_index('ix_chat_messages_session_id', table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index('ix_chat_sessions_user_id', table_name='chat_sessions')
    op.drop_table('chat_sessions')
    sa.Enum(name='chat_role').drop(op.get_bind())

    op.drop_index('ix_user_profiles_user_id', table_name='user_profiles')
    op.drop_table('user_profiles')

    op.drop_column('users', 'chatbot_preemptive_github_suggestions')
    op.drop_column('users', 'chat_provider')
    sa.Enum(name='chat_provider').drop(op.get_bind())

    op.drop_column('users', 'preferred_name')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'middle_name')
    op.drop_column('users', 'first_name')
