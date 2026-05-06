import { computed, ref, watch } from 'vue'
import { useAnalyticsApi } from '~/composables/analyticsApi'
import type { AnalyticsFilters, MotivationOverviewResponse, MotivationRule } from '~/types/analytics'

export const useMotivationData = (filters: AnalyticsFilters) => {
  const api = useAnalyticsApi()

  const overview = ref<MotivationOverviewResponse | null>(null)
  const pending = ref(false)
  const error = ref<string | null>(null)

  const v2Query = computed(() => ({
    dateFrom: filters.dateFrom,
    dateTo: filters.dateTo,
    timezone: filters.timezone,
  }))

  const fetchAll = async () => {
    if (!filters.agentId) return
    pending.value = true
    error.value = null
    try {
      overview.value = await api.getMotivationOverview(filters.agentId, v2Query.value)
    } catch (e: any) {
      error.value = e?.message || 'Не удалось загрузить данные мотивации'
    } finally {
      pending.value = false
    }
  }

  const saveRule = async (payload: Partial<MotivationRule>) => {
    if (!filters.agentId) return
    const updated = await api.updateMotivationRule(filters.agentId, payload)
    // обновляем правило в уже загруженном overview без перезагрузки всей таблицы
    if (overview.value) {
      overview.value = { ...overview.value, rule: updated }
    }
    // пересчёт бонусов требует перезагрузки с сервера — т.к. пересчёт на бэке
    await fetchAll()
    return updated
  }

  watch(
    () => [filters.agentId, filters.dateFrom, filters.dateTo, filters.timezone] as const,
    () => {
      void fetchAll()
    },
  )

  return {
    overview,
    pending,
    error,
    fetchAll,
    saveRule,
  }
}
