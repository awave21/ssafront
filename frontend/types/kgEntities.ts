export const KG_ENTITY_TYPES = [
  { value: 'motive',     label: 'Мотив',          helper: 'Психологический драйвер: страх, статус, безопасность, экономия, скорость' },
  { value: 'argument',   label: 'Аргумент',       helper: 'Тезис/выгода: клинический, экономический, эмоциональный' },
  { value: 'proof',      label: 'Доказательство', helper: 'Кейс, отзыв, сертификат, фото до/после, статистика' },
  { value: 'objection',  label: 'Возражение',     helper: 'BANT-T: Budget, Authority, Need, Timing, Trust' },
  { value: 'constraint', label: 'Ограничение',    helper: 'Политика/запрет: «не обещать результат», «не называть конкурентов»' },
  { value: 'outcome',    label: 'Итог',           helper: 'Результат ветки: запись, отложено, отказ-причина' },
] as const

export type AgentKgEntityType = typeof KG_ENTITY_TYPES[number]['value']

export type AgentKgEntity = {
  id: string
  agent_id: string
  tenant_id: string
  entity_type: AgentKgEntityType
  name: string
  description: string | null
  meta: Record<string, unknown>
  created_at: string
  updated_at: string | null
  usage_count: number
}

export type MotiveMeta = {
  summary?: string
  verbal_markers?: string[]
  how_to_work?: string
  example_response?: string
}

export type AgentKgEntityCreatePayload = {
  entity_type: AgentKgEntityType
  name: string
  description?: string | null
  meta?: Record<string, unknown>
}

export type AgentKgEntityUpdatePayload = {
  name?: string
  description?: string | null
  meta?: Record<string, unknown>
}

export const BANT_T_CATEGORIES = [
  { value: 'budget',    label: 'Budget — бюджет/цена' },
  { value: 'authority', label: 'Authority — решающий' },
  { value: 'need',      label: 'Need — потребность' },
  { value: 'timing',    label: 'Timing — время/срочность' },
  { value: 'trust',     label: 'Trust — доверие' },
] as const

export type ConstraintMeta = {
  is_hard?: boolean
}

export type ObjectionMeta = {
  bant_category?: string
}
