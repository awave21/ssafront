import { ref } from 'vue'
import { useApiFetch } from './useApiFetch'
import { useAuth } from './useAuth'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type {
  AgentKgEntity,
  AgentKgEntityCreatePayload,
  AgentKgEntityType,
  AgentKgEntityUpdatePayload,
} from '~/types/kgEntities'

export const useAgentKgEntities = (agentId: string) => {
  const apiFetch = useApiFetch()
  const { token } = useAuth()

  const entities = ref<AgentKgEntity[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const authHeaders = () => ({ Authorization: `Bearer ${token.value}` })

  const fetchEntities = async (type?: AgentKgEntityType) => {
    isLoading.value = true
    error.value = null
    try {
      const qs = type ? `?type=${encodeURIComponent(type)}` : ''
      entities.value = await apiFetch<AgentKgEntity[]>(
        `/agents/${agentId}/kg-entities${qs}`,
        { headers: authHeaders() },
      ) || []
    } catch (err: unknown) {
      error.value = getReadableErrorMessage(err, 'Не удалось загрузить сущности')
    } finally {
      isLoading.value = false
    }
  }

  const createEntity = async (payload: AgentKgEntityCreatePayload): Promise<AgentKgEntity> => {
    return await apiFetch<AgentKgEntity>(`/agents/${agentId}/kg-entities`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: payload,
    })
  }

  const updateEntity = async (
    entityId: string,
    payload: AgentKgEntityUpdatePayload,
  ): Promise<AgentKgEntity> => {
    return await apiFetch<AgentKgEntity>(`/agents/${agentId}/kg-entities/${entityId}`, {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: payload,
    })
  }

  const deleteEntity = async (entityId: string): Promise<void> => {
    await apiFetch(`/agents/${agentId}/kg-entities/${entityId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
  }

  return {
    entities,
    isLoading,
    error,
    fetchEntities,
    createEntity,
    updateEntity,
    deleteEntity,
  }
}
