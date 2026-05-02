export const ORIGIN_COLORS: Record<string, string> = {
  sqns: '#6366f1',
  knowledge: '#22c55e',
  directory: '#f97316',
  script_bridge: '#ec4899',
}

export const ORIGIN_LABELS: Record<string, string> = {
  sqns: 'SQNS',
  knowledge: 'Файлы',
  directory: 'Справочники',
  script_bridge: 'Сценарии',
}

export const FALLBACK_NODE_COLOR = '#64748b'

export const colorForOrigin = (origin: string | null | undefined): string =>
  (origin && ORIGIN_COLORS[origin]) || FALLBACK_NODE_COLOR

/**
 * Палитра по семантическому типу узла. Известные типы — фиксированные цвета,
 * новые — детерминированный hash → HSL (чтобы UI не «прыгал» между загрузками).
 */
export const TYPE_COLORS: Record<string, string> = {
  // Сценарии / runtime
  motive: '#6366f1',        // индиго — мотив пациента
  concern: '#f59e0b',       // янтарь — опасение
  objection: '#ef4444',     // красный — возражение
  tactic: '#8b5cf6',        // фиолетовый — тактика
  trust_signal: '#06b6d4',  // циан — сигнал доверия
  expertise: '#0ea5e9',     // голубой — экспертиза
  outcome: '#10b981',       // изумруд — результат
  trigger: '#f97316',       // оранжевый — триггер
  condition: '#eab308',     // жёлтый — условие
  stage: '#a855f7',         // лиловый — стадия
  question: '#14b8a6',      // бирюзовый — вопрос
  end: '#64748b',           // серый — конечный узел

  // Доменные сущности
  service: '#22c55e',       // зелёный — услуга
  specialist: '#ec4899',    // розовый — специалист
  person: '#ec4899',        // алиас
  organization: '#3b82f6',  // синий — организация
  geo: '#84cc16',           // лайм — геолокация
  event: '#f43f5e',         // алый — событие
  category: '#7c3aed',      // фиолет — категория

  // Справочники
  directory: '#0891b2',         // тёмная бирюза — справочник
  directory_item: '#06b6d4',    // циан — запись справочника

  // GraphRAG-дефолты
  entity: '#22c55e',
}

export const TYPE_LABELS: Record<string, string> = {
  motive: 'Мотивы',
  concern: 'Сомнения',
  objection: 'Возражения',
  tactic: 'Тактики',
  trust_signal: 'Доверие',
  expertise: 'Экспертиза',
  outcome: 'Результаты',
  trigger: 'Триггеры',
  condition: 'Условия',
  stage: 'Стадии',
  question: 'Вопросы',
  end: 'Концовки',

  service: 'Услуги',
  specialist: 'Сотрудники',
  person: 'Сотрудники',
  organization: 'Организации',
  geo: 'Локации',
  event: 'События',
  category: 'Категории',

  entity: 'Сущности',

  directory: 'Справочники',
  directory_item: 'Записи справочника',
}

const hashHue = (input: string): number => {
  let h = 0
  for (let i = 0; i < input.length; i++) {
    h = (h * 31 + input.charCodeAt(i)) | 0
  }
  return Math.abs(h) % 360
}

export const colorForType = (type: string | null | undefined): string => {
  if (!type) return FALLBACK_NODE_COLOR
  const known = TYPE_COLORS[type]
  if (known) return known
  return `hsl(${hashHue(type)} 55% 55%)`
}

export const labelForType = (type: string | null | undefined): string => {
  if (!type) return 'Прочее'
  return TYPE_LABELS[type] || type.replace(/_/g, ' ')
}
