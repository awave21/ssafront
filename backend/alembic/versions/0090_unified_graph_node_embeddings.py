"""Vector embeddings on unified graph nodes (LightRAG-style semantic search).

Revision ID: 0090
Revises: 0089
Create Date: 2026-04-24
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0090"
down_revision: Union[str, None] = "0089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("ALTER TABLE agent_unified_graph_nodes ADD COLUMN IF NOT EXISTS embedding vector(1536);")
    op.execute(
        "ALTER TABLE agent_unified_graph_nodes ADD COLUMN IF NOT EXISTS embedding_content_hash VARCHAR(64);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agent_unified_graph_nodes_embedding_hnsw "
        "ON agent_unified_graph_nodes USING hnsw (embedding vector_cosine_ops) "
        "WHERE (embedding IS NOT NULL)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_agent_unified_graph_nodes_embedding_hnsw;")
    op.execute("ALTER TABLE agent_unified_graph_nodes DROP COLUMN IF EXISTS embedding_content_hash;")
    op.execute("ALTER TABLE agent_unified_graph_nodes DROP COLUMN IF EXISTS embedding;")
