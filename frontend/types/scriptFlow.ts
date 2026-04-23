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
    label: 'Повод для разговора',
    color: '#3b82f6',
    description:
      'Что говорит или делает клиент, чтобы этот шаг стал уместным — реплика или ситуация входа в тему',
  },
  {
    value: 'expertise',
    label: 'Ответ эксперта',
    color: '#10b981',
    description:
      'Как реагировать специалисту: интонация момента, аргументы и готовые формулировки',
  },
  {
    value: 'question',
    label: 'Уточняющий вопрос',
    color: '#f59e0b',
    description: 'Вопрос клиенту, чтобы продвинуть диалог или лучше понять запрос',
  },
  {
    value: 'condition',
    label: 'Развилка диалога',
    color: '#f97316',
    description: 'Разные ответы клиента ведут к разным следующим шагам',
  },
  {
    value: 'goto',
    label: 'Переход к теме',
    color: '#8b5cf6',
    description: 'Перейти к другому сценарию или блоку разговора',
  },
  {
    value: 'business_rule',
    label: 'Правило клиники',
    color: '#0ea5e9',
    description:
      'Стандарт сервиса «если → то»: кому записать, приоритет врача, жёсткий формат ответа. Расширенный профиль — в карточке сотрудника.',
  },
  {
    value: 'end',
    label: 'Итог разговора',
    color: '#ef4444',
    description: 'Завершение ветки: запись, отказ, перенос или пауза',
  },
] as const

export type NodeType = typeof NODE_TYPES[number]['value']

export const NODE_TYPE_COLORS: Record<string, string> = Object.fromEntries(
  NODE_TYPES.map(t => [t.value, t.color])
)

/** Упрощённая роль узла для UI (Марика): тактика, вопрос/ветка, каталог правил */
export type NodeRole = 'tactic' | 'question' | 'catalog_rule'

export const ROLE_META = {
  tactic: {
    label: 'Шаг сценария',
    emoji: '🎯',
    paletteZone: 'scenario' as const,
    description: 'Повод, ответ эксперта, переход и итог — узлы живого диалога',
  },
  question: {
    label: 'Вопрос и развилка',
    emoji: '❓',
    paletteZone: 'scenario' as const,
    description: 'Уточняющий вопрос и ветвление по ответу клиента',
  },
  catalog_rule: {
    label: 'Правило клиники',
    emoji: '📋',
    paletteZone: 'catalog' as const,
    description: 'Стандарты по сотруднику или услуге вне линейного диалога',
  },
} as const

/** Ветка развилки: стабильный id; исходящий handle = `branch:{id}` (см. QuestionCard) */
export type FlowBranch = { id: string; label: string }

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
  /** true — карточка только каталога (без рёбер диалога); false — наследие / правило в потоке */
  is_catalog_rule?: boolean
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

  /** schema v2 — trigger */
  client_phrase_examples?: string[]
  when_relevant?: string | null
  keyword_hints?: string[]
  /** schema v2 — question */
  alternative_phrasings?: string[]
  expected_answer_type?: string
  why_we_ask?: string | null
  /** schema v2 — condition */
  routing_hint?: string | null
  /** schema v2 — goto */
  transition_phrase?: string | null
  trigger_situation?: string | null
  /** Когда бэкенд вернёт YAML-оси; до миграции редактируем плоские поля выше */
  expertise_axes?: ExpertAxesV1

  // End-node outcome (applies to node_type === 'end')
  outcome_type?: 'success' | 'pending' | 'lost' | null
  final_action?: string | null

  // Navigation (auto-computed on publish; manual override possible)
  /** @deprecated Используйте is_flow_entry / is_searchable */
  is_entry_point?: boolean
  /** Только для trigger: этот узел — точка входа в поток */
  is_flow_entry?: boolean
  /** Участвует в семантическом поиске / индексации (trigger, expertise, question) */
  is_searchable?: boolean
  /** goto: id другого ScriptFlow того же агента */
  target_flow_id?: string | null
  /** goto: опц. id целевой ноды в целевом потоке */
  target_node_ref?: string | null

  /** Ветки развилки (условие): стабильный id + подпись; handle на канвасе = `branch:{id}` */
  conditions?: FlowBranch[]

  /**
   * Ссылки на общую библиотеку KG-сущностей агента (см. agent_kg_entities).
   * Попадают в LightRAG как явные рёбра custom-KG при публикации потока.
   */
  kg_links?: {
    motive_ids?: string[]
    argument_ids?: string[]
    proof_ids?: string[]
    objection_ids?: string[]
    constraint_ids?: string[]
    outcome_id?: string | null
  }
}

/** Структурированные «оси» для compile (см. бэкенд); в UI пока зеркалим в плоские поля */
export type ExpertAxesV1 = {
  version: 1
  context: { stage?: string; service_ids?: string[]; employee_ids?: string[]; situation?: string }
  content: { why_it_works?: string; approach?: string; example_phrases?: string[]; watch_out?: string; good_question?: string }
}

// ── Flow metadata ────────────────────────────────────────────────────────────
export type ScriptFlowMetadata = {
  /** Снимок flow_definition на момент последней успешной публикации (для «что видит бот») */
  published_flow_definition?: Record<string, unknown>
  /** Версия потока при сохранении снимка */
  published_snapshot_version?: number
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
  /** Optimistic concurrency for PATCH flow_definition */
  definition_version?: number
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

export type ScriptFlowKgCoverageObjection = {
  id: string
  name: string
  description: string | null
}

export type ScriptFlowKgCoverageCell = {
  objection_id: string
  service_id: string
  tactic_count: number
}

export type ScriptFlowKgCoverageResult = {
  objections: ScriptFlowKgCoverageObjection[]
  services: string[]
  cells: ScriptFlowKgCoverageCell[]
}

export type ScriptFlowSearchTestMatchLightRag = {
  flow_name: string | null
  stage: string | null
  tactic_title: string
  situation: string | null
  motives: string[]
  arguments: string[]
  proofs: string[]
  objections_answered: string[]
  constraints: string[]
  required_followup_question: string | null
}

export type ScriptFlowSearchTestResult = {
  query: string
  /** Статус выполнения: ok | disabled | no_index | error. */
  status?: 'ok' | 'disabled' | 'no_index' | 'error'
  message?: string
  error?: string
  raw?: string
  /** Legacy-совместимое поле (до LightRAG — матчи узлов). */
  matches: ScriptFlowSearchTestMatch[] | ScriptFlowSearchTestMatchLightRag[]
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

export type ScriptFlowCoverageIssue = {
  key?: string | null
  label?: string | null
  severity?: string | null
}

export type ScriptFlowToolUsageNode = {
  node_ref: string
  tactic_title?: string | null
  count: number
  last_invoked_at?: string | null
}

export type ScriptFlowCoverageResult = {
  flow_id: string
  score: number
  checks: ScriptFlowCoverageCheck[]
  stats: ScriptFlowCoverageStats
  /** Проблемы покрытия по id узла (для подсветки на канвасе) */
  node_issues?: Record<string, ScriptFlowCoverageIssue[]>
}

export type ScriptFlowGraphNode = {
  graph_node_id: string
  node_kind: 'canvas' | 'entity' | 'community' | string
  entity_type: string
  title: string
  description: string | null
  source_node_ids: string[]
  properties: Record<string, unknown>
  community_key: string | null
}

export type ScriptFlowGraphRelation = {
  source_graph_node_id: string
  target_graph_node_id: string
  relation_type: string
  weight: number
  properties: Record<string, unknown>
}

export type ScriptFlowGraphCommunity = {
  community_key: string
  title: string
  summary: string | null
  node_ids: string[]
  properties: Record<string, unknown>
}

export type ScriptFlowGraphDiagnostic = {
  flow_version: number
  extraction_model: string | null
  summary_model: string | null
  extraction_mode: string | null
  llm_ok_nodes: number
  llm_failed_nodes: number
  entity_count: number
  relation_count: number
  community_count: number
  summary_llm_count: number
  summary_fallback_count: number
  raw: Record<string, unknown>
}

export type ScriptFlowGraphPreview = {
  flow_id: string
  flow_version: number
  nodes: ScriptFlowGraphNode[]
  relations: ScriptFlowGraphRelation[]
  communities: ScriptFlowGraphCommunity[]
  debug: {
    source?: string
    diagnostic?: ScriptFlowGraphDiagnostic | null
    [key: string]: unknown
  }
}

// ── Flow variable binding ─────────────────────────────────────────────────────
export type VariableBinding =
  | { source_type: 'static'; value: string }
  | { source_type: 'search'; search_query: string }
  /**
   * Привязка к агентской функции (tool).
   * В скомпилированном тексте становится явной инструкцией для LLM:
   *   «Чтобы узнать <argument_hint>, вызови функцию <function_name>.»
   * Синтаксис в тексте ноды: {{variable_name}}
   */
  | {
      source_type: 'function'
      function_id: string
      /** Что именно вернёт функция: «название услуги + цена», «расписание врача» и т.д. */
      argument_hint: string
      /** Дополнительная инструкция для модели (опц.) */
      llm_instruction?: string
    }
