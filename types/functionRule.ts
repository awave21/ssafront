import {
  mapRuleActionFromBackend,
  type BackendFunctionRuleAction,
  type FunctionRuleAction,
} from '~/types/ruleAction'

export const functionRuleConditionTypes = {
  keywords: 'keywords',
  regex: 'regex',
  semantic: 'semantic',
  jsonContext: 'json_context',
  always: 'always',
} as const

export type FunctionRuleConditionType = (typeof functionRuleConditionTypes)[keyof typeof functionRuleConditionTypes]

export const functionReactionModes = {
  sendMessage: 'send_message',
  aiInstruction: 'ai_instruction',
  aiSelfReply: 'ai_self_reply',
  silent: 'silent',
} as const

export type FunctionReactionMode = (typeof functionReactionModes)[keyof typeof functionReactionModes]

export const functionPostScenarios = {
  continue: 'continue',
  pause: 'pause',
  augmentPrompt: 'augment_prompt',
} as const

export type FunctionPostScenario = (typeof functionPostScenarios)[keyof typeof functionPostScenarios]

export type SemanticConditionConfig = {
  semantic_threshold: number
  intent: string
  examples: string[]
}

export type KeywordConditionConfig = {
  keywords: string[]
}

export type RegexConditionConfig = {
  pattern: string
  flags?: string
}

export type FunctionRuleConditionConfig =
  | SemanticConditionConfig
  | KeywordConditionConfig
  | RegexConditionConfig
  | Record<string, any>

export type FunctionRule = {
  id: string
  agent_id: string
  name: string
  enabled: boolean
  dry_run: boolean
  stop_on_match: boolean
  allow_semantic: boolean
  priority: number
  trigger_mode: 'pre_run' | 'post_tool' | 'post_run' | null
  condition_type: FunctionRuleConditionType
  condition_config: FunctionRuleConditionConfig
  tool_id?: string | null
  reaction_mode: FunctionReactionMode
  reaction_message?: string | null
  reaction_instruction?: string | null
  post_scenario: FunctionPostScenario
  post_scenario_prompt?: string | null
  actions?: FunctionRuleAction[]
  updated_at?: string
  created_at?: string
}

export type FunctionRuleUpsertPayload = Omit<
  FunctionRule,
  'id' | 'agent_id' | 'updated_at' | 'created_at' | 'actions'
>

export type BackendFunctionRuleConditionType =
  | 'keyword'
  | 'regex'
  | 'semantic'
  | 'json_context'
  | 'always'

export type BackendFunctionRuleTriggerMode = 'pre_run' | 'post_tool' | 'post_run'

export type BackendFunctionRuleReactionMode = FunctionReactionMode

export type BackendFunctionRuleBehaviorMode = FunctionPostScenario

export type BackendFunctionRule = {
  id: string
  tenant_id: string
  agent_id: string
  name: string
  enabled: boolean
  dry_run: boolean
  stop_on_match: boolean
  allow_semantic: boolean
  priority: number
  trigger_mode: BackendFunctionRuleTriggerMode
  condition_type: BackendFunctionRuleConditionType
  condition_config: Record<string, any>
  tool_id: string | null
  reaction_to_execution: BackendFunctionRuleReactionMode
  behavior_after_execution: BackendFunctionRuleBehaviorMode
  actions: BackendFunctionRuleAction[]
  created_at?: string
  updated_at?: string | null
}

export type BackendFunctionRulePayload = {
  name: string
  enabled: boolean
  dry_run: boolean
  stop_on_match: boolean
  allow_semantic: boolean
  priority: number
  trigger_mode: BackendFunctionRuleTriggerMode
  condition_type: BackendFunctionRuleConditionType
  condition_config: Record<string, any>
  tool_id: string | null
  reaction_to_execution: BackendFunctionRuleReactionMode
  behavior_after_execution: BackendFunctionRuleBehaviorMode
}

const mapConditionTypeFromBackend = (
  conditionType: BackendFunctionRuleConditionType,
): FunctionRuleConditionType => {
  if (conditionType === 'keyword') {
    return 'keywords'
  }
  return conditionType
}

const mapConditionTypeToBackend = (
  conditionType: FunctionRuleConditionType,
): BackendFunctionRuleConditionType => {
  if (conditionType === 'keywords') {
    return 'keyword'
  }
  return conditionType
}

const normalizeConditionConfigFromBackend = (
  conditionType: BackendFunctionRuleConditionType,
  conditionConfig: Record<string, any> | null | undefined,
): FunctionRuleConditionConfig => {
  const normalized = { ...(conditionConfig || {}) }

  if (conditionType === 'regex') {
    const pattern = String(
      normalized.pattern ||
      (Array.isArray(normalized.patterns) && normalized.patterns.length > 0
        ? normalized.patterns[0]
        : ''),
    )

    return {
      ...normalized,
      pattern,
    }
  }

  if (conditionType === 'semantic') {
    const intents = Array.isArray(normalized.intents) ? normalized.intents : []
    const firstIntent = intents[0] || {}
    const intentName = String(normalized.intent || firstIntent.name || '')
    const examples = Array.isArray(normalized.examples)
      ? normalized.examples
      : Array.isArray(firstIntent.examples)
        ? firstIntent.examples
        : []

    return {
      ...normalized,
      intent: intentName,
      examples,
    }
  }

  return normalized
}

const normalizeConditionConfigToBackend = (
  payload: FunctionRuleUpsertPayload,
): Record<string, any> => {
  const normalized = {
    ...(payload.condition_config as Record<string, any> || {}),
  }

  if (payload.condition_type === 'keywords') {
    normalized.keywords = Array.isArray(normalized.keywords)
      ? normalized.keywords.map((item: any) => String(item).trim()).filter(Boolean)
      : []
  }

  if (payload.condition_type === 'regex') {
    const pattern = String(normalized.pattern || '').trim()
    normalized.patterns = pattern ? [pattern] : []
  }

  if (payload.condition_type === 'semantic') {
    const intent = String(normalized.intent || '').trim()
    const examples = Array.isArray(normalized.examples)
      ? normalized.examples.map((item: any) => String(item).trim()).filter(Boolean)
      : []
    normalized.semantic_threshold = Number(normalized.semantic_threshold ?? 0.7)
    if (intent) {
      normalized.intents = [{ name: intent, examples }]
    }
  }

  if (payload.reaction_mode === 'send_message') {
    normalized.reaction_message = String(payload.reaction_message || '').trim()
    delete normalized.ai_instruction
  }

  if (payload.reaction_mode === 'ai_instruction') {
    normalized.ai_instruction = String(payload.reaction_instruction || '').trim()
    delete normalized.reaction_message
  }

  if (payload.reaction_mode === 'ai_self_reply' || payload.reaction_mode === 'silent') {
    delete normalized.reaction_message
    delete normalized.ai_instruction
  }

  if (payload.post_scenario === 'augment_prompt') {
    normalized.augment_prompt = String(payload.post_scenario_prompt || '').trim()
  }

  return normalized
}

export const mapFunctionRuleFromBackend = (rule: BackendFunctionRule): FunctionRule => {
  const normalizedConditionConfig = normalizeConditionConfigFromBackend(rule.condition_type, rule.condition_config)

  return {
    id: rule.id,
    agent_id: rule.agent_id,
    name: rule.name,
    enabled: rule.enabled,
    dry_run: rule.dry_run,
    stop_on_match: rule.stop_on_match,
    allow_semantic: rule.allow_semantic,
    priority: rule.priority,
    trigger_mode: rule.trigger_mode,
    condition_type: mapConditionTypeFromBackend(rule.condition_type),
    condition_config: normalizedConditionConfig,
    tool_id: rule.tool_id,
    reaction_mode: rule.reaction_to_execution,
    reaction_message: String(rule.condition_config?.reaction_message || '') || null,
    reaction_instruction: String(rule.condition_config?.ai_instruction || '') || null,
    post_scenario: rule.behavior_after_execution,
    post_scenario_prompt: String(rule.condition_config?.augment_prompt || '') || null,
    actions: (rule.actions || []).map(mapRuleActionFromBackend),
    created_at: rule.created_at,
    updated_at: rule.updated_at || undefined,
  }
}

export const mapFunctionRulePayloadToBackend = (
  payload: FunctionRuleUpsertPayload,
): BackendFunctionRulePayload => ({
  name: payload.name,
  enabled: payload.enabled,
  dry_run: payload.dry_run,
  stop_on_match: payload.stop_on_match,
  allow_semantic: payload.allow_semantic ?? true,
  priority: payload.priority,
  trigger_mode: payload.trigger_mode || 'pre_run',
  condition_type: mapConditionTypeToBackend(payload.condition_type),
  condition_config: normalizeConditionConfigToBackend(payload),
  tool_id: payload.tool_id || null,
  reaction_to_execution: payload.reaction_mode,
  behavior_after_execution: payload.post_scenario,
})
