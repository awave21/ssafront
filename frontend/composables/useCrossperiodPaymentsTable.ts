import { computed, ref, watch } from 'vue'
import { useAnalyticsApi } from '~/composables/analyticsApi'
import type {
  AnalyticsCrossperiodPaymentsResponse,
  AnalyticsCrossperiodPaymentsTotals,
  AnalyticsFilters,
  CrossperiodPaymentsSortBy,
} from '~/types/analytics'

export const useCrossperiodPaymentsTable = (
  filters: AnalyticsFilters,
  enabled: { value: boolean },
) => {
  const api = useAnalyticsApi()

  const data = ref<AnalyticsCrossperiodPaymentsResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const sortBy = ref<CrossperiodPaymentsSortBy>('amount')
  const sortOrder = ref<'asc' | 'desc'>('desc')
  const currentPage = ref(0)
  const pageSize = 50

  // Direction filter: '' | 'past' | 'future' | 'unknown'
  const directionFilter = ref<'' | 'past' | 'future' | 'unknown'>('')

  const query = computed(() => ({
    dateFrom: filters.dateFrom,
    dateTo: filters.dateTo,
    timezone: filters.timezone,
    channel: filters.channel,
    revenueBasis: filters.revenueBasis,
    paymentMethods: filters.paymentMethods,
    revenueCategories: filters.revenueCategories,
    resourceExternalId: filters.resourceExternalId,
    clientTags: filters.clientTags,
    sortBy: sortBy.value,
    sortOrder: sortOrder.value,
    limit: pageSize,
    offset: currentPage.value * pageSize,
  }))

  const load = async () => {
    if (!filters.agentId || !enabled.value) return
    loading.value = true
    error.value = null
    try {
      data.value = await api.getCrossperiodPaymentsTable(filters.agentId, query.value)
    } catch (e: any) {
      error.value = e?.message || 'Ошибка загрузки'
    } finally {
      loading.value = false
    }
  }

  const setSort = (col: CrossperiodPaymentsSortBy) => {
    if (sortBy.value === col) {
      sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
    } else {
      sortBy.value = col
      sortOrder.value = 'desc'
    }
    currentPage.value = 0
    load()
  }

  const setPage = (page: number) => {
    currentPage.value = page
    load()
  }

  const totals = computed((): AnalyticsCrossperiodPaymentsTotals | null => data.value?.totals ?? null)

  const items = computed(() => {
    const raw = data.value?.items ?? []
    if (!directionFilter.value) return raw
    return raw.filter((i) => i.direction === directionFilter.value)
  })

  const totalPages = computed(() =>
    data.value ? Math.ceil(data.value.total / pageSize) : 0,
  )

  watch(
    () => [filters.agentId, filters.dateFrom, filters.dateTo, filters.timezone, filters.channel, filters.revenueBasis, filters.resourceExternalId],
    () => {
      currentPage.value = 0
      if (enabled.value) load()
    },
  )

  watch(
    () => enabled.value,
    (v) => { if (v && !data.value) load() },
  )

  return {
    data,
    loading,
    error,
    items,
    totals,
    sortBy,
    sortOrder,
    currentPage,
    totalPages,
    directionFilter,
    setSort,
    setPage,
    load,
  }
}
