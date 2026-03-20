import { useApiFetch } from './useApiFetch'

export type ApiKey = {
  id: string
  name?: string
  key: string
  scopes: string[]
  created_at: string
  revoked_at?: string
  expires_at?: string
}

export type CreateApiKeyData = {
  scopes: string[]
  name?: string
  expires_in_days?: number
}

export const useApiKeys = () => {
  const { token } = useAuth()
  const apiFetch = useApiFetch()
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const apiKeys = ref<ApiKey[]>([])

  // Получение списка API-ключей
  const fetchApiKeys = async (params?: { include_revoked?: boolean }) => {
    try {
      isLoading.value = true
      error.value = null

      const queryParams = new URLSearchParams()
      if (params?.include_revoked) queryParams.append('include_revoked', 'true')

      const response = await apiFetch<ApiKey[]>('/api-keys', {
        query: Object.fromEntries(queryParams)
      })

      apiKeys.value = response
      return response
    } catch (err: any) {
      error.value = err.message || 'Ошибка загрузки API-ключей'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  // Создание нового API-ключа
  const createApiKey = async (keyData: CreateApiKeyData) => {
    try {
      isLoading.value = true
      error.value = null

      const response = await apiFetch<ApiKey>('/api-keys', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: keyData
      })

      // Добавить новый ключ в список
      apiKeys.value.unshift(response)

      return response
    } catch (err: any) {
      error.value = err.message || 'Ошибка создания API-ключа'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  // Удаление API-ключа
  const revokeApiKey = async (keyId: string) => {
    try {
      isLoading.value = true
      error.value = null

      await apiFetch(`/api-keys/${keyId}`, {
        method: 'DELETE'
      })

      // Удалить ключ из списка
      apiKeys.value = apiKeys.value.filter(key => key.id !== keyId)

    } catch (err: any) {
      error.value = err.message || 'Ошибка удаления API-ключа'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  return {
    apiKeys: readonly(apiKeys),
    isLoading: readonly(isLoading),
    error: readonly(error),
    fetchApiKeys,
    createApiKey,
    revokeApiKey
  }
}