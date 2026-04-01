export type TableAttributeType =
  | 'text'
  | 'varchar'
  | 'integer'
  | 'float'
  | 'boolean'
  | 'date'
  | 'datetime'
  | 'timestamp'
  | 'text_array'
  | 'number_array'
  | 'json'

export type TableAttribute = {
  id: string
  table_id: string
  name: string
  label: string
  attribute_type: TableAttributeType
  type_config: Record<string, unknown>
  is_required: boolean
  is_searchable: boolean
  is_unique: boolean
  order_index: number
  default_value?: unknown
}

export type TableItem = {
  id: string
  name: string
  description?: string | null
  records_count: number
  attributes_count?: number
  created_at?: string
  updated_at?: string | null
}

export type TableRead = TableItem & {
  tenant_id: string
  is_deleted: boolean
  attributes: TableAttribute[]
}

export type TableCreatePayload = {
  name: string
  description?: string
  attributes: Array<{
    name: string
    label: string
    attribute_type: TableAttributeType
    type_config?: Record<string, unknown>
    is_required?: boolean
    is_searchable?: boolean
    is_unique?: boolean
    order_index?: number
    default_value?: unknown
  }>
}

export type TableRecordRead = {
  id: string
  table_id: string
  data: Record<string, unknown>
  source: string
  created_at: string
  updated_at?: string | null
  is_deleted: boolean
}

export type TableRecordsListResponse = {
  items: TableRecordRead[]
  total: number
  limit: number
  offset: number
}

export type TableRecordsBulkCreateResponse = {
  created: number
  failed: number
  errors: Record<string, unknown>[]
}
