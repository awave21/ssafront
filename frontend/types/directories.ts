export type DirectoryColumn = {
  name: string
  label: string
  type: string
  required: boolean
  searchable?: boolean
  /** Для type === 'select' */
  options?: string[]
  /** Для type === 'text' (varchar): максимальное количество символов */
  maxLength?: number
}

export type Directory = {
  id: string
  agent_id?: string
  name: string
  slug?: string
  tool_name: string
  tool_description?: string
  /** Текст для системного промпта агента */
  prompt_usage_snippet?: string | null
  template: string
  columns: DirectoryColumn[]
  response_mode?: 'function_result' | 'direct_message'
  search_type?: 'exact' | 'fuzzy' | 'semantic'
  is_enabled: boolean
  items_count: number
  created_at?: string
  updated_at?: string
}

export type DirectoryItem = {
  id: string
  directory_id?: string
  data: Record<string, any>
  created_at?: string
  updated_at?: string
}

export type CreateDirectoryPayload = {
  name: string
  tool_name?: string
  tool_description: string
  prompt_usage_snippet?: string
  template: string
  columns?: DirectoryColumn[]
  response_mode?: string
  search_type?: string
  create_tool?: boolean
}

export type UpdateDirectoryPayload = Partial<{
  name: string
  tool_name: string
  tool_description: string
  prompt_usage_snippet: string
  response_mode: string
  search_type: string
  is_enabled: boolean
  columns: DirectoryColumn[]
}>

export type ImportResult = {
  created: number
  skipped?: number
  errors?: { row: number; error: string }[]
  total?: number
}

export type ColumnDefinition = {
  id?: string
  name: string
  label: string
  type: string
  required: boolean
  searchable: boolean
}
