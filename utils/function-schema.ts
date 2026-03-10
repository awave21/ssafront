/**
 * Utility functions and constants for function schema management
 */

// Regular expressions for variable tokens
export const VARIABLE_REGEX = /\{\{[a-zA-Z0-9_]+\}\}/g
const VARIABLE_TEST_REGEX = /\{\{[a-zA-Z0-9_]+\}\}/
export const VARIABLE_TOKEN_REGEX = /^\{\{[a-zA-Z0-9_]+\}\}$/

/**
 * Type definitions
 */
export type ParameterType = 'string' | 'number' | 'boolean' | 'array' | 'object'
export type ParameterLocation = 'body' | 'path' | 'query'

export type BodyParameter = {
  id: string  // Unique ID for v-for key
  key: string
  location: ParameterLocation
  type: ParameterType
  value: string
  fromAI: boolean
  aiDescription: string
  aiDefaultValue: string
}

export type JSONSchemaProperty = {
  type: ParameterType
  description?: string
  default?: any
  'x-fromAI'?: boolean
  'x-variable'?: boolean
  items?: { type: string }
}

/**
 * Type to JSON Schema mapping
 */
export const TYPE_SCHEMA_MAP: Record<ParameterType, JSONSchemaProperty> = {
  string: { type: 'string' },
  number: { type: 'number' },
  boolean: { type: 'boolean' },
  array: { type: 'array', items: { type: 'string' } },
  object: { type: 'object' }
}

/**
 * Get default value for a given type
 */
export const getTypeDefault = (type: ParameterType): any => {
  switch (type) {
    case 'number': return 0
    case 'boolean': return false
    case 'array': return []
    case 'object': return {}
    default: return ''
  }
}

/**
 * Coerce string value to the correct JS type
 */
export const coerceValue = (value: string, type: ParameterType): any => {
  if (value.startsWith('{{') && value.endsWith('}}')) return value
  
  switch (type) {
    case 'number':
      return Number(value) || 0
    case 'boolean':
      return value === 'true' || value === '1'
    case 'array':
      try { return JSON.parse(value) } catch { return [] }
    case 'object':
      try { return JSON.parse(value) } catch { return {} }
    default:
      return value
  }
}

/**
 * Check if string contains variable tokens
 */
export const hasVariables = (text: string): boolean => 
  VARIABLE_TEST_REGEX.test(text || '')

/**
 * Split text into segments: plain text vs {{variable}} tokens
 */
export const splitByVars = (text: string): Array<{ text: string; isVar: boolean }> => {
  if (!text) return []
  const parts = text.split(/(\{\{[a-zA-Z0-9_]+\}\})/)
  return parts.filter(Boolean).map(p => ({
    text: p,
    isVar: VARIABLE_TOKEN_REGEX.test(p)
  }))
}

/**
 * Resolve variable tokens in a string
 */
export const resolveVariableTokens = (
  input: string,
  varMap: Record<string, string>
): string =>
  (input || '').replace(VARIABLE_REGEX, (match) => {
    const varName = match.slice(2, -2)
    return Object.prototype.hasOwnProperty.call(varMap, varName) ? varMap[varName] : match
  }
  )

/**
 * Resolve variables deeply in nested structures
 */
export const resolveVariablesDeep = (
  value: any,
  varMap: Record<string, string>
): any => {
  if (typeof value === 'string') return resolveVariableTokens(value, varMap)
  if (Array.isArray(value)) return value.map((item) => resolveVariablesDeep(item, varMap))
  if (value && typeof value === 'object') {
    const out: Record<string, any> = {}
    Object.entries(value).forEach(([k, v]) => {
      out[k] = resolveVariablesDeep(v, varMap)
    })
    return out
  }
  return value
}

/**
 * Filter out parameters without keys
 */
export const getValidParameters = (params: BodyParameter[]): BodyParameter[] =>
  params.filter(p => p.key)
