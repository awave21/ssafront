import { ref, readonly } from 'vue'
import { useApiFetch } from './useApiFetch'
import type { Credential, CredentialCreate, CredentialUpdate, CredentialTestResult } from '~/types/credential'

export const useCredentials = () => {
  const apiFetch = useApiFetch()
  const credentials = ref<Credential[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const fetchCredentials = async () => {
    try {
      isLoading.value = true
      error.value = null
      const response = await apiFetch<Credential[]>('/credentials')
      credentials.value = response
      return response
    } catch (err: any) {
      error.value = err.message || 'Ошибка загрузки учётных данных'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const getCredential = async (id: string) => {
    try {
      isLoading.value = true
      error.value = null
      return await apiFetch<Credential>(`/credentials/${id}`)
    } catch (err: any) {
      error.value = err.message || 'Ошибка загрузки учётных данных'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const createCredential = async (data: CredentialCreate) => {
    try {
      isLoading.value = true
      error.value = null
      const response = await apiFetch<Credential>('/credentials', {
        method: 'POST',
        body: data,
      })
      credentials.value.unshift(response)
      return response
    } catch (err: any) {
      error.value = err.message || 'Ошибка создания учётных данных'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const updateCredential = async (id: string, data: CredentialUpdate) => {
    try {
      isLoading.value = true
      error.value = null
      const response = await apiFetch<Credential>(`/credentials/${id}`, {
        method: 'PUT',
        body: data,
      })
      const index = credentials.value.findIndex((c) => c.id === id)
      if (index !== -1) credentials.value.splice(index, 1, response)
      return response
    } catch (err: any) {
      error.value = err.message || 'Ошибка обновления учётных данных'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const deleteCredential = async (id: string) => {
    try {
      isLoading.value = true
      error.value = null
      await apiFetch(`/credentials/${id}`, { method: 'DELETE' })
      credentials.value = credentials.value.filter((c) => c.id !== id)
    } catch (err: any) {
      error.value = err.message || 'Ошибка удаления учётных данных'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const testCredential = async (id: string) => {
    try {
      error.value = null
      return await apiFetch<CredentialTestResult>(`/credentials/${id}/test`, {
        method: 'POST',
      })
    } catch (err: any) {
      error.value = err.message || 'Ошибка тестирования'
      throw err
    }
  }

  return {
    credentials: readonly(credentials),
    isLoading: readonly(isLoading),
    error: readonly(error),
    fetchCredentials,
    getCredential,
    createCredential,
    updateCredential,
    deleteCredential,
    testCredential,
  }
}
