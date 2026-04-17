export type ScriptFlowFlowStatus = 'draft' | 'published'

export type ScriptFlowIndexStatus = 'idle' | 'pending' | 'indexing' | 'indexed' | 'failed'

// ── Conversation stages ──────────────────────────────────────────────────────
export const CONVERSATION_STAGES = [
  { value: 'opening',              label: 'Открытие' },
  { value: 'qualification',        label: 'Квалификация' },
  { value: 'presentation',         label: 'Презентация' },
  { value: 'objection_price',      label: 'Возражение: цена' },
  { value: 'objection_comparison', label: 'Возражение: сравнение' },
  { value: 'objection_time',       label: 'Возражение: время / занятость' },
  { value: 'objection_trust',      label: 'Возражение: доверие' },
  { value: 'closing',              label: 'Закрытие / запись' },
  { value: 'universal',            label: 'Универсальный' },
] as const

export type ConversationStage = typeof CONVERSATION_STAGES[number]['value']

// ── Node types ───────────────────────────────────────────────────────────────
export const NODE_TYPES = [
  {
    value: 'trigger',
    label: '🎯 Сигнал',
    color: '#3b82f6',
    description: 'Ситуация-триггер: что именно говорит или делает клиент, чтобы войти в этот сценарий',
  },
  {
    value: 'expertise',
    label: '🧠 Тактика',
    color: '#10b981',
    description: 'Экспертное знание: психология момента, стратегия ответа, примеры фраз',
  },
  {
    value: 'question',
    label: '❓ Вопрос',
    color: '#f59e0b',
    description: 'Уточняющий вопрос клиенту — помогает продвинуть диалог или квалифицировать',
  },
  {
    value: 'condition',
    label: '🔀 Развилка',
    color: '#f97316',
    description: 'Ветвление по ответу клиента — каждая ветка ведёт к отдельной тактике',
  },
  {
    value: 'goto',
    label: '↗️ Переход',
    color: '#8b5cf6',
    description: 'Переход в другой сценарий или поток',
  },
  {
    value: 'business_rule',
    label: '📋 Бизнес-правило',
    color: '#0ea5e9',
    description: 'Структурное правило: источник данных, сущность, условие и действие',
  },
  {
    value: 'end',
    label: '🏁 Результат',
    color: '#ef4444',
    description: 'Финал ветки: что достигнуто (запись, отказ, ожидание)',
  },
] as const

export type NodeType = typeof NODE_TYPES[number]['value']

export const NODE_TYPE_COLORS: Record<string, string> = Object.fromEntries(
  NODE_TYPES.map(t => [t.value, t.color])
)

// ── Node data (stored inside Vue Flow node.data) ─────────────────────────────
export type ScriptNodeData = {
  // Visual
  title?: string
  label?: string

  // Taxonomy
  node_type?: NodeType
  stage?: ConversationStage | null
  level?: number

  // Context filters
  service_ids?: string[]
  employee_ids?: string[]
  data_source?: 'sqns_resources' | 'sqns_services' | 'custom_table' | string
  entity_type?: 'employee' | 'service' | 'custom' | string
  entity_id?: string | null
  rule_condition?: string | null
  rule_action?: string | null
  rule_priority?: number
  rule_active?: boolean
  constraints?: {
    requires_entity?: 'none' | 'service' | 'employee' | 'both'
    must_follow_node_refs?: string[]
  }

  // Expertise content
  situation?: string
  why_it_works?: string | null
  approach?: string | null
  example_phrases?: string[]
  watch_out?: string | null
  good_question?: string | null
  /** Когда бэкенд вернёт YAML-оси; до миграции редактируем плоские поля выше */
  expertise_axes?: ExpertAxesV1

  // End-node outcome (applies to node_type === 'end')
  outcome_type?: 'success' | 'pending' | 'lost' | null
  final_action?: string | null

  // Navigation (auto-computed on publish; manual override possible)
  is_entry_point?: boolean

  // For condition nodes: list of possible answers/branches
  // Each item gets its own source handle (id = `cond-{index}`)
  conditions?: string[]
}

/** Структурированные «оси» для compile (см. бэкенд); в UI пока зеркалим в плоские поля */
export type ExpertAxesV1 = {
  version: 1
  context: { stage?: string; service_ids?: string[]; employee_ids?: string[]; situation?: string }
  content: { why_it_works?: string; approach?: string; example_phrases?: string[]; watch_out?: string; good_question?: string }
}

// ── Flow metadata ────────────────────────────────────────────────────────────
export type ScriptFlowMetadata = {
  when_relevant?: string | null
  keyword_hints?: string[]
  // Primary stage this flow covers (can cover multiple)
  stages?: ConversationStage[]
  service_ids?: string[]
  employee_ids?: string[]
  funnel_stages?: string[]
  /**
   * Flow-level variables substituted into node content at compile / publish time.
   * Syntax in node fields: {{имя_переменной}}
   *
   * Each value is a VariableBinding:
   *   static → literal text substitution
   *   search → expands to [[поиск: query]] — LLM resolves via directory/knowledge tools
   */
  variables?: Record<string, VariableBinding>
}

// ── ScriptFlow entity ────────────────────────────────────────────────────────
export type ScriptFlow = {
  id: string
  tenant_id: string
  agent_id: string
  name: string
  internal_note: string | null
  flow_status: ScriptFlowFlowStatus
  published_version: number
  indexed_version: number | null
  flow_metadata: ScriptFlowMetadata & Record<string, unknown>
  flow_definition: Record<string, unknown>
  compiled_text: string | null
  index_status: ScriptFlowIndexStatus
  index_error: string | null
  last_indexed_at: string | null
  created_at: string
  updated_at: string | null
}

export type ScriptFlowCreatePayload = {
  name: string
  internal_note?: string | null
  flow_metadata?: Record<string, unknown>
  flow_definition?: Record<string, unknown>
}

export type ScriptFlowUpdatePayload = {
  name?: string
  internal_note?: string | null
  flow_metadata?: Record<string, unknown>
  flow_definition?: Record<string, unknown>
}

export type ScriptFlowSuggestKeywordsResult = {
  keywords: string[]
  when_relevant: string | null
}

export type ScriptFlowSearchTestMatch = {
  node_id: string
  node_ref_id: string
  flow_id: string
  flow_name: string
  node_type: string
  stage: string | null
  level: number
  situation: string
  approach: string | null
  good_question: string | null
  score: number
  distance: number
}

export type ScriptFlowSearchTestResult = {
  query: string
  matches: ScriptFlowSearchTestMatch[]
}

export type ScriptFlowCoverageCheck = {
  key: string
  label: string
  passed: boolean
  severity: 'critical' | 'warning' | string
  details: string | null
}

export type ScriptFlowCoverageStats = {
  total_nodes: number
  searchable_nodes: number
  searchable_with_good_question: number
  condition_nodes: number
  condition_branches: number
}

export type ScriptFlowCoverageResult = {
  flow_id: string
  score: number
  checks: ScriptFlowCoverageCheck[]
  stats: ScriptFlowCoverageStats
}

// ── Flow variable binding ─────────────────────────────────────────────────────
export type VariableBinding =
  | { source_type: 'static'; value: string }
  | { source_type: 'search'; search_query: string }
