"""Enable pgvector and migrate embedding column to vector type

Revision ID: 0018_pgvector_embedding
Revises: 0017_directories
Create Date: 2026-02-05
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_pgvector_embedding"
down_revision = "0017_directories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    # Drop old embedding column (BYTEA) and create new one (vector)
    # First, drop the old column
    op.drop_column("directory_items", "embedding")
    
    # Add new embedding column as vector(1536) for OpenAI text-embedding-3-small
    op.execute("""
        ALTER TABLE directory_items 
        ADD COLUMN embedding vector(1536);
    """)
    
    # Create index for fast vector search (IVFFlat or HNSW)
    # Using HNSW for better recall
    op.execute("""
        CREATE INDEX idx_directory_items_embedding 
        ON directory_items 
        USING hnsw (embedding vector_cosine_ops);
    """)


def downgrade() -> None:
    # Drop the vector index
    op.execute("DROP INDEX IF EXISTS idx_directory_items_embedding;")
    
    # Drop vector column and recreate as BYTEA
    op.drop_column("directory_items", "embedding")
    op.add_column(
        "directory_items",
        sa.Column("embedding", sa.LargeBinary, nullable=True)
    )
    
    # Note: We don't drop the vector extension as other tables might use it
