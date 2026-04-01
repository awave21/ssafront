"""add system created_at attribute to all user tables

Revision ID: 0064
Revises: 0063
Create Date: 2026-03-27
"""

from alembic import op

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
            'created_at',
            'Дата создания',
            'timestamp',
            '{}'::jsonb,
            true,
            false,
            false,
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
                AND a.name = 'created_at'
          );
        """
    )

    op.execute(
        """
        UPDATE user_table_records r
        SET data = jsonb_set(
            r.data,
            '{created_at}',
            to_jsonb(to_char(r.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')),
            true
        )
        WHERE (r.data ->> 'created_at') IS NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM user_table_attributes
        WHERE name = 'created_at'
          AND attribute_type = 'timestamp';
        """
    )
