import type { AnalyticsPaymentMethod, AnalyticsRevenueCategory } from '~/types/analytics'

/** Ответ API списка клиентов SQNS */
export type SqnsClientListItem = {
  id: string
  external_id: number
  name: string | null
  phone: string | null
  birth_date: string | null
  sex: number | null
  client_type: string | null
  visits_count: number | null
  total_arrival: number | string | null
  tags: string[] | null
  last_visit_datetime?: string | null
  last_service_name?: string | null
  last_specialist_name?: string | null
  /** Сумма приёма (total_price) для визита в колонке «Визит» */
  last_visit_total_price?: number | string | null
  /** Выручка за срез vf/vt/vc; null/отсутствует — показывать total_arrival */
  slice_revenue?: number | string | null
  /** Число визитов клиента в срезе vf/vt/vc; null/отсутствует — показывать visits_count (всё время) */
  slice_visits_count?: number | null
  synced_at: string
}

export type SqnsClientsListResponse = {
  clients: SqnsClientListItem[]
  total: number
  limit: number
  offset: number
  has_more: boolean
  /** Сумма выручки по выборке (все страницы): при срезе vf/vt/vc — по визитам периода; иначе — сумма total_arrival */
  revenue_total?: number | string
  revenueTotal?: number | string
  /** Сумма total_arrival по выборке (итого колонка «Всего») */
  total_arrival_sum?: number | string
  totalArrivalSum?: number | string
  /** Сумма visits_count по выборке */
  visits_count_sum?: number
  visitsCountSum?: number
  /** Сумма total_price «визита в строке» по всей выборке */
  last_visit_total_price_sum?: number | string
  lastVisitTotalPriceSum?: number | string
  /** Визитов в срезе (как KPI аналитики при vf/vt/vc) */
  slice_visit_count?: number | null
  sliceVisitCount?: number | null
  /** Топ-услуга по числу визитов в кэше среди клиентов выборки (после поиска) */
  top_service_name?: string | null
  top_service_bookings?: number | null
}

/** Визит из кэша (карточка пациента) */
export type SqnsClientCachedVisitItem = {
  id: string
  visit_external_id: number
  visit_datetime: string | null
  /** Строка datetime из SQNS — показ «как в CRM», без сдвига TZ */
  visit_datetime_raw?: string | null
  service_name: string | null
  specialist_name: string | null
  attendance: number | null
  /** Состоявшийся визит (явка/завершён), с бэкенда; без поля — эвристика по attendance */
  arrived?: boolean
  total_price: number | string | null
}

export type SqnsClientCachedVisitsResponse = {
  visits: SqnsClientCachedVisitItem[]
}

export type PatientsSortBy = 'visits_count' | 'total_arrival' | 'synced_at' | 'external_id'

/** Когорта визитов (drill-down из аналитики, query `vc`) */
export type PatientsVisitCohort =
  | 'primary_bookings'
  | 'primary_arrived'
  | 'repeat_bookings'
  | 'repeat_arrived'
  | 'all_bookings'
  | 'all_arrived'

export type PatientsQuery = {
  search: string
  client_type: string
  sort_by: PatientsSortBy
  sort_order: 'asc' | 'desc'
  limit: number
  offset: number
  /** YYYY-MM-DD, границы периода в TZ агента (как в аналитике) */
  visit_date_from: string
  visit_date_to: string
  visit_cohort: '' | PatientsVisitCohort
  /** IANA, как query tz в аналитике */
  timezone: string
  channel: string
  /** Теги через запятую, как query tags в аналитике */
  tags: string
  revenue_basis: 'all' | 'clinical'
  /** Пустой — все способы; непустой — срезовая выручка по платежам (как в аналитике). */
  paymentMethods: AnalyticsPaymentMethod[]
  /** Пустой — все типы; непустой — фильтр услуги/товары (как в аналитике). */
  revenueCategories: AnalyticsRevenueCategory[]
  /** Внешний ID сотрудника SQNS; учитывается вместе с vf/vt/vc (query `resource`). */
  resource_external_id: number | null
}

/** Тон бейджа в карточке пациента (профиль / детали) */
export type PatientSegmentTone = 'muted' | 'accent' | 'warning' | 'success'

export type PatientDirectoryRow = {
  id: string
  /** SQNS client id — для запроса визитов */
  externalClientId: number
  initials: string
  name: string
  phone: string
  externalId: string
  visitDate: string
  visitRelative: string
  serviceName: string
  serviceDetail: string
  /** Выручка за отображаемый в строке визит (из total_price визита); null — нет визита/суммы */
  visitRevenueRub: number | null
  visitsCount: string
  /** true — visitsCount показывает срезовое число, а не всё время */
  visitsCountIsSlice: boolean
  /** Выручка за период (slice_revenue) если задан срез, иначе total_arrival */
  revenueRub: number
  /** true — показывать revenueRub как срезовую (не всё время) */
  revenueIsSlice: boolean
  /** Подсветка строки (как в макете) */
  highlighted?: boolean
}
