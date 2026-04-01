import type { TableAttributeType } from '~/types/tables'

export type TableAttributeTypeMeta = {
  value: TableAttributeType
  /** Compact UI label (select, chips) */
  label: string
  /** How the value looks in JSON / API */
  syntax: string
  /** Tooltip / documentation text */
  hint: string
}

/** Order matches table configuration forms */
export const TABLE_ATTRIBUTE_TYPE_METAS: TableAttributeTypeMeta[] = [
  {
    value: 'text',
    label: 'text',
    syntax: 'text',
    hint: 'PostgreSQL text — unlimited-length string. Shown as a multiline editor in forms. For short fields use Varchar (length limit).',
  },
  {
    value: 'varchar',
    label: 'varchar',
    syntax: 'varchar(n)',
    hint: 'Length-limited string — PostgreSQL varchar(n). Limit is in type_config.max_length (default 256). Rendered as a single-line field.',
  },
  {
    value: 'integer',
    label: 'int',
    syntax: 'integer',
    hint: 'Whole number, no fractional part. In JSON, a number without quotes. PostgreSQL integer.',
  },
  {
    value: 'float',
    label: 'float',
    syntax: 'double precision',
    hint: 'IEEE 754 64-bit floating point. PostgreSQL double precision.',
  },
  {
    value: 'boolean',
    label: 'bool',
    syntax: 'boolean',
    hint: 'True or false: true/false in JSON. PostgreSQL boolean.',
  },
  {
    value: 'date',
    label: 'date',
    syntax: 'date',
    hint: 'Calendar date without time — PostgreSQL date. Stored in JSONB as an ISO 8601 string (YYYY-MM-DD).',
  },
  {
    value: 'datetime',
    label: 'datetime',
    syntax: 'timestamp with time zone',
    hint: 'Instant with timezone — PostgreSQL timestamptz. Serialized in JSONB as an ISO 8601 string (e.g. 2024-06-01T12:00:00Z).',
  },
  {
    value: 'timestamp',
    label: 'timestamp',
    syntax: 'timestamp with time zone',
    hint: 'UTC date/time — PostgreSQL timestamptz. Usually set automatically by the server (e.g. created_at). ISO 8601 string in JSONB.',
  },
  {
    value: 'text_array',
    label: 'array(text)',
    syntax: 'text[]',
    hint: 'Ordered list of strings. Stored as PostgreSQL text[].',
  },
  {
    value: 'number_array',
    label: 'array (int)',
    syntax: 'double precision[]',
    hint: 'List of floating-point numbers. Stored as PostgreSQL double precision[].',
  },
  {
    value: 'json',
    label: 'json',
    syntax: 'jsonb',
    hint: 'Arbitrary structure: object, array, or scalar. Stored as PostgreSQL jsonb.',
  },
]

const metaByValue = new Map<TableAttributeType, TableAttributeTypeMeta>(
  TABLE_ATTRIBUTE_TYPE_METAS.map((m) => [m.value, m])
)

export const getTableAttributeTypeMeta = (t: TableAttributeType): TableAttributeTypeMeta => {
  const m = metaByValue.get(t)
  if (m) return m
  return {
    value: t,
    label: t,
    syntax: t,
    hint: 'Column data type.',
  }
}

/** Select option text — compact label only */
export const tableAttributeTypeSelectLabel = (m: TableAttributeTypeMeta) => m.label
