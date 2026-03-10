export const toolParameterTypes = {
  text: 'text',
  number: 'number',
  boolean: 'boolean',
} as const

export type ToolParameterType = (typeof toolParameterTypes)[keyof typeof toolParameterTypes]

export type ToolParameter = {
  id?: string
  name: string
  type: ToolParameterType
  instruction: string
  required: boolean
  optional: boolean
  enum_values?: string[] | null
  default_value?: string | number | boolean | null
  x_from_ai: boolean
  order_index: number
}

export type BackendToolParameter = {
  id?: string
  tenant_id?: string
  tool_id?: string
  name: string
  type: ToolParameterType
  instruction: string
  required: boolean
  is_optional: boolean
  enum_values?: string[] | null
  default_value?: string | number | boolean | null
  x_from_ai: boolean
  order_index: number
  created_at?: string
  updated_at?: string | null
}

export type BackendToolParametersResponse = {
  tool_id: string
  parameters: BackendToolParameter[]
  generated_input_schema: Record<string, any>
}

export type BackendToolParametersUpdateRequest = {
  parameters: BackendToolParameter[]
}

export type BackendToolParametersPreviewRequest = {
  parameters: BackendToolParameter[]
}

export type BackendToolParametersPreviewResponse = {
  input_schema: Record<string, any>
}
