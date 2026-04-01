import { computed, reactive, ref, watch, type Ref } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { usePatientsApi } from '~/composables/usePatientsApi'
import type { PatientsQuery, PatientsSortBy, SqnsClientListItem } from '~/types/patient-directory'

const DEFAULT_LIMIT = 50

const parseAggregateNumber = (raw: unknown): number | null => {
  if (raw === undefined || raw === null) return null
  if (typeof raw === 'number') return Number.isFinite(raw) ? raw : null
  if (typeof raw === 'string') {
    const n = parseFloat(raw.trim().replace(/\s/g, '').replace(',', '.'))
    return Number.isFinite(n) ? n : null
  }
  const n = parseFloat(String(raw).replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

export const usePatients = (
  agentId: Readonly<Ref<string | null>>,
  /**
   * Начальные значения фильтров из URL — должны быть прочитаны **до** вызова usePatients
   * в контексте компонента, чтобы первый fetch сразу шёл с правильными параметрами.
   */
  initialRouteQuery: Partial<
    Pick<
      PatientsQuery,
      | 'visit_date_from'
      | 'visit_date_to'
      | 'visit_cohort'
      | 'timezone'
      | 'channel'
      | 'tags'
      | 'revenue_basis'
      | 'paymentMethods'
      | 'revenueCategories'
      | 'resource_external_id'
    >
  > = {},
) => {
  const { getClients } = usePatientsApi()

  const query = reactive<PatientsQuery>({
    search: '',
    client_type: '',
    sort_by: 'visits_count',
    sort_order: 'desc',
    limit: DEFAULT_LIMIT,
    offset: 0,
    visit_date_from: initialRouteQuery.visit_date_from ?? '',
    visit_date_to: initialRouteQuery.visit_date_to ?? '',
    visit_cohort: initialRouteQuery.visit_cohort ?? '',
    timezone: initialRouteQuery.timezone ?? '',
    channel: initialRouteQuery.channel ?? '',
    tags: initialRouteQuery.tags ?? '',
    revenue_basis: initialRouteQuery.revenue_basis ?? 'clinical',
    paymentMethods: initialRouteQuery.paymentMethods ?? [],
    revenueCategories: initialRouteQuery.revenueCategories ?? [],
    resource_external_id: initialRouteQuery.resource_external_id ?? null,
  })

  const debouncedSearch = ref(query.search)

  const items = ref<SqnsClientListItem[]>([])
  const total = ref(0)
  const hasMore = ref(false)
  const revenueTotal = ref<number | null>(null)
  const totalArrivalSum = ref<number | null>(null)
  const visitsCountSum = ref<number | null>(null)
  const lastVisitTotalPriceSum = ref<number | null>(null)
  const sliceVisitCount = ref<number | null>(null)
  const topServiceName = ref<string | null>(null)
  const topServiceBookings = ref<number | null>(null)
  const pending = ref(false)
  const error = ref<unknown>(null)

  const resetLocal = () => {
    items.value = []
    total.value = 0
    hasMore.value = false
    revenueTotal.value = null
    totalArrivalSum.value = null
    visitsCountSum.value = null
    lastVisitTotalPriceSum.value = null
    sliceVisitCount.value = null
    topServiceName.value = null
    topServiceBookings.value = null
    error.value = null
  }

  const refresh = async () => {
    if (!agentId.value) {
      resetLocal()
      pending.value = false
      return
    }
    pending.value = true
    error.value = null
    try {
      const res = await getClients(agentId.value, {
        ...query,
        search: debouncedSearch.value,
      })
      items.value = res.clients
      total.value = res.total
      hasMore.value = res.has_more
      revenueTotal.value = parseAggregateNumber(res.revenue_total ?? res.revenueTotal)
      totalArrivalSum.value = parseAggregateNumber(res.total_arrival_sum ?? res.totalArrivalSum)
      lastVisitTotalPriceSum.value = parseAggregateNumber(
        res.last_visit_total_price_sum ?? res.lastVisitTotalPriceSum,
      )
      const vcs = res.visits_count_sum ?? res.visitsCountSum
      if (vcs === undefined || vcs === null) {
        visitsCountSum.value = null
      } else if (typeof vcs === 'number' && Number.isFinite(vcs)) {
        visitsCountSum.value = Math.trunc(vcs)
      } else {
        const n = Number(vcs)
        visitsCountSum.value = Number.isFinite(n) ? Math.trunc(n) : null
      }
      const svc = res.slice_visit_count ?? res.sliceVisitCount
      if (svc === undefined || svc === null) {
        sliceVisitCount.value = null
      } else if (typeof svc === 'number' && Number.isFinite(svc)) {
        sliceVisitCount.value = Math.trunc(svc)
      } else {
        const n = Number(svc)
        sliceVisitCount.value = Number.isFinite(n) ? Math.trunc(n) : null
      }
      const ts = res.top_service_name
      topServiceName.value = typeof ts === 'string' && ts.trim() ? ts.trim() : null
      const tb = res.top_service_bookings
      if (tb === undefined || tb === null) {
        topServiceBookings.value = null
      } else if (typeof tb === 'number' && Number.isFinite(tb)) {
        topServiceBookings.value = tb
      } else {
        const n = Number(tb)
        topServiceBookings.value = Number.isFinite(n) ? n : null
      }
    } catch (e) {
      error.value = e
      resetLocal()
    } finally {
      pending.value = false
    }
  }

  watchDebounced(
    () => query.search,
    (v) => {
      debouncedSearch.value = v
      query.offset = 0
    },
    { debounce: 400 },
  )

  const fetchKey = computed(() =>
    JSON.stringify({
      id: agentId.value,
      sort_by: query.sort_by,
      sort_order: query.sort_order,
      limit: query.limit,
      offset: query.offset,
      client_type: query.client_type,
      search: debouncedSearch.value,
      visit_date_from: query.visit_date_from,
      visit_date_to: query.visit_date_to,
      visit_cohort: query.visit_cohort,
      timezone: query.timezone,
      channel: query.channel,
      tags: query.tags,
      revenue_basis: query.revenue_basis,
      paymentMethods: query.paymentMethods,
      revenueCategories: query.revenueCategories,
      resource_external_id: query.resource_external_id,
    }),
  )

  watch(
    fetchKey,
    () => {
      if (!agentId.value) {
        resetLocal()
        return
      }
      void refresh()
    },
    { immediate: true },
  )

  watch(agentId, (id) => {
    query.offset = 0
    debouncedSearch.value = query.search
    if (!id) resetLocal()
  })

  const currentPage = computed(() => Math.floor(query.offset / query.limit) + 1)
  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / query.limit)))

  const setSearch = (value: string) => {
    query.search = value
  }

  const setPage = (page: number) => {
    const p = Math.max(1, Math.min(totalPages.value, page))
    query.offset = (p - 1) * query.limit
  }

  const setSort = (by: PatientsSortBy) => {
    if (query.sort_by === by) {
      query.sort_order = query.sort_order === 'asc' ? 'desc' : 'asc'
    } else {
      query.sort_by = by
      query.sort_order = 'desc'
    }
    query.offset = 0
  }

  const initialize = () => {
    query.offset = 0
    void refresh()
  }

  return {
    query,
    items,
    total,
    hasMore,
    revenueTotal,
    totalArrivalSum,
    visitsCountSum,
    lastVisitTotalPriceSum,
    sliceVisitCount,
    topServiceName,
    topServiceBookings,
    pending,
    error,
    currentPage,
    totalPages,
    refresh,
    setSearch,
    setPage,
    setSort,
    initialize,
  }
}
