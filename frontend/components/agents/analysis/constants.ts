import {
  Bell,
  BookOpen,
  Code2,
  FileText,
  MessageCircle,
  MoreHorizontal,
  Shield,
  Target,
  Upload,
  User,
  Wrench,
  Zap,
} from 'lucide-vue-next'
import type { AnalysisRecommendation } from '~/types/agent-analysis'

// ─── Типы ────────────────────────────────────────────────────────────────────

export type ToolTypeDef = {
  id: string
  label: string
  description: string
  icon: unknown
  keywords: string[]
  barClass: string
}

export type PromptSectionDef = {
  key: string
  label: string
  icon: unknown
  keywords: string[]
}

export type KpiCard = {
  label: string
  value: string
  description: string
  colorClass: string
}

export type ToolTypeCard = ToolTypeDef & {
  count: number
  share: number
}

export type PromptSection = PromptSectionDef & {
  items: import('~/types/agent-analysis').AnalysisRecommendation[]
}

// ─── Определения типов инструментов ──────────────────────────────────────────

export const TOOL_TYPE_DEFS: ToolTypeDef[] = [
  {
    id: 'direct',
    label: 'Прямые вопросы',
    description: 'Ответы без инструментов',
    icon: MessageCircle,
    keywords: ['вопрос', 'ответ', 'прямой', 'general', 'question', 'direct', 'faq', 'общий'],
    barClass: 'bg-blue-500',
  },
  {
    id: 'files',
    label: 'Загрузка файлов',
    description: 'Работа с документами',
    icon: Upload,
    keywords: ['файл', 'загрузка', 'документ', 'file', 'upload', 'document', 'attachment', 'вложение'],
    barClass: 'bg-violet-500',
  },
  {
    id: 'sqns',
    label: 'SQN инструменты',
    description: 'Очереди и уведомления',
    icon: Bell,
    keywords: ['sqn', 'очередь', 'уведомление', 'queue', 'notification', 'sqs', 'sns'],
    barClass: 'bg-amber-500',
  },
  {
    id: 'functions',
    label: 'Функции',
    description: 'API-вызовы и инструменты',
    icon: Code2,
    keywords: ['функция', 'function', 'api', 'инструмент', 'tool', 'call', 'вызов', 'метод', 'method'],
    barClass: 'bg-emerald-500',
  },
]

// ─── Определения секций промта ────────────────────────────────────────────────

export const PROMPT_SECTION_DEFS: PromptSectionDef[] = [
  {
    key: 'role',
    label: 'Роль',
    icon: User,
    keywords: ['role', 'роль', 'persona', 'персона', 'character', 'личность'],
  },
  {
    key: 'goal',
    label: 'Цель',
    icon: Target,
    keywords: ['goal', 'цель', 'objective', 'задача', 'mission', 'цели', 'purpose'],
  },
  {
    key: 'behavior',
    label: 'Поведение',
    icon: Zap,
    keywords: ['behavior', 'поведение', 'tone', 'тон', 'стиль', 'style', 'manner', 'манера', 'conduct'],
  },
  {
    key: 'restrictions',
    label: 'Ограничения',
    icon: Shield,
    keywords: ['restriction', 'ограничение', 'constraint', 'limit', 'запрет', 'prohibition', 'boundary', 'правило', 'rule'],
  },
  {
    key: 'format',
    label: 'Формат ответа',
    icon: FileText,
    keywords: ['format', 'формат', 'output', 'структура', 'structure', 'response', 'шаблон', 'template'],
  },
  {
    key: 'context',
    label: 'Контекст',
    icon: BookOpen,
    keywords: ['context', 'контекст', 'background', 'знания', 'knowledge', 'information', 'база'],
  },
  {
    key: 'tools',
    label: 'Инструменты',
    icon: Wrench,
    keywords: ['tool', 'инструмент', 'function', 'функция', 'api', 'sqn', 'upload', 'загрузка', 'файл'],
  },
  {
    key: 'other',
    label: 'Прочее',
    icon: MoreHorizontal,
    keywords: [],
  },
]

// ─── Форматтеры ───────────────────────────────────────────────────────────────

export const formatDateTime = (value?: string | null): string => {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('ru-RU')
}

export const formatPercent = (value?: number | null): string => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(1)}%`
}

export const formatNumber = (value?: number | null): string => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—'
  return value.toLocaleString('ru-RU')
}

export const formatStatus = (status?: string | null): string => {
  const map: Record<string, string> = {
    queued: 'В очереди',
    running: 'Выполняется',
    succeeded: 'Завершено',
    failed: 'Ошибка',
    cancelled: 'Отменено',
    unknown: 'Неизвестно',
  }
  return map[status || ''] || (status ?? 'Неизвестно')
}

export const getStatusClasses = (status: string): string => {
  if (status === 'succeeded') return 'bg-emerald-100 text-emerald-700'
  if (status === 'failed') return 'bg-red-100 text-red-700'
  if (status === 'cancelled') return 'bg-slate-100 text-slate-700'
  if (status === 'running') return 'bg-blue-100 text-blue-700'
  if (status === 'queued') return 'bg-amber-100 text-amber-700'
  return 'bg-slate-100 text-slate-700'
}

export const getHealthBarClass = (health: number): string => {
  if (health >= 70) return 'bg-emerald-500'
  if (health >= 40) return 'bg-amber-500'
  return 'bg-red-500'
}

/** Доля полосы здоровья: API отдаёт good | warning | critical */
export const topicHealthBarPercent = (health: string | number | null | undefined): number => {
  if (typeof health === 'number' && !Number.isNaN(health)) {
    return Math.min(100, Math.max(0, health))
  }
  const h = String(health ?? '').toLowerCase()
  if (h === 'good') return 85
  if (h === 'critical') return 25
  if (h === 'warning') return 55
  return 0
}

export const topicHealthLabel = (health: string | number | null | undefined): string => {
  if (typeof health === 'number' && !Number.isNaN(health)) return `${Math.round(health)}%`
  const h = String(health ?? '').toLowerCase()
  if (h === 'good') return 'Норма'
  if (h === 'critical') return 'Риск'
  if (h === 'warning') return 'Внимание'
  return '—'
}

export const getHealthBarClassForTopic = (health: string | number | null | undefined): string => {
  const pct = topicHealthBarPercent(health)
  if (pct >= 70) return 'bg-emerald-500'
  if (pct >= 40) return 'bg-amber-500'
  return 'bg-red-500'
}

/** Рекомендации, отнесённые к типу инструмента по ключевым словам в category */
export const getRecommendationsForToolTypeId = (
  toolId: string,
  recommendations: AnalysisRecommendation[]
): AnalysisRecommendation[] => {
  const def = TOOL_TYPE_DEFS.find((d) => d.id === toolId)
  if (!def) return []
  return recommendations.filter((rec) => {
    const cat = (rec.category || '').toLowerCase()
    return def.keywords.some((kw) => cat.includes(kw))
  })
}
