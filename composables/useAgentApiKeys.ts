import { ref, readonly } from 'vue'
import { useApiFetch } from './useApiFetch'
import { useToast } from './useToast'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type { ApiKey, ApiKeyCreated, CreateApiKeyPayload, UpdateApiKeyPayload } from '~/types/apiKey'

export const useAgentApiKeys = () => {
  const apiFetch = useApiFetch()
  const { success: toastSuccess, error: toastError } = useToast()

  const keys = ref<ApiKey[]>([])
  const isLoading = ref(false)

  const fetchKeys = async (agentId: string, includeRevoked = false) => {
    try {
      isLoading.value = true
      const response = await apiFetch<ApiKey[]>('/api-keys', {
        query: {
          agent_id: agentId,
          ...(includeRevoked && { include_revoked: true })
        }
      })
      keys.value = response
    } catch (err: any) {
      toastError('Ошибка загрузки', getReadableErrorMessage(err, 'Не удалось загрузить API-ключи'))
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const createKey = async (payload: CreateApiKeyPayload): Promise<ApiKeyCreated> => {
    try {
      const response = await apiFetch<ApiKeyCreated>('/api-keys', {
        method: 'POST',
        body: payload
      })
      keys.value.unshift(response)
      toastSuccess('Ключ создан', `API-ключ «${response.name}» успешно создан`)
      return response
    } catch (err: any) {
      toastError('Ошибка создания', getReadableErrorMessage(err, 'Не удалось создать API-ключ'))
      throw err
    }
  }

  const updateKey = async (keyId: string, payload: UpdateApiKeyPayload): Promise<ApiKey> => {
    try {
      const response = await apiFetch<ApiKey>(`/api-keys/${keyId}`, {
        method: 'PATCH',
        body: payload
      })
      const idx = keys.value.findIndex(k => k.id === keyId)
      if (idx !== -1) keys.value[idx] = response
      toastSuccess('Ключ обновлён', 'Настройки API-ключа сохранены')
      return response
    } catch (err: any) {
      toastError('Ошибка обновления', getReadableErrorMessage(err, 'Не удалось обновить API-ключ'))
      throw err
    }
  }

  const revokeKey = async (keyId: string) => {
    try {
      await apiFetch(`/api-keys/${keyId}`, { method: 'DELETE' })
      const idx = keys.value.findIndex(k => k.id === keyId)
      if (idx !== -1) {
        keys.value[idx] = { ...keys.value[idx], revoked_at: new Date().toISOString() }
      }
      toastSuccess('Ключ отозван', 'API-ключ отозван и больше не работает')
    } catch (err: any) {
      toastError('Ошибка отзыва', getReadableErrorMessage(err, 'Не удалось отозвать API-ключ'))
      throw err
    }
  }

  return {
    keys: readonly(keys),
    isLoading: readonly(isLoading),
    fetchKeys,
    createKey,
    updateKey,
    revokeKey
  }
}
