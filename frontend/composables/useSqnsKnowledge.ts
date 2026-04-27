import { ref } from 'vue'
import {
  useAgents,
  type SqnsService,
  type SqnsSpecialist,
  type SqnsServiceEmployeeLink,
} from '~/composables/useAgents'
import { getReadableErrorMessage } from '~/utils/api-errors'

/** Backend `Query(..., le=1000)` on `/sqns/services/cached` and `/sqns/specialists`. */
const SQNS_LIST_PAGE_MAX = 1000

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
    updateSqnsService,
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

  const fetchAllCachedServices = async (): Promise<SqnsService[]> => {
    const acc: SqnsService[] = []
    let offset = 0
    while (true) {
      const res = await fetchSqnsServicesCached(agentId, { limit: SQNS_LIST_PAGE_MAX, offset })
      const batch = res.services ?? []
      acc.push(...batch)
      if (batch.length < SQNS_LIST_PAGE_MAX) break
      offset += SQNS_LIST_PAGE_MAX
    }
    return acc
  }

  const fetchAllSpecialists = async (): Promise<SqnsSpecialist[]> => {
    const acc: SqnsSpecialist[] = []
    let offset = 0
    while (true) {
      const batch = await fetchSqnsSpecialists(agentId, { limit: SQNS_LIST_PAGE_MAX, offset }) ?? []
      acc.push(...batch)
      if (batch.length < SQNS_LIST_PAGE_MAX) break
      offset += SQNS_LIST_PAGE_MAX
    }
    return acc
  }

  const loadAll = async () => {
    isLoading.value = true
    error.value = null
    try {
      const [svcList, specList, linksRes] = await Promise.all([
        fetchAllCachedServices(),
        fetchAllSpecialists(),
        fetchSqnsServiceEmployeeLinks(agentId, { limit: 8000, offset: 0 }),
      ])
      services.value = svcList
      specialists.value = specList.map(normalizeSpecialist)
      serviceEmployeeLinks.value = linksRes.items ?? []
    } catch (err: unknown) {
      error.value = getReadableErrorMessage(err as { statusCode?: number }, 'Не удалось загрузить данные SQNS')
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const updateSpecialistInfo = async (specialistId: string, information: string) => {
    await updateSqnsSpecialist(agentId, specialistId, { information })
    const row = specialists.value.find((x) => x.id === specialistId)
    if (row) row.information = information.trim() ? information : null
  }

  const updateServiceDescription = async (serviceId: string, description: string) => {
    await updateSqnsService(agentId, serviceId, { description: description || null })
    const row = services.value.find((x) => x.id === serviceId)
    if (row) (row as { description?: string | null }).description = description ? description : null
  }

  return {
    services,
    specialists,
    serviceEmployeeLinks,
    isLoading,
    error,
    loadAll,
    updateSpecialistInfo,
    updateServiceDescription,
  }
}
