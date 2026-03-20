export const functionRuleActionTypes = {
  setTag: 'set_tag',
  sendMessage: 'send_message',
  webhook: 'webhook',
  pauseDialog: 'pause_dialog',
  augmentPrompt: 'augment_prompt',
  setResult: 'set_result',
  noop: 'noop',
} as const

export type FunctionRuleActionType = (typeof functionRuleActionTypes)[keyof typeof functionRuleActionTypes]

export const functionRuleActionStatuses = {
  success: 'success',
  error: 'error',
  always: 'always',
} as const

export type FunctionRuleActionStatus = (typeof functionRuleActionStatuses)[keyof typeof functionRuleActionStatuses]

export type BackendFunctionRuleActionType = FunctionRuleActionType
export type BackendFunctionRuleActionStatus = FunctionRuleActionStatus

export type BackendFunctionRuleAction = {
  id: string
  tenant_id: string
  rule_id: string
  action_type: BackendFunctionRuleActionType
  action_config: Record<string, any>
  on_status: BackendFunctionRuleActionStatus
  order_index: number
  enabled: boolean
  created_at?: string
  updated_at?: string | null
}

export type BackendFunctionRuleActionPayload = {
  action_type: BackendFunctionRuleActionType
  action_config: Record<string, any>
  on_status: BackendFunctionRuleActionStatus
  order_index: number
  enabled: boolean
}

export type FunctionRuleAction = {
  id: string
  rule_id: string
  action_type: FunctionRuleActionType
  on_status: FunctionRuleActionStatus
  enabled: boolean
  order_index: number
  config: Record<string, any>
  created_at?: string
  updated_at?: string
}

export type FunctionRuleActionPayload = Omit<
  FunctionRuleAction,
  'id' | 'rule_id' | 'created_at' | 'updated_at'
>

const normalizeActionConfigFromBackend = (
  actionType: BackendFunctionRuleActionType,
  config: Record<string, any> | null | undefined,
): Record<string, any> => {
  const source = { ...(config || {}) }

  if (actionType === 'augment_prompt' && source.instruction && !source.prompt) {
    source.prompt = source.instruction
  }

  if (actionType === 'set_result' && source.result != null && source.value == null) {
    source.value = source.result
  }

  return source
}

const normalizeActionConfigToBackend = (
  actionType: FunctionRuleActionType,
  config: Record<string, any> | null | undefined,
): Record<string, any> => {
  const source = { ...(config || {}) }

  if (actionType === 'augment_prompt') {
    const instruction = String(source.instruction ?? source.prompt ?? '').trim()
    return {
      ...source,
      instruction,
    }
  }

  if (actionType === 'set_result') {
    const result = source.result ?? source.value ?? ''
    return {
      ...source,
      result,
    }
  }

  return source
}

export const mapRuleActionFromBackend = (action: BackendFunctionRuleAction): FunctionRuleAction => ({
  id: action.id,
  rule_id: action.rule_id,
  action_type: action.action_type,
  on_status: action.on_status,
  enabled: action.enabled,
  order_index: action.order_index,
  config: normalizeActionConfigFromBackend(action.action_type, action.action_config),
  created_at: action.created_at,
  updated_at: action.updated_at || undefined,
})

export const mapRuleActionPayloadToBackend = (
  payload: FunctionRuleActionPayload,
): BackendFunctionRuleActionPayload => ({
  action_type: payload.action_type,
  action_config: normalizeActionConfigToBackend(payload.action_type, payload.config),
  on_status: payload.on_status,
  enabled: payload.enabled,
  order_index: payload.order_index,
})
