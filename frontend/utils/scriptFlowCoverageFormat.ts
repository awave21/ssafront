/** Formatting helpers for the Coverage dashboard (non-technical sales-expert UX). */

export type MatchTone = 'emerald' | 'amber' | 'rose' | 'slate'

export interface MatchInfo {
  category: string
  pct: string        // e.g. "68%"
  tone: MatchTone
  icon: string       // emoji
}

export interface AppliedRateInfo {
  label: string      // "Соблюдён в 6 из 8 ответов · 75%"
  tone: MatchTone
}

export interface MissedClassInfo {
  label: string      // human-readable "Возражение клиента"
  icon: string       // emoji
  detail: string     // short description
}

interface Thresholds {
  relevant: number
  irrelevant: number
}

export function formatMatch(
  score: number | null,
  hits: number,
  thresholds: Thresholds,
): MatchInfo {
  if (hits === 0 || score === null) {
    return { category: 'Сценария нет', pct: '—', tone: 'slate', icon: '⬜' }
  }
  const pct = Math.round(score * 100) + '%'
  if (score >= thresholds.relevant) {
    return { category: 'Точное попадание', pct, tone: 'emerald', icon: '✅' }
  }
  if (score > thresholds.irrelevant) {
    return { category: 'Близкая тема', pct, tone: 'amber', icon: '🟡' }
  }
  return { category: 'Не подходит', pct, tone: 'rose', icon: '🔴' }
}

export function formatAppliedRate(
  applied: number,
  scored: number,
): AppliedRateInfo {
  if (scored === 0) {
    return { label: 'Нет данных о соблюдении', tone: 'slate' }
  }
  const rate = applied / scored
  const pct = Math.round(rate * 100)
  const label = `Соблюдён в ${applied} из ${scored} ответов · ${pct}%`
  if (rate >= 0.7) return { label, tone: 'emerald' }
  if (rate >= 0.4) return { label, tone: 'amber' }
  return { label, tone: 'rose' }
}

const MISSED_CLASS_MAP: Record<string, MissedClassInfo> = {
  objection: {
    label: 'Возражения клиентов',
    icon: '🛑',
    detail: 'Клиент сомневался: по цене, сравнивал, не доверял',
  },
  trigger: {
    label: 'Поводы для разговора',
    icon: '🎯',
    detail: 'Клиент дал повод открыть сценарий, но ассистент не воспользовался',
  },
  concern: {
    label: 'Сомнения и страхи',
    icon: '😟',
    detail: 'Клиент высказал беспокойство — боялся процедуры, побочных эффектов',
  },
  qualification: {
    label: 'Уточняющие вопросы',
    icon: '🔍',
    detail: 'Клиент хотел разобраться, ассистент ответил без опоры на сценарий',
  },
  closing: {
    label: 'Готовность к записи',
    icon: '✅',
    detail: 'Клиент был готов записаться, но ассистент не воспользовался сценарием закрытия',
  },
}

export function formatMissedClass(classification: string): MissedClassInfo {
  return MISSED_CLASS_MAP[classification] ?? {
    label: classification,
    icon: '📌',
    detail: '',
  }
}

/** Badge tone → Tailwind classes */
export function toneClasses(tone: MatchTone): {
  bg: string; border: string; text: string; dot: string
} {
  switch (tone) {
    case 'emerald':
      return { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-800', dot: 'bg-emerald-500' }
    case 'amber':
      return { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-800', dot: 'bg-amber-400' }
    case 'rose':
      return { bg: 'bg-rose-50', border: 'border-rose-200', text: 'text-rose-800', dot: 'bg-rose-500' }
    default:
      return { bg: 'bg-slate-50', border: 'border-slate-200', text: 'text-slate-600', dot: 'bg-slate-400' }
  }
}

export function periodLabel(days: number): string {
  if (days === 1) return 'сегодня'
  if (days === 7) return 'за неделю'
  return `за ${days} дней`
}
