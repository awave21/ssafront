import { computed, reactive, ref, watch } from 'vue'
import { useAnalyticsApi } from '~/composables/analyticsApi'
import type {
  AnalyticsAgentOption,
  ToolCallHistoryItem,
  ToolCallHistoryParam,
  ToolCallHistoryQuery,
  ToolCallHistoryResponse,
  ToolCallHistoryStatus,
} from '~/types/analytics'

const DEFAULT_LIMIT = 20
const DEFAULT_TIMEZONE = 'UTC'

const formatDate = (value: Date) => {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const parseDate = (raw: unknown) => {
  if (typeof raw !== 'string') return ''
  return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : ''
}

const parseNumber = (raw: unknown, fallback: number) => {
  const value = Number(raw)
  return Number.isFinite(value) ? value : fallback
}

const toStatus = (raw: unknown): ToolCallHistoryStatus => {
  if (raw === true) return 'success'
  if (raw === false) return 'error'
  const normalized = String(raw || '').toLowerCase()
  if (['ok', 'success', 'succeeded', 'done'].includes(normalized)) return 'success'
  if (['error', 'failed', 'failure'].includes(normalized)) return 'error'
  if (normalized === 'skipped' || normalized === 'skip') return 'skipped'
  if (normalized === 'dry_run') return 'dry_run'
  return 'unknown'
}

const normalizeParams = (raw: unknown): ToolCallHistoryParam[] => {
  if (Array.isArray(raw)) {
    return raw
      .map((entry) => {
        if (!entry || typeof entry !== 'object') return null
        const item = entry as Record<string, unknown>
        const key = String(item.key || item.name || '')
        if (!key) return null
        return { key, value: item.value }
      })
      .filter((entry): entry is ToolCallHistoryParam => entry !== null)
  }

  if (raw && typeof raw === 'object') {
    return Object.entries(raw as Record<string, unknown>).map(([key, value]) => ({ key, value }))
  }

  return []
}

const normalizeItem = (raw: unknown, index: number): ToolCallHistoryItem => {
  const record = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const toolRecord = (record.tool && typeof record.tool === 'object' ? record.tool : {}) as Record<string, unknown>
  const userRecord = (
    record.user_info && typeof record.user_info === 'object'
      ? record.user_info
      : record.user && typeof record.user === 'object'
        ? record.user
        : {}
  ) as Record<string, unknown>
  const agentRecord = (record.agent && typeof record.agent === 'object' ? record.agent : {}) as Record<string, unknown>

  const paramsRaw = record.params || record.parameters || record.args || record.payload || {}
  const params = normalizeParams(paramsRaw)

  const toolName = String(record.tool_name || toolRecord.name || 'Unknown tool')
  const firstName = String(userRecord.first_name || '').trim()
  const lastName = String(userRecord.last_name || '').trim()
  const fullName = `${firstName} ${lastName}`.trim()
  const entryType: 'tool' | 'scenario' = record.entry_type === 'scenario' ? 'scenario' : 'tool'
  const defaultUserName = entryType === 'scenario' ? 'Сценарий (автоматика)' : 'Неизвестный пользователь'

  return {
    entryType,
    id: String(record.id || record.tool_call_id || `${toolName}-${index}`),
    toolName,
    toolDescription: String(record.tool_description || toolRecord.description || 'Описание отсутствует'),
    toolSettingsUrl: String(
      record.tool_settings_url ||
      toolRecord.settings_url ||
      toolRecord.edit_url ||
      record.tool_url ||
      '',
    ).trim() || null,
    status: toStatus(record.status || record.rule_result_status || record.result_status || record.success),
    invokedAt: String(record.invoked_at || record.created_at || record.timestamp || ''),
    durationMs: Number.isFinite(Number(record.duration_ms || record.latency_ms))
      ? Number(record.duration_ms || record.latency_ms)
      : null,
    user: {
      id: userRecord.id ? String(userRecord.id) : null,
      name: String(userRecord.name || fullName || userRecord.username || defaultUserName),
      username: userRecord.username ? String(userRecord.username) : null,
      email: userRecord.email ? String(userRecord.email) : null,
    },
    agent: {
      id: agentRecord.id ? String(agentRecord.id) : null,
      name: String(agentRecord.name || record.agent_name || '—'),
    },
    params,
    requestPayload: record.request_payload || record.payload || record.args || null,
    responsePayload: record.response_payload || record.result || null,
    errorPayload: record.error_payload || record.error || null,
    ruleId: record.rule_id != null ? String(record.rule_id) : null,
    ruleName: record.rule_name != null ? String(record.rule_name) : null,
    triggerPhase: record.trigger_phase != null ? String(record.trigger_phase) : null,
    matched: typeof record.matched === 'boolean' ? record.matched : null,
    ruleResultStatus: record.rule_result_status != null ? String(record.rule_result_status) : null,
    reason: record.reason != null ? String(record.reason) : null,
  }
}

const normalizeResponse = (raw: unknown): ToolCallHistoryResponse => {
  const payload = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const sourceItems = Array.isArray(payload.items)
    ? payload.items
    : Array.isArray(payload.logs)
      ? payload.logs
      : Array.isArray(payload.records)
        ? payload.records
        : Array.isArray(raw)
          ? raw
          : []

  const items = sourceItems.map((item, index) => normalizeItem(item, index))
  const limit = parseNumber(payload.limit, DEFAULT_LIMIT)
  const offset = parseNumber(payload.offset, 0)
  const total = parseNumber(payload.total, items.length)

  return {
    items,
    total,
    limit,
    offset,
  }
}

export const useToolCallsHistory = () => {
  const route = useRoute()
  const router = useRouter()
  const analyticsApi = useAnalyticsApi()

  const query = reactive<ToolCallHistoryQuery>({
    dateFrom: '',
    dateTo: '',
    timezone: DEFAULT_TIMEZONE,
    agentId: '',
    toolName: '',
    status: '',
    search: '',
    limit: DEFAULT_LIMIT,
    offset: 0,
  })

  const agents = ref<AnalyticsAgentOption[]>([])
  const isSyncingRoute = ref(false)

  const applyDefaultDates = () => {
    if (query.dateFrom && query.dateTo) return
    const dateTo = new Date()
    const dateFrom = new Date(dateTo)
    dateFrom.setDate(dateFrom.getDate() - 6)
    query.dateFrom = formatDate(dateFrom)
    query.dateTo = formatDate(dateTo)
  }

  const applyRouteQuery = () => {
    query.dateFrom = parseDate(route.query.tch_from)
    query.dateTo = parseDate(route.query.tch_to)
    query.timezone = typeof route.query.tch_tz === 'string' && route.query.tch_tz.trim()
      ? route.query.tch_tz.trim()
      : DEFAULT_TIMEZONE
    query.agentId = typeof route.query.tch_agent === 'string' ? route.query.tch_agent : ''
    query.toolName = typeof route.query.tch_tool === 'string' ? route.query.tch_tool : ''
    query.status = route.query.tch_status === 'success' || route.query.tch_status === 'error'
      ? route.query.tch_status
      : ''
    query.search = typeof route.query.tch_search === 'string' ? route.query.tch_search : ''
    query.limit = Math.max(1, Math.min(100, parseNumber(route.query.tch_limit, DEFAULT_LIMIT)))
    query.offset = Math.max(0, parseNumber(route.query.tch_offset, 0))
    applyDefaultDates()
  }

  applyRouteQuery()

  const syncRouteQuery = async () => {
    if (isSyncingRoute.value) return
    isSyncingRoute.value = true

    const nextQuery = { ...route.query } as Record<string, any>
    nextQuery.tch_from = query.dateFrom
    nextQuery.tch_to = query.dateTo
    nextQuery.tch_tz = query.timezone !== DEFAULT_TIMEZONE ? query.timezone : undefined
    nextQuery.tch_agent = query.agentId || undefined
    nextQuery.tch_tool = query.toolName || undefined
    nextQuery.tch_status = query.status || undefined
    nextQuery.tch_search = query.search || undefined
    nextQuery.tch_limit = query.limit !== DEFAULT_LIMIT ? String(query.limit) : undefined
    nextQuery.tch_offset = query.offset > 0 ? String(query.offset) : undefined

    Object.keys(nextQuery).forEach((key) => {
      if (nextQuery[key] === undefined || nextQuery[key] === '') delete nextQuery[key]
    })

    await router.replace({ query: nextQuery })
    isSyncingRoute.value = false
  }

  const requestKey = computed(() => JSON.stringify({
    dateFrom: query.dateFrom,
    dateTo: query.dateTo,
    timezone: query.timezone,
    agentId: query.agentId,
    toolName: query.toolName,
    status: query.status,
    search: query.search,
    limit: query.limit,
    offset: query.offset,
  }))

  const {
    data,
    pending,
    error,
    refresh,
  } = useAsyncData<ToolCallHistoryResponse>(
    'tool-calls-history',
    async () => {
      await syncRouteQuery()
      const response = await analyticsApi.getToolCallsHistory(query)
      return normalizeResponse(response)
    },
    {
      watch: [requestKey],
      immediate: false,
      default: () => ({ items: [], total: 0, limit: query.limit, offset: query.offset }),
      dedupe: 'defer',
    },
  )

  const fetchAgents = async () => {
    try {
      agents.value = await analyticsApi.getAgentsForFilter()
    } catch {
      agents.value = []
    }
  }

  const initialize = async () => {
    await fetchAgents()
    await refresh()
  }

  const items = computed(() => data.value?.items || [])
  const total = computed(() => data.value?.total || 0)
  const currentPage = computed(() => Math.floor(query.offset / query.limit) + 1)
  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / query.limit)))
  const toolOptions = computed(() =>
    Array.from(new Set(items.value.map((item) => item.toolName).filter(Boolean))).sort((a, b) => a.localeCompare(b, 'ru')),
  )

  const updateQuery = (patch: Partial<ToolCallHistoryQuery>) => {
    if (patch.dateFrom !== undefined) query.dateFrom = patch.dateFrom
    if (patch.dateTo !== undefined) query.dateTo = patch.dateTo
    if (patch.timezone !== undefined) query.timezone = patch.timezone
    if (patch.agentId !== undefined) query.agentId = patch.agentId
    if (patch.toolName !== undefined) query.toolName = patch.toolName
    if (patch.status !== undefined) query.status = patch.status
    if (patch.search !== undefined) query.search = patch.search
    if (patch.limit !== undefined) query.limit = patch.limit
    query.offset = 0
  }

  const setPage = (page: number) => {
    const normalized = Math.max(1, Math.min(totalPages.value, page))
    query.offset = (normalized - 1) * query.limit
  }

  return {
    query,
    agents,
    items,
    total,
    currentPage,
    totalPages,
    toolOptions,
    pending,
    error,
    initialize,
    refresh,
    updateQuery,
    setPage,
  }
}
