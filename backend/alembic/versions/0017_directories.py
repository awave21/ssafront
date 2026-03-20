"""Справочники (Directories) - структурированные данные как tools агента

Revision ID: 0017_directories
Revises: 0016_telegram_webhook_secret
Create Date: 2026-02-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017_directories"
down_revision = "0016_telegram_webhook_secret"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Включаем расширение pg_trgm для нечёткого поиска
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    
    # Создаём ENUM типы
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE directory_template AS ENUM (
                'qa', 'service_catalog', 'product_catalog', 'company_info', 'custom'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE directory_response_mode AS ENUM (
                'function_result', 'direct_message'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE directory_search_type AS ENUM (
                'exact', 'fuzzy', 'semantic'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    
    # Создаём таблицу directories
    op.create_table(
        "directories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True),
        
        # Основные поля
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("tool_description", sa.Text, nullable=True),
        
        # Шаблон и структура
        sa.Column("template", postgresql.ENUM("qa", "service_catalog", "product_catalog", "company_info", "custom", name="directory_template", create_type=False), nullable=False, server_default="custom"),
        sa.Column("columns", postgresql.JSONB, nullable=False, server_default="[]"),
        
        # Настройки поведения
        sa.Column("response_mode", postgresql.ENUM("function_result", "direct_message", name="directory_response_mode", create_type=False), nullable=False, server_default="function_result"),
        sa.Column("search_type", postgresql.ENUM("exact", "fuzzy", "semantic", name="directory_search_type", create_type=False), nullable=False, server_default="fuzzy"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        
        # Метаданные
        sa.Column("items_count", sa.Integer, nullable=False, server_default="0"),
        
        # Timestamps и soft delete
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        
        # Уникальные ограничения
        sa.UniqueConstraint("agent_id", "slug", name="uq_directories_agent_slug"),
        sa.UniqueConstraint("agent_id", "tool_name", name="uq_directories_agent_tool_name"),
    )
    
    # Создаём таблицу directory_items
    # Используем BYTEA для embedding (без зависимости от pgvector)
    op.create_table(
        "directory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("directory_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("directories.id", ondelete="CASCADE"), nullable=False, index=True),
        
        sa.Column("data", postgresql.JSONB, nullable=False, server_default="{}"),
        # Embedding хранится как BYTEA (JSON-сериализованный массив float)
        # Если pgvector установлен, можно мигрировать на vector(1536) позже
        sa.Column("embedding", sa.LargeBinary, nullable=True),
        
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # Создаём индекс для полнотекстового поиска по data
    op.execute("""
        CREATE INDEX idx_directory_items_data_fts ON directory_items 
        USING gin(to_tsvector('russian', data::text));
    """)
    
    # Создаём триггер для автоматического обновления items_count
    op.execute("""
        CREATE OR REPLACE FUNCTION update_directory_items_count()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE directories SET items_count = items_count + 1, updated_at = NOW()
                WHERE id = NEW.directory_id;
            ELSIF TG_OP = 'DELETE' THEN
                UPDATE directories SET items_count = items_count - 1, updated_at = NOW()
                WHERE id = OLD.directory_id;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER trigger_directory_items_count
        AFTER INSERT OR DELETE ON directory_items
        FOR EACH ROW EXECUTE FUNCTION update_directory_items_count();
    """)


def downgrade() -> None:
    # Удаляем триггер и функцию
    op.execute("DROP TRIGGER IF EXISTS trigger_directory_items_count ON directory_items;")
    op.execute("DROP FUNCTION IF EXISTS update_directory_items_count();")
    
    # Удаляем индексы (если существуют)
    op.execute("DROP INDEX IF EXISTS idx_directory_items_data_fts;")
    
    # Удаляем таблицы
    op.drop_table("directory_items")
    op.drop_table("directories")
    
    # Удаляем ENUM типы
    op.execute("DROP TYPE IF EXISTS directory_search_type;")
    op.execute("DROP TYPE IF EXISTS directory_response_mode;")
    op.execute("DROP TYPE IF EXISTS directory_template;")
