"""add system integer id attribute to all user tables

Revision ID: 0065
Revises: 0064
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_tables", sa.Column("next_row_id", sa.Integer(), nullable=False, server_default="1"))

    op.execute(
        """
        INSERT INTO user_table_attributes (
            id, table_id, tenant_id, name, label, attribute_type, type_config,
            is_required, is_searchable, is_unique, order_index, default_value,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            t.id,
            t.tenant_id,
            'id',
            'ID',
            'integer',
            '{}'::jsonb,
            true,
            false,
            true,
            0,
            NULL,
            NOW(),
            NULL
        FROM user_tables t
        WHERE t.is_deleted = false
          AND NOT EXISTS (
              SELECT 1
              FROM user_table_attributes a
              WHERE a.table_id = t.id
                AND a.name = 'id'
          );
        """
    )

    op.execute(
        """
        WITH ranked AS (
          SELECT
            r.id AS record_id,
            r.table_id,
            row_number() OVER (
              PARTITION BY r.table_id
              ORDER BY r.created_at ASC, r.id ASC
            ) AS seq_id
          FROM user_table_records r
        )
        UPDATE user_table_records r
        SET data = jsonb_set(
            r.data,
            '{id}',
            to_jsonb(ranked.seq_id),
            true
        )
        FROM ranked
        WHERE r.id = ranked.record_id
          AND (r.data ->> 'id') IS NULL;
        """
    )

    op.execute(
        """
        UPDATE user_tables t
        SET next_row_id = COALESCE(max_values.max_id, 0) + 1
        FROM (
          SELECT
            r.table_id,
            MAX((r.data ->> 'id')::int) AS max_id
          FROM user_table_records r
          WHERE (r.data ->> 'id') ~ '^[0-9]+$'
          GROUP BY r.table_id
        ) AS max_values
        WHERE t.id = max_values.table_id;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM user_table_attributes
        WHERE name = 'id'
          AND attribute_type = 'integer';
        """
    )
    op.drop_column("user_tables", "next_row_id")
