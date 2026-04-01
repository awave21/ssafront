import { computed, reactive, ref, watch, type Ref } from 'vue'
import { useAnalyticsApi } from '~/composables/analyticsApi'
import { routerReplaceSafe } from '~/utils/routerSafe'
import type {
  AnalyticsCommoditiesTableResponse,
  AnalyticsCommoditiesTableTotals,
  AnalyticsCommodityTableItem,
  AnalyticsFilterOption,
  AnalyticsFilters,
  AnalyticsResourceOption,
  CommoditiesTableQuery,
  CommoditiesTableSortBy,
  CommoditiesTableSortOrder,
} from '~/types/analytics'

export type UseCommoditiesAnalyticsTableOptions = {
  /** Период / канал / теги / TZ берутся из дашборда; в URL не пишутся ct_from, ct_to, … */
  syncFromDashboard?: AnalyticsFilters
}

const DEFAULT_LIMIT = 50
const DEFAULT_SORT_BY: CommoditiesTableSortBy = 'bookings_total'
const DEFAULT_SORT_ORDER: CommoditiesTableSortOrder = 'desc'
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

export const useCommoditiesAnalyticsTable = (
  agentId: Readonly<Ref<string>>,
  options?: UseCommoditiesAnalyticsTableOptions,
) => {
  const syncFromDashboard = options?.syncFromDashboard
  const route = useRoute()
  const router = useRouter()
  const analyticsApi = useAnalyticsApi()
  const { error: toastError } = useToast()

  const channels = ref<AnalyticsFilterOption[]>([])
  const tags = ref<AnalyticsFilterOption[]>([])
  const resources = ref<AnalyticsResourceOption[]>([])
  const isSyncingRoute = ref(false)

  const query = reactive<CommoditiesTableQuery>({
    dateFrom: '',
    dateTo: '',
    timezone: DEFAULT_TIMEZONE,
    channel: '',
    resourceExternalId: null,
    clientTags: [],
    revenueBasis: 'clinical',
    paymentMethods: [],
    revenueCategories: [],
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

  const applyTableParamsFromRoute = () => {
    query.resourceExternalId = parseResourceId(route.query.ct_resource)
    query.limit = Math.max(1, Math.min(200, parseNumber(route.query.ct_limit, DEFAULT_LIMIT)))
    query.offset = Math.max(0, parseNumber(route.query.ct_offset, 0))

    const rawSortBy = route.query.ct_sort_by
    const allowedSortBy: CommoditiesTableSortBy[] = [
      'commodity_name',
      'bookings_total',
      'arrived_total',
      'primary_total',
      'primary_arrived_total',
      'repeat_total',
      'revenue_total',
      'avg_check',
    ]
    query.sortBy = typeof rawSortBy === 'string' && allowedSortBy.includes(rawSortBy as CommoditiesTableSortBy)
      ? (rawSortBy as CommoditiesTableSortBy)
      : DEFAULT_SORT_BY

    const rawSortOrder = route.query.ct_sort_order
    query.sortOrder = rawSortOrder === 'asc' || rawSortOrder === 'desc' ? rawSortOrder : DEFAULT_SORT_ORDER
  }

  const patchQueryFromDashboard = () => {
    if (!syncFromDashboard) return
    if (!syncFromDashboard.dateFrom || !syncFromDashboard.dateTo) return
    query.dateFrom = syncFromDashboard.dateFrom
    query.dateTo = syncFromDashboard.dateTo
    query.timezone = syncFromDashboard.timezone?.trim() || DEFAULT_TIMEZONE
    query.channel = syncFromDashboard.channel || ''
    query.clientTags = [...syncFromDashboard.clientTags]
    query.revenueBasis = syncFromDashboard.revenueBasis
    query.paymentMethods = [...(syncFromDashboard.paymentMethods ?? [])]
    query.revenueCategories = [...(syncFromDashboard.revenueCategories ?? [])]
    query.resourceExternalId = syncFromDashboard.resourceExternalId
  }

  const applyRouteQuery = () => {
    applyTableParamsFromRoute()
    if (syncFromDashboard) {
      patchQueryFromDashboard()
      return
    }
    query.dateFrom = parseDate(route.query.ct_from)
    query.dateTo = parseDate(route.query.ct_to)
    query.timezone = typeof route.query.ct_tz === 'string' && route.query.ct_tz.trim()
      ? route.query.ct_tz.trim()
      : DEFAULT_TIMEZONE
    query.channel = typeof route.query.ct_channel === 'string' ? route.query.ct_channel : ''
    query.clientTags = parseTags(route.query.ct_tags)
    applyDefaultDates()
  }

  applyRouteQuery()

  if (syncFromDashboard) {
    watch(
      () => [
        syncFromDashboard.dateFrom,
        syncFromDashboard.dateTo,
        syncFromDashboard.timezone,
        syncFromDashboard.channel,
        [...syncFromDashboard.clientTags].slice().sort().join(','),
        syncFromDashboard.revenueBasis,
        [...(syncFromDashboard.paymentMethods ?? [])].slice().sort().join(','),
        [...(syncFromDashboard.revenueCategories ?? [])].slice().sort().join(','),
        syncFromDashboard.resourceExternalId,
      ],
      () => {
        patchQueryFromDashboard()
        query.offset = 0
      },
      { flush: 'sync', immediate: true },
    )
  }

  const syncRouteQuery = async () => {
    if (isSyncingRoute.value) return
    isSyncingRoute.value = true

    const nextQuery = { ...route.query } as Record<string, any>
    if (syncFromDashboard) {
      delete nextQuery.ct_from
      delete nextQuery.ct_to
      delete nextQuery.ct_tz
      delete nextQuery.ct_channel
      delete nextQuery.ct_tags
    } else {
      nextQuery.ct_from = query.dateFrom
      nextQuery.ct_to = query.dateTo
      nextQuery.ct_tz = query.timezone !== DEFAULT_TIMEZONE ? query.timezone : undefined
      nextQuery.ct_channel = query.channel || undefined
      nextQuery.ct_tags = query.clientTags.length ? query.clientTags.join(',') : undefined
    }
    nextQuery.ct_resource = query.resourceExternalId ?? undefined
    nextQuery.ct_sort_by = query.sortBy !== DEFAULT_SORT_BY ? query.sortBy : undefined
    nextQuery.ct_sort_order = query.sortOrder !== DEFAULT_SORT_ORDER ? query.sortOrder : undefined
    nextQuery.ct_limit = query.limit !== DEFAULT_LIMIT ? String(query.limit) : undefined
    nextQuery.ct_offset = query.offset > 0 ? String(query.offset) : undefined

    Object.keys(nextQuery).forEach((key) => {
      if (nextQuery[key] === undefined || nextQuery[key] === '') delete nextQuery[key]
    })

    await routerReplaceSafe(router, { query: nextQuery })
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
    revenueBasis: query.revenueBasis,
    paymentMethods: query.paymentMethods,
    revenueCategories: query.revenueCategories,
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
  } = useAsyncData<AnalyticsCommoditiesTableResponse | null>(
    'analytics-commodities-table',
    async () => {
      if (!agentId.value) return null
      if (syncFromDashboard && (!query.dateFrom || !query.dateTo)) return null
      await syncRouteQuery()
      return await analyticsApi.getCommoditiesTable(agentId.value, query)
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
    if (syncFromDashboard && (!query.dateFrom || !query.dateTo)) return
    await refresh()
  }, { immediate: true })

  const items = computed<AnalyticsCommodityTableItem[]>(() => data.value?.items || [])
  const totals = computed<AnalyticsCommoditiesTableTotals | null>(() => data.value?.totals || null)
  const totalItems = computed(() => data.value?.total || 0)
  const currentPage = computed(() => Math.floor(query.offset / query.limit) + 1)
  const totalPages = computed(() => Math.max(1, Math.ceil(totalItems.value / query.limit)))

  const setSort = (sortBy: CommoditiesTableSortBy) => {
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

  const updateQuery = (patch: Partial<CommoditiesTableQuery>) => {
    if (patch.dateFrom !== undefined) query.dateFrom = patch.dateFrom
    if (patch.dateTo !== undefined) query.dateTo = patch.dateTo
    if (patch.timezone !== undefined) query.timezone = patch.timezone
    if (patch.channel !== undefined) query.channel = patch.channel
    if (patch.resourceExternalId !== undefined) query.resourceExternalId = patch.resourceExternalId
    if (patch.clientTags !== undefined) query.clientTags = patch.clientTags
    if (patch.limit !== undefined) query.limit = patch.limit
    query.offset = 0
  }

  const toCsvRows = (rows: AnalyticsCommodityTableItem[]) => {
    const headers = [
      'Товар',
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
        item.commodity_name,
        item.commodity_category || '—',
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
    downloadCsv(toCsvRows(items.value), `commodities-table-page-${currentPage.value}.csv`)
  }

  const exportAllCsv = async () => {
    if (!agentId.value) return
    try {
      const allRows: AnalyticsCommodityTableItem[] = []
      const batchLimit = 200
      let offset = 0
      let total = 0

      do {
        const response = await analyticsApi.getCommoditiesTable(agentId.value, {
          ...query,
          limit: batchLimit,
          offset,
        })
        total = response.total
        allRows.push(...response.items)
        offset += batchLimit
      } while (offset < total)

      downloadCsv(toCsvRows(allRows), 'commodities-table-all.csv')
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
