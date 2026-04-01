"""user tables storage

Revision ID: 0063
Revises: 0062
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_tables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("records_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_tables_tenant_id", "user_tables", ["tenant_id"])

    op.create_table(
        "user_table_attributes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("attribute_type", sa.String(50), nullable=False),
        sa.Column("type_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_searchable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_unique", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("default_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("table_id", "name", name="uq_user_table_attribute_name"),
    )
    op.create_index("ix_user_table_attributes_table_id", "user_table_attributes", ["table_id"])
    op.create_index("ix_user_table_attributes_tenant_id", "user_table_attributes", ["tenant_id"])

    op.create_table(
        "user_table_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("table_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("source", sa.String(50), nullable=False, server_default="admin"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("ALTER TABLE user_table_records ADD COLUMN embedding vector(1536);")
    op.create_index("ix_user_table_records_table_id", "user_table_records", ["table_id"])
    op.create_index("ix_user_table_records_tenant_id", "user_table_records", ["tenant_id"])

    op.execute(
        """
        CREATE INDEX ix_user_table_records_data_gin
        ON user_table_records USING gin(data);
        """
    )
    op.execute(
        """
        CREATE INDEX ix_user_table_records_data_fts
        ON user_table_records
        USING gin(to_tsvector('russian', data::text));
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_user_table_records_count()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.is_deleted = false THEN
                    UPDATE user_tables
                    SET records_count = records_count + 1, updated_at = NOW()
                    WHERE id = NEW.table_id;
                END IF;
            ELSIF TG_OP = 'UPDATE' THEN
                IF OLD.is_deleted = false AND NEW.is_deleted = true THEN
                    UPDATE user_tables
                    SET records_count = GREATEST(records_count - 1, 0), updated_at = NOW()
                    WHERE id = NEW.table_id;
                ELSIF OLD.is_deleted = true AND NEW.is_deleted = false THEN
                    UPDATE user_tables
                    SET records_count = records_count + 1, updated_at = NOW()
                    WHERE id = NEW.table_id;
                END IF;
            ELSIF TG_OP = 'DELETE' THEN
                IF OLD.is_deleted = false THEN
                    UPDATE user_tables
                    SET records_count = GREATEST(records_count - 1, 0), updated_at = NOW()
                    WHERE id = OLD.table_id;
                END IF;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trigger_user_table_records_count
        AFTER INSERT OR UPDATE OR DELETE ON user_table_records
        FOR EACH ROW EXECUTE FUNCTION update_user_table_records_count();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trigger_user_table_records_count ON user_table_records;")
    op.execute("DROP FUNCTION IF EXISTS update_user_table_records_count();")
    op.execute("DROP INDEX IF EXISTS ix_user_table_records_data_fts;")
    op.execute("DROP INDEX IF EXISTS ix_user_table_records_data_gin;")
    op.drop_table("user_table_records")
    op.drop_table("user_table_attributes")
    op.drop_table("user_tables")
