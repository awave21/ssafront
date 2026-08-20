export type AnalyticsTimeGroup = 'day' | 'week' | 'month'

/** all — полная касса; clinical — услуги + товары + сертификаты (как итог отчёта по услугам SQNS). */
export type AnalyticsRevenueBasis = 'all' | 'clinical'
export type AnalyticsBreakdownDimension = 'channel' | 'tag' | 'client_type'
export type AnalyticsPeriodPreset = '7d' | '30d' | '90d' | 'custom'

export type AnalyticsOverview = {
  visits_total: number
  arrived_total: number
  primary_visits: number
  primary_arrived: number
  conversion_primary_arrived_pct: number
  primary_revenue: number
  repeat_total: number
  repeat_arrived: number
  conversion_repeat_arrived_pct: number
  repeat_revenue: number
  /** Выручка первичных / дошедшие первичные */
  primary_avg_check: number
  /** Выручка повторных / дошедшие повторные */
  repeat_avg_check: number
  bookings_from_primary: number
  conversion_arrived_to_booked_pct: number
  avg_check: number
  revenue_total: number
  payments_total: number
  revenue_crossperiod: number
  revenue_basis?: AnalyticsRevenueBasis
  period_start: string
  period_end: string
  timezone: string
  last_sync_at?: string | null
}

export type AnalyticsTimeseriesPoint = {
  bucket: string
  label: string
  visits_total: number
  arrived_total: number
  primary_visits: number
  primary_arrived: number
  revenue_total: number
}

export type AnalyticsTimeseries = {
  group_by: AnalyticsTimeGroup
  timezone: string
  period_start: string
  period_end: string
  revenue_basis?: AnalyticsRevenueBasis
  points: AnalyticsTimeseriesPoint[]
}

export type AnalyticsBreakdownItem = {
  key: string
  label: string
  count: number
  share: number
}

export type AnalyticsBreakdown = {
  dimension: AnalyticsBreakdownDimension
  total: number
  items: AnalyticsBreakdownItem[]
  period_start: string
  period_end: string
  timezone: string
}

export type AnalyticsFilterOption = {
  value: string
  label: string
}

export type AnalyticsFiltersMeta = {
  timezone: string
  default_period_days: number
  min_date?: string | null
  max_date?: string | null
  last_sync_at?: string | null
  available_channels: AnalyticsFilterOption[]
  available_tags: AnalyticsFilterOption[]
  phase2_backlog: string[]
}

export type AnalyticsPaymentMethod = 'cash' | 'card' | 'certificate'

/** Группы paymentTypeHandle SQNS: услуги (в т.ч. сертификаты продажа) / товары. */
export type AnalyticsRevenueCategory = 'services' | 'commodities'

export type AnalyticsFilters = {
  agentId: string
  periodPreset: AnalyticsPeriodPreset
  dateFrom: string
  dateTo: string
  timezone: string
  channel: string
  clientTags: string[]
  /** По умолчанию clinical — ближе к выручке в SQNS. */
  revenueBasis: AnalyticsRevenueBasis
  /** Пустой массив = все способы оплаты. */
  paymentMethods: AnalyticsPaymentMethod[]
  /** Пустой массив = все типы (услуги+товары в clinical). */
  revenueCategories: AnalyticsRevenueCategory[]
  /** Внешний ID сотрудника SQNS; null — все. */
  resourceExternalId: number | null
}

export type AnalyticsAgentOption = {
  id: string
  name: string
}

export type ServicesTableSortBy =
  | 'service_name'
  | 'bookings_total'
  | 'arrived_total'
  | 'primary_total'
  | 'primary_arrived_total'
  | 'repeat_total'
  | 'revenue_total'
  | 'avg_check'

export type ServicesTableSortOrder = 'asc' | 'desc'

export type ServicesTableQuery = {
  dateFrom: string
  dateTo: string
  timezone: string
  channel: string
  resourceExternalId: number | string | null
  clientTags: string[]
  revenueBasis: AnalyticsRevenueBasis
  paymentMethods: AnalyticsPaymentMethod[]
  revenueCategories: AnalyticsRevenueCategory[]
  sortBy: ServicesTableSortBy
  sortOrder: ServicesTableSortOrder
  limit: number
  offset: number
}

export type AnalyticsServiceTableItem = {
  service_key: string
  service_external_id: string | number | null
  service_name: string
  service_category: string | null
  bookings_total: number
  arrived_total: number
  primary_total: number
  primary_arrived_total: number
  repeat_total: number
  repeat_arrived_total: number
  revenue_total: number
  payments_total: number
  avg_check: number
  share_bookings: number
}

export type AnalyticsServicesTableTotals = {
  services_total: number
  bookings_total: number
  arrived_total: number
  primary_total: number
  primary_arrived_total: number
  repeat_total: number
  repeat_arrived_total: number
  revenue_total: number
  payments_total: number
  avg_check: number
}

export type AnalyticsServicesTableResponse = {
  items: AnalyticsServiceTableItem[]
  totals: AnalyticsServicesTableTotals
  period_start: string
  period_end: string
  timezone: string
  revenue_basis?: AnalyticsRevenueBasis
  last_sync_at?: string | null
  total: number
  limit: number
  offset: number
  sort_by: ServicesTableSortBy
  sort_order: ServicesTableSortOrder
  resource_external_id?: number | null
}

export type CommoditiesTableSortBy =
  | 'commodity_name'
  | 'bookings_total'
  | 'arrived_total'
  | 'primary_total'
  | 'primary_arrived_total'
  | 'repeat_total'
  | 'revenue_total'
  | 'avg_check'

export type CommoditiesTableSortOrder = 'asc' | 'desc'

export type CommoditiesTableQuery = {
  dateFrom: string
  dateTo: string
  timezone: string
  channel: string
  resourceExternalId: number | string | null
  clientTags: string[]
  revenueBasis: AnalyticsRevenueBasis
  paymentMethods: AnalyticsPaymentMethod[]
  revenueCategories: AnalyticsRevenueCategory[]
  sortBy: CommoditiesTableSortBy
  sortOrder: CommoditiesTableSortOrder
  limit: number
  offset: number
}

export type AnalyticsCommodityTableItem = {
  commodity_key: string
  commodity_external_id: string | number | null
  commodity_name: string
  commodity_category: string | null
  bookings_total: number
  arrived_total: number
  primary_total: number
  primary_arrived_total: number
  repeat_total: number
  repeat_arrived_total: number
  revenue_total: number
  payments_total: number
  avg_check: number
  share_bookings: number
}

export type AnalyticsCommoditiesTableTotals = {
  commodities_total: number
  bookings_total: number
  arrived_total: number
  primary_total: number
  primary_arrived_total: number
  repeat_total: number
  repeat_arrived_total: number
  revenue_total: number
  payments_total: number
  avg_check: number
}

export type AnalyticsCommoditiesTableResponse = {
  items: AnalyticsCommodityTableItem[]
  totals: AnalyticsCommoditiesTableTotals
  period_start: string
  period_end: string
  timezone: string
  revenue_basis?: AnalyticsRevenueBasis
  last_sync_at?: string | null
  total: number
  limit: number
  offset: number
  sort_by: CommoditiesTableSortBy
  sort_order: CommoditiesTableSortOrder
  resource_external_id?: number | null
}

export type AnalyticsResourceOption = {
  id: number | string
  name: string
}

export type ToolCallHistoryStatus = 'success' | 'error' | 'unknown' | 'skipped' | 'dry_run'

export type ToolCallHistoryUser = {
  id: string | null
  name: string
  username: string | null
  email: string | null
}

export type ToolCallHistoryAgent = {
  id: string | null
  name: string
}

export type ToolCallHistoryParam = {
  key: string
  value: unknown
}

export type ToolCallHistoryItem = {
  entryType: 'tool' | 'scenario'
  id: string
  toolName: string
  toolDescription: string
  toolSettingsUrl: string | null
  status: ToolCallHistoryStatus
  invokedAt: string
  durationMs: number | null
  user: ToolCallHistoryUser
  agent: ToolCallHistoryAgent
  params: ToolCallHistoryParam[]
  requestPayload: unknown
  responsePayload: unknown
  errorPayload: unknown
  ruleId: string | null
  ruleName: string | null
  triggerPhase: string | null
  matched: boolean | null
  ruleResultStatus: string | null
  reason: string | null
}

export type ToolCallHistoryQuery = {
  dateFrom: string
  dateTo: string
  timezone: string
  agentId: string
  toolName: string
  status: '' | ToolCallHistoryStatus
  search: string
  limit: number
  offset: number
}

export type ToolCallHistoryResponse = {
  items: ToolCallHistoryItem[]
  total: number
  limit: number
  offset: number
}

// ===== Analytics v2 =====

export type StaffMember = {
  resource_external_id: number
  full_name: string
  position: string | null
  is_fired: boolean
  visits_total: number
  arrived_total: number
  no_show_total: number
  no_show_pct: number
  primary_total: number
  primary_arrived: number
  repeat_total: number
  conversion_pct: number
  revenue_total: number
  margin_total: number
  avg_check: number
  revenue_delta_pct: number | null
  visits_delta_pct: number | null
}

export type StaffOverviewResponse = {
  period_start: string
  period_end: string
  timezone: string
  items: StaffMember[]
  employees_total: number
}

export type StaffServiceLine = {
  service_external_id: number | null
  service_name: string
  bookings_total: number
  arrived_total: number
  no_show_total: number
  primary_total: number
  repeat_total: number
  revenue_total: number
  avg_check: number
  conversion_pct: number
  no_show_pct: number
}

export type StaffClientLine = {
  client_external_id: number
  full_name: string
  phone: string | null
  visits_total: number
  arrived_total: number
  no_show_total: number
  primary_total: number
  repeat_total: number
  revenue_total: number
  avg_check: number
  last_visit_at: string | null
}

export type StaffSparkPoint = {
  bucket: string
  visits: number
  revenue: number
}

export type StaffDetailResponse = {
  period_start: string
  period_end: string
  timezone: string
  staff: StaffMember
  top_services: StaffServiceLine[]
  clients: StaffClientLine[]
  sparkline: StaffSparkPoint[]
}

export type ManagerStat = {
  user_id: string | null
  full_name: string
  email: string | null
  overrides_count: number
  bot_disable_count: number
  dialogs_paused_count: number
  avg_first_response_seconds: number | null
  last_active_at: string | null
}

export type ManagersOverviewResponse = {
  period_start: string
  period_end: string
  timezone: string
  items: ManagerStat[]
  managers_total: number
  overrides_total: number
  bot_disable_total: number
}

export type ManagerOverrideEvent = {
  happened_at: string
  event_type: 'manager_message' | 'bot_disabled' | 'dialog_paused'
  session_id: string | null
  user_id: string | null
  full_name: string | null
  text_preview: string | null
}

export type ManagersTimelineResponse = {
  period_start: string
  period_end: string
  timezone: string
  events: ManagerOverrideEvent[]
}

export type BotRunsKpi = {
  runs_total: number
  success_pct: number
  failed_total: number
  avg_duration_ms: number
  prompt_tokens_total: number
  completion_tokens_total: number
  cost_usd_total: number
  cost_rub_total: number
}

export type BotToolStat = {
  tool_name: string
  calls_total: number
  error_count: number
  error_pct: number
  p50_ms: number | null
  p95_ms: number | null
  avg_ms: number | null
}

export type BotDialogQuality = {
  dialogs_total: number
  dialogs_with_manager: number
  dialogs_paused: number
  dialogs_disabled: number
  autonomy_pct: number
  avg_messages_per_dialog: number
}

export type BotBudget = {
  initial_balance_usd: number
  spent_usd: number
  remaining_usd: number
  spent_pct: number
  burn_rate_usd_per_day: number
  days_to_zero: number | null
  last_14d_usd: number
}

export type BotHealthResponse = {
  period_start: string
  period_end: string
  timezone: string
  runs: BotRunsKpi
  tools: BotToolStat[]
  dialogs: BotDialogQuality
  budget: BotBudget
}

export type FunnelStage = {
  key: string
  label: string
  value: number
}

export type FunnelResponse = {
  period_start: string
  period_end: string
  timezone: string
  stages: FunnelStage[]
}

export type InsightSeverity = 'info' | 'warning' | 'critical'
export type InsightCategory = 'staff' | 'manager' | 'bot' | 'budget' | 'dialog' | 'organization'

export type Insight = {
  code: string
  severity: InsightSeverity
  category: InsightCategory
  title: string
  body: string
  metric_value: number | null
  metric_label: string | null
  entity_type: string | null
  entity_id: string | null
  action_url: string | null
  action_tab: string | null
}

export type InsightsResponse = {
  period_start: string
  period_end: string
  timezone: string
  items: Insight[]
}

export type AiRecommendationPriority = 'high' | 'medium' | 'low'
export type AiEffortLevel = 'low' | 'medium' | 'high'
export type AiConfidenceLevel = 'low' | 'medium' | 'high'
export type AiPeriodVerdict = 'positive' | 'neutral' | 'negative'

export type AiRecommendation = {
  priority: AiRecommendationPriority
  title: string
  body: string
  root_cause: string | null
  expected_impact_rub: number | null
  effort: AiEffortLevel | null
  confidence: AiConfidenceLevel | null
  risk_if_ignored: string | null
  target_entity: string | null
  target_tab: string | null
}

export type AiRecommendationsPayload = {
  summary: string
  headline_metric: string | null
  period_verdict: AiPeriodVerdict | null
  wins: string[]
  risks: string[]
  recommendations: AiRecommendation[]
}

export type AiRecommendationsResponse = {
  period_start: string
  period_end: string
  timezone: string
  payload: AiRecommendationsPayload
  generated_at: string
  cached: boolean
  model: string | null
}

// ──────────────────────────────────────────────────────────────
// Cross-period payments table
// ──────────────────────────────────────────────────────────────

export type CrossperiodPaymentsSortBy =
  | 'payment_date'
  | 'visit_date'
  | 'amount'
  | 'client_name'
  | 'days_gap'

export type CrossperiodPaymentsQuery = {
  dateFrom: string
  dateTo: string
  timezone: string
  channel: string
  revenueBasis: AnalyticsRevenueBasis
  paymentMethods: AnalyticsPaymentMethod[]
  revenueCategories: AnalyticsRevenueCategory[]
  resourceExternalId: number | null
  clientTags: string[]
  sortBy: CrossperiodPaymentsSortBy
  sortOrder: 'asc' | 'desc'
  limit: number
  offset: number
  crossperiodOnly?: boolean
}

export type AnalyticsCrossperiodPaymentItem = {
  payment_external_id: string
  payment_date: string
  visit_external_id: string | null
  visit_date: string | null
  days_gap: number | null
  direction: 'past' | 'future' | 'unknown' | 'current'
  is_crossperiod: boolean
  amount: number
  payment_method: string | null
  payment_type_name: string | null
  payment_type_handle: string | null
  client_external_id: string | null
  client_name: string | null
  resource_external_id: number | null
  resource_name: string | null
  visit_attendance: number | null
  visit_total_price: number | null
  comment: string | null
}

export type AnalyticsCrossperiodPaymentsTotals = {
  payments_total: number
  amount_total: number
  amount_past: number
  amount_future: number
  amount_unknown: number
  clients_unique: number
}

export type AnalyticsCrossperiodPaymentsResponse = {
  timezone: string
  period_start: string
  period_end: string
  last_sync_at: string | null
  total: number
  limit: number
  offset: number
  sort_by: CrossperiodPaymentsSortBy
  sort_order: 'asc' | 'desc'
  totals: AnalyticsCrossperiodPaymentsTotals
  items: AnalyticsCrossperiodPaymentItem[]
}

// ──────────────────────────────────────────────────────────────
// Client card (patient drawer)
// ──────────────────────────────────────────────────────────────

export type AnalyticsClientCardVisit = {
  visit_external_id: string
  visit_datetime: string
  attendance: number | null
  is_primary: boolean
  resource_external_id: number | null
  resource_name: string | null
  services: string[]
  total_price: number
  paid_amount: number
  status: 'arrived' | 'no_show' | 'cancelled' | 'planned'
}

export type AnalyticsClientCardPayment = {
  payment_external_id: string
  payment_date: string
  amount: number
  payment_method: string | null
  payment_type_name: string | null
  visit_external_id: string | null
  visit_datetime: string | null
}

export type AnalyticsClientCardResponse = {
  client_external_id: string
  full_name: string | null
  phone: string | null
  email: string | null
  sex: number | null
  client_type: string | null
  tags: string[]
  first_visit_at: string | null
  last_visit_at: string | null
  visits_count: number
  arrived_count: number
  no_show_count: number
  no_show_pct: number
  lifetime_revenue: number
  avg_check: number
  top_services: { name: string; count: number }[]
  top_resources: { name: string; count: number }[]
  visits: AnalyticsClientCardVisit[]
  payments: AnalyticsClientCardPayment[]
}

// ---------- motivation ----------

export type MotivationTier = 'low' | 'norm' | 'high' | 'no_primary'

export type MotivationRule = {
  primary_pct_low: number
  primary_pct_norm: number
  primary_pct_high: number
  repeat_pct_low: number
  repeat_pct_norm: number
  repeat_pct_high: number
  avg_check_low: number
  avg_check_high: number
  include_commodities: boolean
}

export type MotivationMember = {
  resource_external_id: number
  full_name: string
  position: string | null
  is_fired: boolean
  visits_total: number
  arrived_total: number
  primary_visits: number
  repeat_visits: number
  services_revenue: number
  commodities_revenue: number
  revenue_total: number
  bonusable_revenue: number
  primary_revenue: number
  repeat_revenue: number
  primary_avg_check: number
  repeat_avg_check: number
  total_avg_check: number
  tier: MotivationTier
  applied_primary_pct: number
  applied_repeat_pct: number
  bonus_primary: number
  bonus_repeat: number
  bonus_total: number
}

export type MotivationTotals = {
  revenue_total: number
  services_revenue: number
  commodities_revenue: number
  primary_revenue: number
  repeat_revenue: number
  bonus_total: number
}

export type MotivationOverviewResponse = {
  period_start: string
  period_end: string
  timezone: string
  rule: MotivationRule
  items: MotivationMember[]
  totals: MotivationTotals
}
