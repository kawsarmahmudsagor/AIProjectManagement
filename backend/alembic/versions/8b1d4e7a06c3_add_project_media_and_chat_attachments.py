"""add project media, thumbnail jobs, and chat attachments

Revision ID: 8b1d4e7a06c3
Revises: c9b5f3a7e1d6
Create Date: 2026-09-10 00:00:00.000000

Binary payloads are stored in Postgres as bytea, not on disk — a deliberate departure
from services/document_service.py and services/profile_service.py, so media travels with
the database and there is no second backup surface and no orphaned-file cleanup path.
Three things in here make that affordable, and all three are load-bearing:

1. Bytes live in their own tables (project_media_blobs, chat_attachment_blobs), one row
   per parent, so "read the metadata" and "read the bytes" are physically different
   queries. See models/project_media.py's docstring.
2. `ALTER COLUMN data SET STORAGE EXTERNAL` on both blob columns. This is the single most
   important line in this migration: with the default EXTENDED storage Postgres
   *compresses* the value, and a compressed TOAST value cannot be sliced — every
   `substring(data from N for L)` would decompress the whole thing, defeating the HTTP
   Range streaming that keeps a large video out of the API process's memory. Video, JPEG,
   PNG and WEBP are already compressed, so EXTERNAL gives up nothing.
3. uq_project_media_project_kind: at most one thumbnail and one video per project, which
   makes the upload endpoints an idempotent PUT rather than an insert that can race.

thumbnail_jobs reuses the existing `job_status` TYPE with create_type=False (same as
9a2f6c1d8e4b did for breakdown_jobs) — a new enum would fail with "type job_status
already exists" and would also break the stale-job reaper and the cancel endpoint, which
are written against JobStatus.

Enum value literals are UPPERCASE because SQLAlchemy's Enum(StrEnum) persists member
*names*, not values — the same reason 9a2f6c1d8e4b writes 'QUEUED', not 'queued'.
Getting this wrong produces a schema that alembic accepts and create_all-based tests
(tests/conftest.py:63-68) silently disagree with.

Note: Base.metadata.create_all (used by the test suite) never emits `SET STORAGE
EXTERNAL` — it isn't part of SQLAlchemy's Column model. Test databases therefore have
EXTENDED (compressed) blob columns: correct byte-for-byte results from substring(), but
without the performance property this migration exists to provide. Don't infer from a
green test suite that production is configured this way.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '8b1d4e7a06c3'
down_revision: Union[str, None] = 'c9b5f3a7e1d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Created explicitly, once, up front — then referenced below with create_type=False
    # so op.create_table's DDL compiler doesn't also try to CREATE TYPE as a side effect
    # of compiling the column (postgresql.ENUM defaults to create_type=True, which would
    # otherwise attempt a second, duplicate CREATE TYPE for the same name).
    postgresql.ENUM('THUMBNAIL', 'VIDEO', name='media_kind').create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('UPLOADED', 'GENERATED', name='media_origin').create(op.get_bind(), checkfirst=False)
    postgresql.ENUM('IMAGE', 'DOCUMENT', name='attachment_kind').create(op.get_bind(), checkfirst=False)

    media_kind = postgresql.ENUM('THUMBNAIL', 'VIDEO', name='media_kind', create_type=False)
    media_origin = postgresql.ENUM('UPLOADED', 'GENERATED', name='media_origin', create_type=False)
    attachment_kind = postgresql.ENUM('IMAGE', 'DOCUMENT', name='attachment_kind', create_type=False)

    # Reused, never created here — see the module docstring.
    job_status = postgresql.ENUM(
        'QUEUED', 'PARSING', 'EXTRACTING', 'STRUCTURING', 'SUCCEEDED', 'FAILED', 'CANCELLED',
        name='job_status', create_type=False,
    )
    provider_name = postgresql.ENUM('GEMINI', 'OPENAI', name='provider_name', create_type=False)

    # ---- project media -------------------------------------------------------------
    op.create_table(
        'project_media',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('kind', media_kind, nullable=False),
        sa.Column('origin', media_origin, nullable=False, server_default='UPLOADED'),
        sa.Column('generator', sa.String(length=32), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=255), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('project_id', 'kind', name='uq_project_media_project_kind'),
    )
    op.create_index('ix_project_media_user_id', 'project_media', ['user_id'])
    op.create_index('ix_project_media_project_id', 'project_media', ['project_id'])

    op.create_table(
        'project_media_blobs',
        sa.Column('media_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(['media_id'], ['project_media.id'], ondelete='CASCADE'),
    )
    op.execute('ALTER TABLE project_media_blobs ALTER COLUMN data SET STORAGE EXTERNAL')

    # ---- thumbnail jobs ------------------------------------------------------------
    op.create_table(
        'thumbnail_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', provider_name, nullable=False),
        sa.Column('status', job_status, nullable=False, server_default='QUEUED'),
        sa.Column('media_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('generator', sa.String(length=32), nullable=True),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['media_id'], ['project_media.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_thumbnail_jobs_user_id', 'thumbnail_jobs', ['user_id'])
    op.create_index('ix_thumbnail_jobs_project_id', 'thumbnail_jobs', ['project_id'])
    op.create_index('ix_thumbnail_jobs_status', 'thumbnail_jobs', ['status'])

    # ---- chat attachments ----------------------------------------------------------
    op.create_table(
        'chat_attachments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('kind', attachment_kind, nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=255), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('text_truncated', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_chat_attachments_user_id', 'chat_attachments', ['user_id'])
    op.create_index('ix_chat_attachments_session_id', 'chat_attachments', ['session_id'])
    # Replay (services/chat_service._load_attachment_payloads) selects by message_id IN
    # (...) on every turn — this index is not optional.
    op.create_index('ix_chat_attachments_message_id', 'chat_attachments', ['message_id'])

    op.create_table(
        'chat_attachment_blobs',
        sa.Column('attachment_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(['attachment_id'], ['chat_attachments.id'], ondelete='CASCADE'),
    )
    op.execute('ALTER TABLE chat_attachment_blobs ALTER COLUMN data SET STORAGE EXTERNAL')


def downgrade() -> None:
    op.drop_table('chat_attachment_blobs')
    op.drop_index('ix_chat_attachments_message_id', table_name='chat_attachments')
    op.drop_index('ix_chat_attachments_session_id', table_name='chat_attachments')
    op.drop_index('ix_chat_attachments_user_id', table_name='chat_attachments')
    op.drop_table('chat_attachments')

    op.drop_index('ix_thumbnail_jobs_status', table_name='thumbnail_jobs')
    op.drop_index('ix_thumbnail_jobs_project_id', table_name='thumbnail_jobs')
    op.drop_index('ix_thumbnail_jobs_user_id', table_name='thumbnail_jobs')
    op.drop_table('thumbnail_jobs')

    op.drop_table('project_media_blobs')
    op.drop_index('ix_project_media_project_id', table_name='project_media')
    op.drop_index('ix_project_media_user_id', table_name='project_media')
    op.drop_table('project_media')

    # job_status / provider_name are shared with other tables — never dropped here.
    postgresql.ENUM(name='attachment_kind').drop(op.get_bind())
    postgresql.ENUM(name='media_origin').drop(op.get_bind())
    postgresql.ENUM(name='media_kind').drop(op.get_bind())
