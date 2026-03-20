import { computed, reactive, ref, watch, type Ref } from 'vue'
import { useAnalyticsApi } from '~/composables/analyticsApi'
import type {
  AnalyticsFilterOption,
  AnalyticsResourceOption,
  AnalyticsServiceTableItem,
  AnalyticsServicesTableResponse,
  AnalyticsServicesTableTotals,
  ServicesTableQuery,
  ServicesTableSortBy,
  ServicesTableSortOrder,
} from '~/types/analytics'

const DEFAULT_LIMIT = 50
const DEFAULT_SORT_BY: ServicesTableSortBy = 'bookings_total'
const DEFAULT_SORT_ORDER: ServicesTableSortOrder = 'desc'
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

const parseResourceId = (raw: unknown): number | string | null => {
  if (raw === undefined || raw === null || raw === '') return null
  if (typeof raw === 'number') return raw
  if (typeof raw === 'string') {
    const trimmed = raw.trim()
    if (!trimmed) return null
    const numeric = Number(trimmed)
    return Number.isFinite(numeric) ? numeric : trimmed
  }
  return null
}

const parseTags = (raw: unknown): string[] => {
  if (typeof raw !== 'string') return []
  return Array.from(new Set(raw.split(',').map(item => item.trim().toLowerCase()).filter(Boolean)))
}

const escapeCsv = (value: unknown) => {
  const text = String(value ?? '')
  if (text.includes('"') || text.includes(',') || text.includes('\n')) return `"${text.replace(/"/g, '""')}"`
  return text
}

export const useServicesAnalyticsTable = (agentId: Readonly<Ref<string>>) => {
  const route = useRoute()
  const router = useRouter()
  const analyticsApi = useAnalyticsApi()
  const { error: toastError } = useToast()

  const channels = ref<AnalyticsFilterOption[]>([])
  const tags = ref<AnalyticsFilterOption[]>([])
  const resources = ref<AnalyticsResourceOption[]>([])
  const isSyncingRoute = ref(false)

  const query = reactive<ServicesTableQuery>({
    dateFrom: '',
    dateTo: '',
    timezone: DEFAULT_TIMEZONE,
    channel: '',
    resourceExternalId: null,
    clientTags: [],
    sortBy: DEFAULT_SORT_BY,
    sortOrder: DEFAULT_SORT_ORDER,
    limit: DEFAULT_LIMIT,
    offset: 0,
  })

  const applyDefaultDates = () => {
    if (query.dateFrom && query.dateTo) return
    const dateTo = new Date()
    const dateFrom = new Date(dateTo)
    dateFrom.setDate(dateFrom.getDate() - 29)
    query.dateFrom = formatDate(dateFrom)
    query.dateTo = formatDate(dateTo)
  }

  const applyRouteQuery = () => {
    query.dateFrom = parseDate(route.query.st_from)
    query.dateTo = parseDate(route.query.st_to)
    query.timezone = typeof route.query.st_tz === 'string' && route.query.st_tz.trim()
      ? route.query.st_tz.trim()
      : DEFAULT_TIMEZONE
    query.channel = typeof route.query.st_channel === 'string' ? route.query.st_channel : ''

    query.resourceExternalId = parseResourceId(route.query.st_resource)

    query.clientTags = parseTags(route.query.st_tags)
    query.limit = Math.max(1, Math.min(200, parseNumber(route.query.st_limit, DEFAULT_LIMIT)))
    query.offset = Math.max(0, parseNumber(route.query.st_offset, 0))

    const rawSortBy = route.query.st_sort_by
    const allowedSortBy: ServicesTableSortBy[] = [
      'service_name',
      'bookings_total',
      'arrived_total',
      'primary_total',
      'primary_arrived_total',
      'repeat_total',
      'revenue_total',
      'avg_check',
    ]
    query.sortBy = typeof rawSortBy === 'string' && allowedSortBy.includes(rawSortBy as ServicesTableSortBy)
      ? (rawSortBy as ServicesTableSortBy)
      : DEFAULT_SORT_BY

    const rawSortOrder = route.query.st_sort_order
    query.sortOrder = rawSortOrder === 'asc' || rawSortOrder === 'desc' ? rawSortOrder : DEFAULT_SORT_ORDER

    applyDefaultDates()
  }

  applyRouteQuery()

  const syncRouteQuery = async () => {
    if (isSyncingRoute.value) return
    isSyncingRoute.value = true

    const nextQuery = { ...route.query } as Record<string, any>
    nextQuery.st_from = query.dateFrom
    nextQuery.st_to = query.dateTo
    nextQuery.st_tz = query.timezone !== DEFAULT_TIMEZONE ? query.timezone : undefined
    nextQuery.st_channel = query.channel || undefined
    nextQuery.st_resource = query.resourceExternalId ?? undefined
    nextQuery.st_tags = query.clientTags.length ? query.clientTags.join(',') : undefined
    nextQuery.st_sort_by = query.sortBy !== DEFAULT_SORT_BY ? query.sortBy : undefined
    nextQuery.st_sort_order = query.sortOrder !== DEFAULT_SORT_ORDER ? query.sortOrder : undefined
    nextQuery.st_limit = query.limit !== DEFAULT_LIMIT ? String(query.limit) : undefined
    nextQuery.st_offset = query.offset > 0 ? String(query.offset) : undefined

    Object.keys(nextQuery).forEach((key) => {
      if (nextQuery[key] === undefined || nextQuery[key] === '') delete nextQuery[key]
    })

    await router.replace({ query: nextQuery })
    isSyncingRoute.value = false
  }

  const fetchFiltersOptions = async () => {
    if (!agentId.value) return
    const [meta, sqnsResources] = await Promise.all([
      analyticsApi.getFiltersMeta(agentId.value, query.timezone).catch(() => null),
      analyticsApi.getSqnsResourcesForFilter(agentId.value).catch(() => []),
    ])

    channels.value = meta?.available_channels || []
    tags.value = meta?.available_tags || []
    resources.value = sqnsResources
    if (meta?.timezone && !query.timezone) query.timezone = meta.timezone
  }

  const requestQueryKey = computed(() => JSON.stringify({
    agentId: agentId.value,
    dateFrom: query.dateFrom,
    dateTo: query.dateTo,
    timezone: query.timezone,
    channel: query.channel,
    resourceExternalId: query.resourceExternalId,
    clientTags: query.clientTags,
    sortBy: query.sortBy,
    sortOrder: query.sortOrder,
    limit: query.limit,
    offset: query.offset,
  }))

  const {
    data,
    pending,
    error,
    refresh,
  } = useAsyncData<AnalyticsServicesTableResponse | null>(
    'analytics-services-table',
    async () => {
      if (!agentId.value) return null
      await syncRouteQuery()
      return await analyticsApi.getServicesTable(agentId.value, query)
    },
    {
      immediate: false,
      watch: [requestQueryKey],
      default: () => null,
      dedupe: 'defer',
    },
  )

  watch(agentId, async (nextAgentId) => {
    if (!nextAgentId) return
    query.offset = 0
    await fetchFiltersOptions()
    await refresh()
  }, { immediate: true })

  const items = computed<AnalyticsServiceTableItem[]>(() => data.value?.items || [])
  const totals = computed<AnalyticsServicesTableTotals | null>(() => data.value?.totals || null)
  const totalItems = computed(() => data.value?.total || 0)
  const currentPage = computed(() => Math.floor(query.offset / query.limit) + 1)
  const totalPages = computed(() => Math.max(1, Math.ceil(totalItems.value / query.limit)))

  const setSort = (sortBy: ServicesTableSortBy) => {
    if (query.sortBy === sortBy) {
      query.sortOrder = query.sortOrder === 'asc' ? 'desc' : 'asc'
    } else {
      query.sortBy = sortBy
      query.sortOrder = 'desc'
    }
    query.offset = 0
  }

  const setPage = (page: number) => {
    const normalized = Math.max(1, Math.min(totalPages.value, page))
    query.offset = (normalized - 1) * query.limit
  }

  const updateQuery = (patch: Partial<ServicesTableQuery>) => {
    if (patch.dateFrom !== undefined) query.dateFrom = patch.dateFrom
    if (patch.dateTo !== undefined) query.dateTo = patch.dateTo
    if (patch.timezone !== undefined) query.timezone = patch.timezone
    if (patch.channel !== undefined) query.channel = patch.channel
    if (patch.resourceExternalId !== undefined) query.resourceExternalId = patch.resourceExternalId
    if (patch.clientTags !== undefined) query.clientTags = patch.clientTags
    if (patch.limit !== undefined) query.limit = patch.limit
    query.offset = 0
  }

  const toCsvRows = (rows: AnalyticsServiceTableItem[]) => {
    const headers = [
      'Услуга',
      'Категория',
      'Записи',
      'Дошедшие',
      'Первичные',
      'Первичные дошедшие',
      'Повторные',
      'Повторные дошедшие',
      'Конверсия доходимости %',
      'Выручка',
      'Платежи',
      'Средний чек',
      'Доля записей %',
    ]

    const body = rows.map((item) => {
      const conversion = item.bookings_total > 0 ? (item.arrived_total / item.bookings_total) * 100 : 0
      return [
        item.service_name,
        item.service_category || '—',
        item.bookings_total,
        item.arrived_total,
        item.primary_total,
        item.primary_arrived_total,
        item.repeat_total,
        item.repeat_arrived_total,
        conversion.toFixed(1),
        item.revenue_total.toFixed(2),
        item.payments_total,
        item.avg_check.toFixed(2),
        (item.share_bookings * 100).toFixed(1),
      ]
    })

    return [headers, ...body].map(line => line.map(escapeCsv).join(',')).join('\n')
  }

  const downloadCsv = (content: string, filename: string) => {
    const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  }

  const exportCurrentPageCsv = () => {
    downloadCsv(toCsvRows(items.value), `services-table-page-${currentPage.value}.csv`)
  }

  const exportAllCsv = async () => {
    if (!agentId.value) return
    try {
      const allRows: AnalyticsServiceTableItem[] = []
      const batchLimit = 200
      let offset = 0
      let total = 0

      do {
        const response = await analyticsApi.getServicesTable(agentId.value, {
          ...query,
          limit: batchLimit,
          offset,
        })
        total = response.total
        allRows.push(...response.items)
        offset += batchLimit
      } while (offset < total)

      downloadCsv(toCsvRows(allRows), 'services-table-all.csv')
    } catch (err) {
      toastError('Не удалось экспортировать CSV', 'Попробуйте снова через несколько секунд.')
    }
  }

  const retry = async () => {
    await refresh()
  }

  return {
    query,
    pending,
    error,
    items,
    totals,
    totalItems,
    currentPage,
    totalPages,
    channels,
    tags,
    resources,
    refresh: retry,
    setSort,
    setPage,
    updateQuery,
    exportCurrentPageCsv,
    exportAllCsv,
  }
}
