import type { Component } from 'vue'
import {
  AlertCircle,
  Calendar,
  CheckCircle2,
  Clock,
  FlaskConical,
  Mail,
  MapPin,
  Phone,
  XCircle,
} from 'lucide-vue-next'
import type { PatientSegmentTone, SqnsClientCachedVisitItem, SqnsClientListItem } from '~/types/patient-directory'

export const formatRub = (n: number) =>
  new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(n)

export const toRevenueNumber = (v: number | string | null | undefined): number => {
  if (v == null) return 0
  if (typeof v === 'number') return Number.isFinite(v) ? v : 0
  const n = parseFloat(String(v).replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

export const initialsFromName = (name: string | null | undefined): string => {
  const parts = (name ?? '').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '—'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export const segmentBadgeAttrs = (tone: PatientSegmentTone) => {
  const base =
    'rounded-xl border px-2.5 py-1 text-[10px] font-bold shadow-sm transition-colors gap-1 inline-flex items-center'
  switch (tone) {
    case 'muted':
      return {
        variant: 'secondary' as const,
        class: `${base} border-slate-100 bg-white text-slate-600 hover:bg-slate-50`,
      }
    case 'accent':
      return {
        variant: 'outline' as const,
        class: `${base} border-primary/20 bg-primary/5 text-primary`,
      }
    case 'warning':
      return {
        variant: 'outline' as const,
        class: `${base} border-amber-100 bg-amber-50 text-amber-800`,
      }
    case 'success':
      return {
        variant: 'outline' as const,
        class: `${base} border-emerald-100 bg-emerald-50 text-emerald-700`,
      }
    default:
      return {
        variant: 'secondary' as const,
        class: `${base} border-slate-100 bg-white text-slate-600`,
      }
  }
}

export type ProfileBadgeVm = { label: string; tone: PatientSegmentTone; icon?: 'star' }

export const buildProfileBadges = (c: SqnsClientListItem): ProfileBadgeVm[] => {
  const out: ProfileBadgeVm[] = []
  const tags = (c.tags ?? []).map((t) => String(t).trim()).filter(Boolean)
  const joined = tags.join(' ').toLowerCase()
  if (joined.includes('vip')) out.push({ label: 'VIP клиент', tone: 'warning', icon: 'star' })
  else if (c.client_type?.trim()) out.push({ label: c.client_type.trim(), tone: 'muted' })
  const vc = c.visits_count ?? 0
  if (vc > 1) out.push({ label: 'Повторный', tone: 'muted' })
  out.push({ label: 'Активен', tone: 'success' })
  return out
}

export const formatBirth = (raw: string | null): string => {
  if (!raw?.trim()) return '—'
  const d = new Date(raw)
  if (!Number.isNaN(d.getTime())) {
    const dateStr = new Intl.DateTimeFormat('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }).format(d)
    const age = Math.floor((Date.now() - d.getTime()) / (365.25 * 24 * 60 * 60 * 1000))
    if (age >= 0 && age < 130) return `${dateStr} (${age} лет)`
    return dateStr
  }
  return raw.trim()
}

export type ContactRowVm = { label: string; value: string; icon: Component }

export const buildContactRows = (c: SqnsClientListItem): ContactRowVm[] => {
  const phone = c.phone?.trim() ? c.phone.trim() : '—'
  return [
    { label: 'Телефон', value: phone, icon: Phone },
    { label: 'Email', value: '—', icon: Mail },
    { label: 'Дата рождения', value: formatBirth(c.birth_date), icon: Calendar },
    { label: 'Регион', value: '—', icon: MapPin },
  ]
}

export const visitTimestamp = (v: SqnsClientCachedVisitItem): number | null => {
  if (!v.visit_datetime) return null
  const t = new Date(v.visit_datetime).getTime()
  return Number.isNaN(t) ? null : t
}

/** Дата YYYY-MM-DD из сырой строки SQNS (календарная, без UTC). */
const calendarDateFromSqnsRaw = (raw: string): { y: number; m: number; d: number } | null => {
  const head = raw.includes('T') ? raw.split('T')[0] : (raw.split(/\s+/)[0] ?? '')
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(head.trim())
  if (!m) return null
  return { y: Number(m[1]), m: Number(m[2]), d: Number(m[3]) }
}

/** Время из сырой строки SQNS — как в ответе API, без пересчёта пояса. */
const clockFromSqnsRaw = (raw: string): string | null => {
  const s = raw.trim()
  if (!s) return null
  if (s.includes('T')) {
    const after = s.split('T')[1]
    if (!after) return null
    const noTz = after.replace(/([+-]\d{2}:?\d{2}|Z).*$/i, '').trim()
    return noTz || null
  }
  const parts = s.split(/\s+/).filter(Boolean)
  if (parts.length < 2) return null
  return parts.slice(1).join(' ')
}

export type VisitKind = 'upcoming' | 'completed' | 'cancelled' | 'incomplete' | 'unknown'

/** Состоявшийся визит: как на бэкенде (attendance + status в raw_data), см. visit_arrival.py */
export const visitArrived = (v: SqnsClientCachedVisitItem): boolean => {
  if (v.arrived === true) return true
  if (v.arrived === false) return false
  const att = v.attendance
  if (att === 0) return false
  if (att != null && att > 0) return true
  return false
}

export const visitKind = (v: SqnsClientCachedVisitItem): VisitKind => {
  const t = visitTimestamp(v)
  if (t === null) return 'unknown'
  const now = Date.now()
  if (t >= now) return 'upcoming'
  if (v.attendance === 0) return 'cancelled'
  if (visitArrived(v)) return 'completed'
  return 'incomplete'
}

export const sortVisitsForDisplay = (list: SqnsClientCachedVisitItem[]): SqnsClientCachedVisitItem[] => {
  const now = Date.now()
  const copy = [...list]
  const withT = copy
    .map((v) => ({ v, t: visitTimestamp(v) }))
    .filter((x): x is { v: SqnsClientCachedVisitItem; t: number } => x.t !== null)
  const upcoming = withT
    .filter((x) => x.t >= now)
    .sort((a, b) => a.t - b.t)
    .map((x) => x.v)
  const past = withT
    .filter((x) => x.t < now)
    .sort((a, b) => b.t - a.t)
    .map((x) => x.v)
  const noDt = copy.filter((v) => visitTimestamp(v) === null)
  return [...upcoming, ...past, ...noDt]
}

export const formatVisitDate = (v: SqnsClientCachedVisitItem) => {
  const raw = v.visit_datetime_raw?.trim()
  if (raw) {
    const cal = calendarDateFromSqnsRaw(raw)
    if (cal) {
      const local = new Date(cal.y, cal.m - 1, cal.d)
      return new Intl.DateTimeFormat('ru-RU', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      }).format(local)
    }
  }
  const t = visitTimestamp(v)
  if (t === null) return '—'
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }).format(
    new Date(t),
  )
}

export const formatVisitTime = (v: SqnsClientCachedVisitItem) => {
  const raw = v.visit_datetime_raw?.trim()
  if (raw) {
    const clock = clockFromSqnsRaw(raw)
    if (clock) return clock
  }
  const t = visitTimestamp(v)
  if (t === null) return ''
  return new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(new Date(t))
}

export const rowHighlightClass = (v: SqnsClientCachedVisitItem) =>
  visitKind(v) === 'upcoming' ? 'bg-primary/[0.03]' : 'hover:bg-slate-50/80'

export const visitPriceMain = (v: SqnsClientCachedVisitItem) => formatRub(toRevenueNumber(v.total_price))

export const visitPriceSub = (v: SqnsClientCachedVisitItem) => {
  const k = visitKind(v)
  const p = toRevenueNumber(v.total_price)
  if (k === 'upcoming') return p > 0 ? 'Не оплачено' : '—'
  if (k === 'cancelled' || k === 'incomplete') return '—'
  return p > 0 ? 'Оплачено' : '—'
}

export const visitStatusLabel = (v: SqnsClientCachedVisitItem) => {
  const k = visitKind(v)
  if (k === 'upcoming') return 'Предстоит'
  if (k === 'cancelled') return 'Отменён'
  if (k === 'incomplete') return 'Нет явки'
  return 'Завершён'
}

export const visitStatusIcon = (v: SqnsClientCachedVisitItem): Component => {
  const k = visitKind(v)
  if (k === 'upcoming') return Clock
  if (k === 'cancelled') return XCircle
  if (k === 'incomplete') return AlertCircle
  const isLab = (v.service_name ?? '').toLowerCase().includes('анализ')
  return isLab ? FlaskConical : CheckCircle2
}

export const visitStatusBadgeAttrs = (v: SqnsClientCachedVisitItem) => {
  const k = visitKind(v)
  const base =
    'rounded-xl border px-2.5 py-1 text-[10px] font-bold shadow-sm gap-1 inline-flex items-center'
  if (k === 'upcoming')
    return {
      variant: 'outline' as const,
      class: `${base} border-primary/25 bg-primary/5 text-primary`,
    }
  if (k === 'cancelled')
    return {
      variant: 'outline' as const,
      class: `${base} border-rose-100 bg-rose-50 text-rose-600`,
    }
  if (k === 'incomplete')
    return {
      variant: 'outline' as const,
      class: `${base} border-amber-100 bg-amber-50 text-amber-800`,
    }
  return {
    variant: 'secondary' as const,
    class: `${base} border-slate-100 bg-slate-50 text-slate-600`,
  }
}

export const computeNextVisitSummary = (
  sortedVisits: SqnsClientCachedVisitItem[],
  visitsPending: boolean,
): { title: string; sub: string } => {
  const now = Date.now()
  const withT = sortedVisits
    .map((v) => ({ v, t: visitTimestamp(v) }))
    .filter((x): x is { v: SqnsClientCachedVisitItem; t: number } => x.t !== null)
  const upcoming = withT.filter((x) => x.t >= now).sort((a, b) => a.t - b.t)[0]
  if (upcoming) {
    const raw = upcoming.v.visit_datetime_raw?.trim()
    const cal = raw ? calendarDateFromSqnsRaw(raw) : null
    const d = cal ? new Date(cal.y, cal.m - 1, cal.d) : new Date(upcoming.t)
    const title = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' }).format(d)
    const time =
      (raw && clockFromSqnsRaw(raw)) ||
      new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(new Date(upcoming.t))
    const days = Math.ceil((upcoming.t - now) / (24 * 60 * 60 * 1000))
    const rel =
      days <= 0 ? 'сегодня' : days === 1 ? 'через 1 день' : `через ${days} дн.`
    return { title, sub: `${time} · ${rel}` }
  }
  const lastArrivedPast = withT
    .filter((x) => x.t < now && visitArrived(x.v))
    .sort((a, b) => b.t - a.t)[0]
  if (lastArrivedPast) {
    const raw = lastArrivedPast.v.visit_datetime_raw?.trim()
    const cal = raw ? calendarDateFromSqnsRaw(raw) : null
    const d = cal ? new Date(cal.y, cal.m - 1, cal.d) : new Date(lastArrivedPast.t)
    const title = new Intl.DateTimeFormat('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(d)
    return { title, sub: 'Последний визит с подтверждённой явкой' }
  }
  const anyPast = withT.filter((x) => x.t < now).sort((a, b) => b.t - a.t)[0]
  if (anyPast) {
    return { title: '—', sub: 'Нет завершённых визитов (явка не подтверждена)' }
  }
  if (!visitsPending && !sortedVisits.length) return { title: '—', sub: 'Нет визитов' }
  return { title: '—', sub: 'Нет запланированных визитов' }
}

export type PatientDetailTabId = 'visits' | 'dialogs' | 'services' | 'files'

export type PatientDetailTabVm = {
  id: PatientDetailTabId
  label: string
  badge: number | null
}

export const buildPatientDetailTabs = (visitsCount: number): PatientDetailTabVm[] => [
  { id: 'visits', label: 'История визитов', badge: visitsCount },
  { id: 'dialogs', label: 'Диалоги с агентом', badge: 0 },
  { id: 'services', label: 'Услуги и назначения', badge: null },
  { id: 'files', label: 'Файлы и анализы', badge: 0 },
]
