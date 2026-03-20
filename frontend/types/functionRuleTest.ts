export type FunctionRuleTestRequest = {
  message: string
  session_id: string
  historical_messages?: Array<{
    role: string
    content: string
    created_at?: string
  }>
  execute_tool_calls: boolean
}

export type BackendFunctionRuleTestRequest = {
  message: string
  session_id: string
  historical_messages?: string[]
  run_tool_calls: boolean
  trace_id?: string
}

export type FunctionRuleTestMatchedRule = {
  rule_id: string
  name: string
  matched: boolean
  reason?: string | null
  score?: number | null
}

export type FunctionRuleTestExecutedAction = {
  action_id: string
  action_type: string
  on_status: string
  executed: boolean
  reason?: string | null
  details?: Record<string, any>
}

export type FunctionRuleTestResponse = {
  rules: FunctionRuleTestMatchedRule[]
  actions: FunctionRuleTestExecutedAction[]
  tags_created: string[]
  should_pause: boolean
  trace_id: string
}

export type BackendFunctionRuleActionTrace = {
  action_id?: string | null
  action_type: string
  status: string
  details: Record<string, any>
}

export type BackendFunctionRuleMatchedRule = {
  rule_id: string
  matched: boolean
  reason?: string | null
  score?: number | null
  actions: BackendFunctionRuleActionTrace[]
}

export type BackendFunctionRuleTestResponse = {
  trace_id: string
  matched_rules: BackendFunctionRuleMatchedRule[]
  tags_created: string[]
  should_pause: boolean
}

export const mapFunctionRuleTestRequestToBackend = (
  payload: FunctionRuleTestRequest,
): BackendFunctionRuleTestRequest => ({
  message: payload.message,
  session_id: payload.session_id,
  run_tool_calls: payload.execute_tool_calls,
  historical_messages: (payload.historical_messages || [])
    .map((item) => String(item?.content || '').trim())
    .filter(Boolean),
})

export const mapFunctionRuleTestResponseFromBackend = (
  payload: BackendFunctionRuleTestResponse,
): FunctionRuleTestResponse => {
  const rules: FunctionRuleTestMatchedRule[] = (payload.matched_rules || []).map((rule) => ({
    rule_id: rule.rule_id,
    name: '',
    matched: rule.matched,
    reason: rule.reason,
    score: rule.score,
  }))

  const actions: FunctionRuleTestExecutedAction[] = (payload.matched_rules || []).flatMap((rule) =>
    (rule.actions || []).map((action) => ({
      action_id: String(action.action_id || ''),
      action_type: action.action_type,
      on_status: action.status,
      executed: action.status === 'success',
      reason: action.details?.error || action.status,
      details: action.details,
    })),
  )

  return {
    trace_id: payload.trace_id,
    should_pause: payload.should_pause,
    tags_created: payload.tags_created || [],
    rules,
    actions,
  }
}
