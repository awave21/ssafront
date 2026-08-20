"""Hybrid (ILIKE + pgvector) search over SQNS cache tables.

Добавляет vector-эмбеддинг + content-hash на sqns_services и sqns_resources,
чтобы поиск услуг/специалистов работал по намерению пациента (а не только ILIKE
по имени). Trigram-индексы на name/description уже есть (миграция 0012), поэтому
здесь только vector-столбец + HNSW-индекс (cosine).

Revision ID: 0099
Revises: 0098
Create Date: 2026-07-10
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0099"
down_revision: Union[str, None] = "0098"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # --- sqns_services ---
    op.execute("ALTER TABLE sqns_services ADD COLUMN IF NOT EXISTS embedding vector(1536);")
    op.execute(
        "ALTER TABLE sqns_services ADD COLUMN IF NOT EXISTS embedding_content_hash VARCHAR(64);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sqns_services_embedding_hnsw "
        "ON sqns_services USING hnsw (embedding vector_cosine_ops) "
        "WHERE (embedding IS NOT NULL)"
    )

    # --- sqns_resources ---
    op.execute("ALTER TABLE sqns_resources ADD COLUMN IF NOT EXISTS embedding vector(1536);")
    op.execute(
        "ALTER TABLE sqns_resources ADD COLUMN IF NOT EXISTS embedding_content_hash VARCHAR(64);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sqns_resources_embedding_hnsw "
        "ON sqns_resources USING hnsw (embedding vector_cosine_ops) "
        "WHERE (embedding IS NOT NULL)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_sqns_resources_embedding_hnsw;")
    op.execute("ALTER TABLE sqns_resources DROP COLUMN IF EXISTS embedding_content_hash;")
    op.execute("ALTER TABLE sqns_resources DROP COLUMN IF EXISTS embedding;")

    op.execute("DROP INDEX IF EXISTS ix_sqns_services_embedding_hnsw;")
    op.execute("ALTER TABLE sqns_services DROP COLUMN IF EXISTS embedding_content_hash;")
    op.execute("ALTER TABLE sqns_services DROP COLUMN IF EXISTS embedding;")
