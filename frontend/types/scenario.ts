import {
  mapRuleActionFromBackend,
  type BackendFunctionRuleAction,
  type FunctionRuleAction,
  type FunctionRuleActionType,
  type FunctionRuleActionStatus,
} from '~/types/ruleAction'

export const scenarioTriggerModes = {
  preRun: 'pre_run',
  postTool: 'post_tool',
  postRun: 'post_run',
  dialogStart: 'dialog_start',
  clientMessage: 'client_message',
  agentMessage: 'agent_message',
  managerMessage: 'manager_message',
  clientReturn: 'client_return',
  spendLimit: 'spend_limit',
  sendError: 'send_error',
} as const

export type ScenarioTriggerMode = (typeof scenarioTriggerModes)[keyof typeof scenarioTriggerModes]

export const scenarioConditionTypes = {
  keyword: 'keyword',
  regex: 'regex',
  semantic: 'semantic',
  jsonContext: 'json_context',
  always: 'always',
  scheduleTime: 'schedule_time',
  scheduleWeekday: 'schedule_weekday',
  dialogSource: 'dialog_source',
  startParam: 'start_param',
  afterScenario: 'after_scenario',
  clientReturnGap: 'client_return_gap',
} as const

export type ScenarioConditionType = (typeof scenarioConditionTypes)[keyof typeof scenarioConditionTypes]

export const scenarioActionTypes = {
  setTag: 'set_tag',
  sendMessage: 'send_message',
  webhook: 'webhook',
  pauseDialog: 'pause_dialog',
  resumeDialog: 'resume_dialog',
  blockUser: 'block_user',
  unblockUser: 'unblock_user',
  augmentPrompt: 'augment_prompt',
  setResult: 'set_result',
  noop: 'noop',
  sendDelayed: 'send_delayed',
  notifyAdmin: 'notify_admin',
  handoffToOperator: 'handoff_to_operator',
  setVariable: 'set_variable',
} as const

export type ScenarioActionType = (typeof scenarioActionTypes)[keyof typeof scenarioActionTypes]

export type ScenarioConditionConfig = Record<string, any>

export type ScenarioAction = FunctionRuleAction & {
  action_type: ScenarioActionType
}

// Reaction/Behavior — эти два поля backend требует у каждого правила.
// В UI сейчас не редактируются, но должны round-trip'иться без потерь,
// иначе PUT затирает значения, установленные через API/SQL (например `pause`).
export type ScenarioReactionMode = 'send_message' | 'ai_instruction' | 'ai_self_reply' | 'silent'
export type ScenarioPostBehavior = 'continue' | 'pause' | 'augment_prompt'

export type Scenario = {
  id: string
  agent_id: string
  name: string
  enabled: boolean
  priority: number
  trigger_mode: ScenarioTriggerMode
  condition_type: ScenarioConditionType
  condition_config: ScenarioConditionConfig
  reaction_to_execution?: ScenarioReactionMode
  behavior_after_execution?: ScenarioPostBehavior
  actions: ScenarioAction[]
  created_at?: string
  updated_at?: string
}

export type ScenarioUpsertPayload = Omit<
  Scenario,
  'id' | 'agent_id' | 'created_at' | 'updated_at'
>

export type BackendScenario = {
  id: string
  tenant_id: string
  agent_id: string
  name: string
  enabled: boolean
  priority: number
  trigger_mode: ScenarioTriggerMode
  condition_type: ScenarioConditionType
  condition_config: Record<string, any>
  reaction_to_execution?: ScenarioReactionMode
  behavior_after_execution?: ScenarioPostBehavior
  actions: BackendFunctionRuleAction[]
  created_at?: string
  updated_at?: string | null
}

export const mapScenarioFromBackend = (backend: BackendScenario): Scenario => {
  return {
    id: backend.id,
    agent_id: backend.agent_id,
    name: backend.name,
    enabled: backend.enabled,
    priority: backend.priority,
    trigger_mode: backend.trigger_mode,
    condition_type: backend.condition_type,
    condition_config: backend.condition_config || {},
    reaction_to_execution: backend.reaction_to_execution,
    behavior_after_execution: backend.behavior_after_execution,
    actions: (backend.actions || []).map(mapRuleActionFromBackend) as ScenarioAction[],
    created_at: backend.created_at,
    updated_at: backend.updated_at || undefined,
  }
}
