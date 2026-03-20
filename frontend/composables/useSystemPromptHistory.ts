import { ref, readonly } from 'vue'
import { useApiFetch } from './useApiFetch'
import type {
  SystemPromptVersionListItem,
  SystemPromptVersionListResponse,
  SystemPromptVersionRead,
} from '../types/systemPromptHistory'

export const useSystemPromptHistory = (agentId: () => string | undefined) => {
  const apiFetch = useApiFetch()

  const versions = ref<SystemPromptVersionListItem[]>([])
  const nextCursor = ref<number | null>(null)
  const isLoading = ref(false)
  const isLoadingMore = ref(false)
  const isActivating = ref(false)
  const error = ref<string | null>(null)

  /** Загрузить первую порцию (сброс списка) */
  const fetchHistory = async () => {
    const id = agentId()
    if (!id) return

    try {
      isLoading.value = true
      error.value = null

      const data = await apiFetch<SystemPromptVersionListResponse>(
        `/agents/${id}/system-prompt/history`,
        { query: { limit: 30 } }
      )

      versions.value = data.items
      nextCursor.value = data.next_cursor
    } catch (err: any) {
      // 404 — у агента нет истории (legacy)
      if (err?.statusCode === 404 || err?.status === 404) {
        versions.value = []
        nextCursor.value = null
        return
      }
      error.value = err.message || 'Не удалось загрузить историю промпта'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /** Подгрузить следующую порцию */
  const fetchMore = async () => {
    const id = agentId()
    if (!id || nextCursor.value === null) return

    try {
      isLoadingMore.value = true

      const data = await apiFetch<SystemPromptVersionListResponse>(
        `/agents/${id}/system-prompt/history`,
        { query: { limit: 30, cursor: nextCursor.value } }
      )

      versions.value.push(...data.items)
      nextCursor.value = data.next_cursor
    } catch (err: any) {
      error.value = err.message || 'Не удалось загрузить ещё'
      throw err
    } finally {
      isLoadingMore.value = false
    }
  }

  /** Получить полный текст конкретной версии */
  const fetchVersionDetail = async (versionId: string) => {
    const id = agentId()
    if (!id) return null

    const data = await apiFetch<SystemPromptVersionRead>(
      `/agents/${id}/system-prompt/history/${versionId}`
    )
    return data
  }

  /** Активировать (откатиться на) выбранную версию */
  const activateVersion = async (versionId: string) => {
    const id = agentId()
    if (!id) return null

    try {
      isActivating.value = true

      const data = await apiFetch<SystemPromptVersionRead>(
        `/agents/${id}/system-prompt/history/${versionId}/activate`,
        { method: 'POST' }
      )

      // Обновляем is_active в локальном списке
      for (const v of versions.value) {
        v.is_active = v.id === versionId
      }

      return data
    } finally {
      isActivating.value = false
    }
  }

  return {
    versions: readonly(versions),
    nextCursor: readonly(nextCursor),
    isLoading: readonly(isLoading),
    isLoadingMore: readonly(isLoadingMore),
    isActivating: readonly(isActivating),
    error: readonly(error),
    fetchHistory,
    fetchMore,
    fetchVersionDetail,
    activateVersion,
  }
}
