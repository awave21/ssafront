import { computed, ref, watch } from 'vue'
import { useAnalyticsApi } from '~/composables/analyticsApi'
import type {
  AiRecommendationsResponse,
  AnalyticsFilters,
  BotHealthResponse,
  FunnelResponse,
  InsightsResponse,
  ManagersOverviewResponse,
  ManagersTimelineResponse,
  StaffOverviewResponse,
} from '~/types/analytics'

export const useAnalyticsV2Data = (filters: AnalyticsFilters) => {
  const api = useAnalyticsApi()

  const staff = ref<StaffOverviewResponse | null>(null)
  const managers = ref<ManagersOverviewResponse | null>(null)
  const managersTimeline = ref<ManagersTimelineResponse | null>(null)
  const botHealth = ref<BotHealthResponse | null>(null)
  const funnel = ref<FunnelResponse | null>(null)
  const insights = ref<InsightsResponse | null>(null)
  const aiReco = ref<AiRecommendationsResponse | null>(null)
  const aiRecoLoading = ref(false)

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
    const agentId = filters.agentId
    const q = v2Query.value
    try {
      const [s, m, mt, b, f, i] = await Promise.allSettled([
        api.getStaffOverview(agentId, q),
        api.getManagersOverview(agentId, q),
        api.getManagersTimeline(agentId, q),
        api.getBotHealth(agentId, q),
        api.getFunnel(agentId, q),
        api.getInsights(agentId, q),
      ])
      if (s.status === 'fulfilled') staff.value = s.value
      if (m.status === 'fulfilled') managers.value = m.value
      if (mt.status === 'fulfilled') managersTimeline.value = mt.value
      if (b.status === 'fulfilled') botHealth.value = b.value
      if (f.status === 'fulfilled') funnel.value = f.value
      if (i.status === 'fulfilled') insights.value = i.value
    } catch (e: any) {
      error.value = e?.message || 'Не удалось загрузить аналитику'
    } finally {
      pending.value = false
    }
  }

  const fetchAiReco = async (force = false) => {
    if (!filters.agentId) return
    aiRecoLoading.value = true
    try {
      aiReco.value = await api.getAiRecommendations(filters.agentId, v2Query.value, force)
    } catch (e: any) {
      // не обнуляем существующий
    } finally {
      aiRecoLoading.value = false
    }
  }

  watch(
    () => [filters.agentId, filters.dateFrom, filters.dateTo, filters.timezone] as const,
    () => {
      void fetchAll()
    },
  )

  return {
    staff,
    managers,
    managersTimeline,
    botHealth,
    funnel,
    insights,
    aiReco,
    aiRecoLoading,
    pending,
    error,
    fetchAll,
    fetchAiReco,
  }
}
