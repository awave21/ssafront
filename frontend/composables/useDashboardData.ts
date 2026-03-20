import { computed, reactive, ref } from 'vue'
import { useAnalyticsApi } from '~/composables/analyticsApi'
import type {
  AnalyticsAgentOption,
  AnalyticsBreakdown,
  AnalyticsFilters,
  AnalyticsFiltersMeta,
  AnalyticsOverview,
  AnalyticsPeriodPreset,
  AnalyticsTimeseries,
} from '~/types/analytics'

type DashboardData = {
  overview: AnalyticsOverview | null
  previousOverview: AnalyticsOverview | null
  timeseries: AnalyticsTimeseries | null
  channelBreakdown: AnalyticsBreakdown | null
  tagBreakdown: AnalyticsBreakdown | null
}

const DEFAULT_PERIOD_PRESET: AnalyticsPeriodPreset = '30d'
const DEFAULT_TIMEZONE = 'UTC'

const PERIOD_DAYS: Record<Exclude<AnalyticsPeriodPreset, 'custom'>, number> = {
  '7d': 7,
  '30d': 30,
  '90d': 90,
}

const formatDate = (value: Date) => {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const normalizePreset = (raw: unknown): AnalyticsPeriodPreset => {
  if (raw === '7d' || raw === '30d' || raw === '90d' || raw === 'custom') return raw
  return DEFAULT_PERIOD_PRESET
}

const parseTags = (raw: unknown): string[] => {
  if (typeof raw !== 'string') return []
  const values = raw
    .split(',')
    .map(item => item.trim().toLowerCase())
    .filter(Boolean)

  return Array.from(new Set(values))
}

const parseDate = (raw: unknown): string => {
  if (typeof raw !== 'string') return ''
  const value = raw.trim()
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : ''
}

const fallbackErrorMessage = 'Не удалось загрузить данные аналитики'

export const useDashboardData = () => {
  const route = useRoute()
  const router = useRouter()
  const analyticsApi = useAnalyticsApi()

  const pending = ref(false)
  const error = ref<string | null>(null)
  const initialized = ref(false)
  const requestSerial = ref(0)

  const filters = reactive<AnalyticsFilters>({
    agentId: '',
    periodPreset: DEFAULT_PERIOD_PRESET,
    dateFrom: '',
    dateTo: '',
    timezone: DEFAULT_TIMEZONE,
    channel: '',
    clientTags: [],
  })

  const agentOptions = ref<AnalyticsAgentOption[]>([])
  const filtersMeta = ref<AnalyticsFiltersMeta | null>(null)
  const overview = ref<AnalyticsOverview | null>(null)
  const previousOverview = ref<AnalyticsOverview | null>(null)
  const timeseries = ref<AnalyticsTimeseries | null>(null)
  const channelBreakdown = ref<AnalyticsBreakdown | null>(null)
  const tagBreakdown = ref<AnalyticsBreakdown | null>(null)

  const availableChannels = computed(() => filtersMeta.value?.available_channels || [])
  const availableTags = computed(() => filtersMeta.value?.available_tags || [])
  const phase2Backlog = computed(() => filtersMeta.value?.phase2_backlog || [])

  const data = computed<DashboardData | null>(() => {
    if (!overview.value && !timeseries.value && !channelBreakdown.value && !tagBreakdown.value) return null
    return {
      overview: overview.value,
      previousOverview: previousOverview.value,
      timeseries: timeseries.value,
      channelBreakdown: channelBreakdown.value,
      tagBreakdown: tagBreakdown.value,
    }
  })

  const applyPresetDates = (preset: AnalyticsPeriodPreset) => {
    if (preset === 'custom') return
    const days = PERIOD_DAYS[preset]
    const dateTo = new Date()
    const dateFrom = new Date(dateTo)
    dateFrom.setDate(dateFrom.getDate() - days + 1)
    filters.dateFrom = formatDate(dateFrom)
    filters.dateTo = formatDate(dateTo)
  }

  const applyQueryFilters = () => {
    const query = route.query
    const queryPreset = normalizePreset(query.period)

    filters.agentId = typeof query.agent === 'string' ? query.agent : ''
    filters.periodPreset = queryPreset
    filters.channel = typeof query.channel === 'string' ? query.channel : ''
    filters.clientTags = parseTags(query.tags)
    filters.timezone = typeof query.tz === 'string' && query.tz.trim() ? query.tz.trim() : DEFAULT_TIMEZONE

    const queryFrom = parseDate(query.from)
    const queryTo = parseDate(query.to)
    if (queryPreset === 'custom' && queryFrom && queryTo) {
      filters.dateFrom = queryFrom
      filters.dateTo = queryTo
      return
    }

    if (queryPreset === 'custom') {
      filters.periodPreset = DEFAULT_PERIOD_PRESET
      applyPresetDates(DEFAULT_PERIOD_PRESET)
      return
    }

    applyPresetDates(queryPreset)
  }

  const syncQueryWithFilters = async () => {
    const query: Record<string, string> = {}
    if (filters.agentId) query.agent = filters.agentId
    if (filters.periodPreset !== DEFAULT_PERIOD_PRESET) query.period = filters.periodPreset
    if (filters.dateFrom) query.from = filters.dateFrom
    if (filters.dateTo) query.to = filters.dateTo
    if (filters.channel) query.channel = filters.channel
    if (filters.clientTags.length) query.tags = filters.clientTags.join(',')
    if (filters.timezone && filters.timezone !== DEFAULT_TIMEZONE) query.tz = filters.timezone
    await router.replace({ query })
  }

  const clearData = () => {
    overview.value = null
    previousOverview.value = null
    timeseries.value = null
    channelBreakdown.value = null
    tagBreakdown.value = null
  }

  const fetchFiltersMeta = async () => {
    if (!filters.agentId) return null
    const meta = await analyticsApi.getFiltersMeta(filters.agentId, filters.timezone)
    filtersMeta.value = meta
    if (!filters.timezone) {
      filters.timezone = meta.timezone || DEFAULT_TIMEZONE
    }
    return meta
  }

  const refresh = async () => {
    if (!filters.agentId) {
      clearData()
      return
    }

    const currentRequest = ++requestSerial.value
    pending.value = true
    error.value = null

    try {
      await fetchFiltersMeta()

      const requestFilters = {
        dateFrom: filters.dateFrom,
        dateTo: filters.dateTo,
        timezone: filters.timezone,
        channel: filters.channel,
        clientTags: filters.clientTags,
      }

      // Calculate previous period
      const currentFrom = new Date(filters.dateFrom)
      const currentTo = new Date(filters.dateTo)
      const diffMs = currentTo.getTime() - currentFrom.getTime()
      const prevTo = new Date(currentFrom.getTime() - 1)
      const prevFrom = new Date(prevTo.getTime() - diffMs)

      const prevRequestFilters = {
        ...requestFilters,
        dateFrom: formatDate(prevFrom),
        dateTo: formatDate(prevTo),
      }

      const [overviewResponse, prevOverviewResponse, timeseriesResponse, channelResponse, tagResponse] = await Promise.all([
        analyticsApi.getOverview(filters.agentId, requestFilters),
        analyticsApi.getOverview(filters.agentId, prevRequestFilters).catch(() => null),
        analyticsApi.getTimeseries(filters.agentId, requestFilters, 'day'),
        analyticsApi.getBreakdown(filters.agentId, requestFilters, 'channel', 10),
        analyticsApi.getBreakdown(filters.agentId, requestFilters, 'tag', 10),
      ])

      if (currentRequest !== requestSerial.value) return

      overview.value = overviewResponse
      previousOverview.value = prevOverviewResponse
      timeseries.value = timeseriesResponse
      channelBreakdown.value = channelResponse
      tagBreakdown.value = tagResponse
    } catch (err: any) {
      if (currentRequest !== requestSerial.value) return
      clearData()
      error.value = err?.data?.message || err?.message || fallbackErrorMessage
    } finally {
      if (currentRequest === requestSerial.value) {
        pending.value = false
      }
    }
  }

  const updateFilters = async (patch: Partial<AnalyticsFilters>) => {
    if (patch.agentId !== undefined) {
      filters.agentId = patch.agentId
      filters.channel = ''
      filters.clientTags = []
    }

    if (patch.periodPreset !== undefined) {
      filters.periodPreset = patch.periodPreset
      applyPresetDates(filters.periodPreset)
    }

    if (patch.dateFrom !== undefined) {
      filters.dateFrom = patch.dateFrom
      filters.periodPreset = 'custom'
    }

    if (patch.dateTo !== undefined) {
      filters.dateTo = patch.dateTo
      filters.periodPreset = 'custom'
    }

    if (patch.channel !== undefined) {
      filters.channel = patch.channel
    }

    if (patch.clientTags !== undefined) {
      filters.clientTags = Array.from(new Set(patch.clientTags.map(item => item.trim().toLowerCase()).filter(Boolean)))
    }

    if (patch.timezone !== undefined) {
      filters.timezone = patch.timezone || DEFAULT_TIMEZONE
    }

    if (initialized.value) {
      await syncQueryWithFilters()
      await refresh()
    }
  }

  const resetFilters = async () => {
    filters.periodPreset = DEFAULT_PERIOD_PRESET
    filters.channel = ''
    filters.clientTags = []
    applyPresetDates(filters.periodPreset)
    if (initialized.value) {
      await syncQueryWithFilters()
      await refresh()
    }
  }

  const initialize = async () => {
    if (initialized.value) return

    pending.value = true
    error.value = null

    try {
      const agents = await analyticsApi.getAgentsForFilter()
      agentOptions.value = agents

      applyQueryFilters()
      if (!filters.agentId && agents.length) {
        filters.agentId = agents[0].id
      }

      if (!filters.dateFrom || !filters.dateTo) {
        applyPresetDates(filters.periodPreset)
      }

      initialized.value = true
      await syncQueryWithFilters()
      await refresh()
    } catch (err: any) {
      clearData()
      error.value = err?.data?.message || err?.message || fallbackErrorMessage
      pending.value = false
    }
  }

  return {
    data,
    pending,
    error,
    initialized,
    filters,
    filtersMeta,
    agentOptions,
    availableChannels,
    availableTags,
    phase2Backlog,
    overview,
    previousOverview,
    timeseries,
    channelBreakdown,
    tagBreakdown,
    initialize,
    refresh,
    updateFilters,
    resetFilters,
  }
}
