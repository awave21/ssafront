export type AnalyticsTimeGroup = 'day' | 'week' | 'month'
export type AnalyticsBreakdownDimension = 'channel' | 'tag' | 'client_type'
export type AnalyticsPeriodPreset = '7d' | '30d' | '90d' | 'custom'

export type AnalyticsOverview = {
  visits_total: number
  arrived_total: number
  arrived_primary: number
  repeat_total: number
  bookings_from_primary: number
  bookings_from_existing_patients: number
  conversion_arrived_to_booked_pct: number
  avg_check: number
  revenue_total: number
  payments_total: number
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
  revenue_total: number
}

export type AnalyticsTimeseries = {
  group_by: AnalyticsTimeGroup
  timezone: string
  period_start: string
  period_end: string
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

export type AnalyticsFilters = {
  agentId: string
  periodPreset: AnalyticsPeriodPreset
  dateFrom: string
  dateTo: string
  timezone: string
  channel: string
  clientTags: string[]
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
  last_sync_at?: string | null
  total: number
  limit: number
  offset: number
  sort_by: ServicesTableSortBy
  sort_order: ServicesTableSortOrder
  resource_external_id?: number | null
}

export type AnalyticsResourceOption = {
  id: number | string
  name: string
}

export type ToolCallHistoryStatus = 'success' | 'error' | 'unknown'

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
