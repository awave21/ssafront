import { ref } from 'vue'
import { useAnalyticsApi } from '~/composables/analyticsApi'
import type { AnalyticsClientCardResponse } from '~/types/analytics'

export const useClientCard = (agentId: string) => {
  const api = useAnalyticsApi()

  const isOpen = ref(false)
  const currentClientId = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const data = ref<AnalyticsClientCardResponse | null>(null)

  const cache = new Map<string, AnalyticsClientCardResponse>()

  const open = async (clientExternalId: string) => {
    currentClientId.value = clientExternalId
    isOpen.value = true

    if (cache.has(clientExternalId)) {
      data.value = cache.get(clientExternalId)!
      return
    }

    loading.value = true
    error.value = null
    try {
      const result = await api.getClientCard(agentId, clientExternalId)
      cache.set(clientExternalId, result)
      data.value = result
    } catch (e: any) {
      error.value = e?.message || 'Ошибка загрузки карточки'
    } finally {
      loading.value = false
    }
  }

  const close = () => {
    isOpen.value = false
  }

  return {
    isOpen,
    currentClientId,
    loading,
    error,
    data,
    open,
    close,
  }
}
