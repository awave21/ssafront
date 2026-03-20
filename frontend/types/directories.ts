export type DirectoryColumn = {
  name: string
  label: string
  type: string
  required: boolean
  searchable?: boolean
}

export type Directory = {
  id: string
  agent_id?: string
  name: string
  slug?: string
  tool_name: string
  tool_description?: string
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
  tool_name: string
  tool_description: string
  template: string
  columns?: DirectoryColumn[]
  response_mode?: string
  search_type?: string
}

export type UpdateDirectoryPayload = Partial<{
  name: string
  tool_name: string
  tool_description: string
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
