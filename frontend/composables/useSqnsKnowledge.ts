import { ref } from 'vue'
import {
  useAgents,
  type SqnsService,
  type SqnsSpecialist,
  type SqnsServiceEmployeeLink,
} from '~/composables/useAgents'
import { getReadableErrorMessage } from '~/utils/api-errors'

/**
 * Загрузка услуг / сотрудников / связей SQNS для экрана сценариев (скриптов).
 * Обёртка над методами useAgents с локальным состоянием списков.
 */
export const useSqnsKnowledge = (agentId: string) => {
  const {
    fetchSqnsServicesCached,
    fetchSqnsSpecialists,
    fetchSqnsServiceEmployeeLinks,
    updateSqnsSpecialist,
  } = useAgents()

  const services = ref<SqnsService[]>([])
  const specialists = ref<SqnsSpecialist[]>([])
  const serviceEmployeeLinks = ref<SqnsServiceEmployeeLink[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const normalizeSpecialist = (s: SqnsSpecialist): SqnsSpecialist => ({
    ...s,
    active: Boolean(s.active ?? s.is_active ?? false),
  })

  const loadAll = async () => {
    isLoading.value = true
    error.value = null
    try {
      const [cached, specList, linksRes] = await Promise.all([
        fetchSqnsServicesCached(agentId, { limit: 5000, offset: 0 }),
        fetchSqnsSpecialists(agentId, { limit: 5000, offset: 0 }),
        fetchSqnsServiceEmployeeLinks(agentId, { limit: 8000, offset: 0 }),
      ])
      services.value = cached.services ?? []
      specialists.value = (specList ?? []).map(normalizeSpecialist)
      serviceEmployeeLinks.value = linksRes.items ?? []
    } catch (err: unknown) {
      error.value = getReadableErrorMessage(err as { statusCode?: number }, 'Не удалось загрузить данные SQNS')
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const updateSpecialistInfo = async (specialistId: string, information: string) => {
    await updateSqnsSpecialist(agentId, specialistId, { information: information || null })
    const row = specialists.value.find((x) => x.id === specialistId)
    if (row) row.information = information ? information : null
  }

  return {
    services,
    specialists,
    serviceEmployeeLinks,
    isLoading,
    error,
    loadAll,
    updateSpecialistInfo,
  }
}
