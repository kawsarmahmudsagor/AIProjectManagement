"""replace ollama provider with openai

Revision ID: 46f852e48df7
Revises: d4e1a9c2f6b8
Create Date: 2026-09-02 11:50:12.523317

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '46f852e48df7'
down_revision: Union[str, None] = 'd4e1a9c2f6b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres enum values can't be dropped, but they can be renamed in-place
    # (transaction-safe, unlike ADD VALUE). Every row currently set to OLLAMA was
    # configured for Ollama specifically, so after the rename its base_url/model/key
    # are cleared below rather than left masquerading as a working OpenAI config.
    op.execute("ALTER TYPE provider_name RENAME VALUE 'OLLAMA' TO 'OPENAI'")
    op.execute("ALTER TYPE chat_provider RENAME VALUE 'OLLAMA' TO 'OPENAI'")
    op.execute(
        "UPDATE ai_provider_settings "
        "SET base_url = NULL, default_model = NULL, encrypted_api_key = NULL, is_default = false "
        "WHERE provider = 'OPENAI'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE ai_provider_settings "
        "SET base_url = 'http://localhost:11434', default_model = 'gemma4:e2b', is_default = false "
        "WHERE provider = 'OPENAI'"
    )
    op.execute("ALTER TYPE chat_provider RENAME VALUE 'OPENAI' TO 'OLLAMA'")
    op.execute("ALTER TYPE provider_name RENAME VALUE 'OPENAI' TO 'OLLAMA'")
