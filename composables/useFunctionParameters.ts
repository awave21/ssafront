/**
 * Composable: body parameters management
 * Handles: CRUD for parameters, sync fields ↔ JSON, schema generation, test payload
 */
import { ref, type Ref } from 'vue'
import type { Tool } from '~/types/tool'
import type { BodyParameter, ParameterType } from '~/utils/function-schema'
import {
  coerceValue,
  getTypeDefault,
  getValidParameters,
  TYPE_SCHEMA_MAP,
} from '~/utils/function-schema'

type FunctionVariable = { name: string; value: string; description: string }

export const generateParameterId = () => `param_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

export const useFunctionParameters = (
  selectedFunction: Ref<Tool | null>,
  variables: Ref<FunctionVariable[]>,
  testPayload: Ref<string>,
  markAsChanged: () => void,
  autoSave: () => void,
) => {
  const bodyParameters = ref<BodyParameter[]>([])
  const bodyJson = ref('{}')
  const bodyViewMode = ref<'fields' | 'json'>('fields')

  // Add parameter
  const addBodyParameter = () => {
    bodyParameters.value.push({
      id: generateParameterId(),
      key: '',
      location: 'body',
      type: 'string',
      value: '',
      fromAI: false,
      aiDescription: '',
      aiDefaultValue: ''
    })
    markAsChanged()
  }

  // Remove parameter
  const removeBodyParameter = (index: number) => {
    bodyParameters.value.splice(index, 1)
    markAsChanged()
    generateInputSchema()
    generateTestPayload()
    autoSave()
  }

  // Update single field
  const updateBodyParameter = (index: number, field: keyof BodyParameter, value: any) => {
    if (!bodyParameters.value[index]) {
      console.warn('updateBodyParameter: parameter at index', index, 'does not exist')
      return
    }
    bodyParameters.value[index] = { ...bodyParameters.value[index], [field]: value }
    onBodyParameterInput()
  }

  // Immediate input handler: keeps unsaved state in sync with blur autosave.
  const onBodyParameterInput = () => {
    markAsChanged()
    generateInputSchema()
    generateTestPayload()
  }

  // Build params object for test payloads
  const buildParamsObject = (params: BodyParameter[], skipPlaceholders = false): Record<string, any> => {
    const obj: Record<string, any> = {}
    params.forEach(param => {
      if (!param.key) return
      if (param.fromAI) {
        obj[param.key] = param.aiDefaultValue
          ? coerceValue(param.aiDefaultValue, param.type)
          : getTypeDefault(param.type)
        return
      }
      if (skipPlaceholders && param.value.startsWith('{{') && param.value.endsWith('}}')) {
        obj[param.key] = ''
        return
      }
      obj[param.key] = coerceValue(param.value, param.type)
    })
    return obj
  }

  // Sync fields → JSON
  const syncFieldsToJson = () => {
    const obj: Record<string, any> = {}
    bodyParameters.value.forEach(param => {
      if (!param.key) return
      if (param.fromAI) {
        const key_ = JSON.stringify(param.key)
        const desc = JSON.stringify(param.aiDescription || '')
        const type_ = JSON.stringify(param.type || 'string')
        const def = param.aiDefaultValue ? JSON.stringify(param.aiDefaultValue) : ''
        const parts = def ? [key_, desc, type_, def] : [key_, desc, type_]
        obj[param.key] = `$fromAI(${parts.join(', ')})`
      } else {
        obj[param.key] = coerceValue(param.value, param.type)
      }
    })
    bodyJson.value = JSON.stringify(obj, null, 2)
  }

  // Parse $fromAI() expression
  const parseFromAIExpression = (expr: string): { key: string; description: string; type: string; defaultValue: string } => {
    const inner = expr.slice('$fromAI('.length, -1)
    const args: string[] = []
    let current = ''
    let inString = false
    let escapeNext = false

    for (const ch of inner) {
      if (escapeNext) { current += ch; escapeNext = false; continue }
      if (ch === '\\') { escapeNext = true; current += ch; continue }
      if (ch === '"') { inString = !inString; current += ch; continue }
      if (ch === ',' && !inString) { args.push(current.trim()); current = ''; continue }
      current += ch
    }
    if (current.trim()) args.push(current.trim())

    const unquote = (s: string) => s.startsWith('"') && s.endsWith('"') ? s.slice(1, -1) : s
    return {
      key: args[0] ? unquote(args[0]) : '',
      description: args[1] ? unquote(args[1]) : '',
      type: args[2] ? unquote(args[2]) : 'string',
      defaultValue: args[3] ? unquote(args[3]) : ''
    }
  }

  // Sync JSON → fields (preserves location from existing params)
  const syncJsonToFields = () => {
    try {
      const parsed = JSON.parse(bodyJson.value)

      // Build a map of existing param locations so we don't lose them
      const prevLocationMap = new Map<string, 'body' | 'path' | 'query'>()
      bodyParameters.value.forEach(p => {
        if (p.key) prevLocationMap.set(p.key, p.location)
      })

      bodyParameters.value = Object.entries(parsed).map(([key, value]) => {
        const prevLocation = prevLocationMap.get(key) ?? 'body'

        if (typeof value === 'string' && value.startsWith('$fromAI(') && value.endsWith(')')) {
          const ai = parseFromAIExpression(value)
          return {
            id: generateParameterId(),
            key,
            location: prevLocation,
            type: (ai.type || 'string') as ParameterType,
            value: '',
            fromAI: true,
            aiDescription: ai.description,
            aiDefaultValue: ai.defaultValue
          }
        }
        let type: ParameterType = 'string'
        let strValue = String(value)
        if (typeof value === 'number') type = 'number'
        else if (typeof value === 'boolean') type = 'boolean'
        else if (Array.isArray(value)) { type = 'array'; strValue = JSON.stringify(value) }
        else if (typeof value === 'object' && value !== null) { type = 'object'; strValue = JSON.stringify(value) }
        return {
          id: generateParameterId(),
          key,
          location: prevLocation,
          type,
          value: strValue,
          fromAI: false,
          aiDescription: '',
          aiDefaultValue: ''
        }
      })
      markAsChanged()
      generateInputSchema()
      generateTestPayload()
    } catch (e) {
      console.error('Invalid JSON', e)
    }
  }

  // Generate test payload (updates shared testPayload ref)
  const generateTestPayload = () => {
    testPayload.value = JSON.stringify(buildParamsObject(bodyParameters.value, true), null, 2)
  }

  // Load from schema
  const loadBodyParametersFromSchema = (func: Tool) => {
    const schema = func.input_schema
    const mapping = func.parameter_mapping

    if (!schema?.properties || Object.keys(schema.properties).length === 0) {
      bodyParameters.value = []
      bodyJson.value = '{}'
      return
    }

    const loadedBodyParams: BodyParameter[] = []
    const loadedVariables: FunctionVariable[] = []

    Object.entries(schema.properties).forEach(([key, propSchema]: [string, any]) => {
      if (propSchema['x-variable'] === true) {
        loadedVariables.push({
          name: key,
          value: propSchema.default !== undefined ? String(propSchema.default) : '',
          description: (propSchema.description || '').replace(/^Variable: /, '')
        })
        return
      }

      const rawType = propSchema.type || 'string'
      const type: ParameterType = rawType === 'integer' ? 'number' : rawType

      if (propSchema['x-fromAI'] === true) {
        loadedBodyParams.push({
          id: generateParameterId(),
          key,
          location: (mapping?.[key] || 'body') as 'body' | 'path' | 'query',
          type,
          value: '',
          fromAI: true,
          aiDescription: propSchema.description || '',
          aiDefaultValue: propSchema.default !== undefined
            ? (typeof propSchema.default === 'string' ? propSchema.default : JSON.stringify(propSchema.default))
            : ''
        })
        return
      }

      let value = ''
      if (propSchema.description?.startsWith('Parameter: ')) {
        const varName = propSchema.description.replace('Parameter: ', '')
        value = `{{${varName}}}`
      } else if (propSchema.default !== undefined) {
        value = typeof propSchema.default === 'string'
          ? propSchema.default
          : JSON.stringify(propSchema.default)
      }

      loadedBodyParams.push({
        id: generateParameterId(),
        key,
        location: (mapping?.[key] || 'body') as 'body' | 'path' | 'query',
        type,
        value,
        fromAI: false,
        aiDescription: '',
        aiDefaultValue: ''
      })
    })

    bodyParameters.value = loadedBodyParams
    if (loadedVariables.length > 0) variables.value = loadedVariables
    syncFieldsToJson()
  }

  // Generate input schema
  const generateInputSchema = () => {
    if (!selectedFunction.value) return

    type SchemaProperty = {
      type: ParameterType
      description?: string
      default?: any
      'x-fromAI'?: boolean
      'x-variable'?: boolean
      items?: { type: string }
    }

    const properties: Record<string, SchemaProperty> = {}
    const required: string[] = []
    const parameterMapping: Record<string, 'path' | 'query' | 'body'> = {}

    getValidParameters(bodyParameters.value).forEach(param => {
      const schema: SchemaProperty = { ...TYPE_SCHEMA_MAP[param.type] }
      if (param.fromAI) {
        schema.description = param.aiDescription || `Value for ${param.key}`
        schema['x-fromAI'] = true
        if (param.aiDefaultValue) schema.default = coerceValue(param.aiDefaultValue, param.type)
        required.push(param.key)
      } else if (param.value) {
        if (param.value.startsWith('{{') && param.value.endsWith('}}')) {
          schema.description = `Parameter: ${param.value.slice(2, -2)}`
        } else {
          schema.default = coerceValue(param.value, param.type)
        }
      }
      properties[param.key] = schema
      parameterMapping[param.key] = param.location
      if (!param.fromAI && param.value && !param.value.startsWith('{{')) required.push(param.key)
    })

    variables.value.forEach(v => {
      const name = v.name.trim()
      if (!name) return
      properties[name] = {
        type: 'string',
        description: v.description || `Variable: ${name}`,
        'x-variable': true,
        'x-fromAI': true,
        ...(v.value ? { default: v.value } : {})
      }
    })

    const prevSchema = selectedFunction.value.input_schema || {}
    selectedFunction.value.input_schema = {
      type: 'object',
      properties,
      ...(required.length > 0 ? { required } : {}),
      ...(prevSchema._displayName ? { _displayName: prevSchema._displayName } : {})
    }

    selectedFunction.value.parameter_mapping = Object.keys(parameterMapping).length > 0
      ? parameterMapping
      : null

    markAsChanged()
  }

  return {
    bodyParameters,
    bodyJson,
    bodyViewMode,
    addBodyParameter,
    removeBodyParameter,
    updateBodyParameter,
    onBodyParameterInput,
    buildParamsObject,
    syncFieldsToJson,
    syncJsonToFields,
    generateTestPayload,
    loadBodyParametersFromSchema,
    generateInputSchema,
    parseFromAIExpression,
  }
}
