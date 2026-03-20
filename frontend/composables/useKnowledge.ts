import { ref, computed } from 'vue'
import { useApiFetch } from './useApiFetch'
import { useAuth } from './useAuth'
import type {
  DirectQuestion,
  CreateDirectQuestionPayload,
  UpdateDirectQuestionPayload,
  DirectQuestionsImportOptions,
  DirectQuestionsImportResult
} from '~/types/knowledge'
import { getReadableErrorMessage } from '~/utils/api-errors'

export const useKnowledge = (agentId: string) => {
  const apiFetch = useApiFetch()
  const { token } = useAuth()

  const directQuestions = ref<DirectQuestion[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const sortDirectQuestions = (items: DirectQuestion[]) => {
    const hasOrderIndex = items.some((item) => typeof item.order_index === 'number')
    if (!hasOrderIndex) return items
    return [...items].sort((left, right) => (left.order_index ?? Number.MAX_SAFE_INTEGER) - (right.order_index ?? Number.MAX_SAFE_INTEGER))
  }

  const fetchDirectQuestions = async () => {
    isLoading.value = true
    error.value = null
    try {
      const data = await apiFetch<DirectQuestion[]>(`/agents/${agentId}/knowledge/direct-questions`, {
        headers: { Authorization: `Bearer ${token.value}` }
      })
      directQuestions.value = sortDirectQuestions(data || [])
    } catch (err: any) {
      error.value = getReadableErrorMessage(err, 'Не удалось загрузить прямые вопросы')
      console.error('Failed to fetch direct questions:', err)
    } finally {
      isLoading.value = false
    }
  }

  const createDirectQuestion = async (payload: CreateDirectQuestionPayload): Promise<DirectQuestion | null> => {
    try {
      const created = await apiFetch<DirectQuestion>(`/agents/${agentId}/knowledge/direct-questions`, {
        method: 'POST',
        headers: { 
          Authorization: `Bearer ${token.value}`,
          'Content-Type': 'application/json'
        },
        body: payload
      })
      directQuestions.value.push(created)
      directQuestions.value = sortDirectQuestions(directQuestions.value)
      return created
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось создать прямой вопрос'))
    }
  }

  const updateDirectQuestion = async (id: string, payload: UpdateDirectQuestionPayload): Promise<DirectQuestion | null> => {
    try {
      const updated = await apiFetch<DirectQuestion>(`/agents/${agentId}/knowledge/direct-questions/${id}`, {
        method: 'PUT',
        headers: { 
          Authorization: `Bearer ${token.value}`,
          'Content-Type': 'application/json'
        },
        body: payload
      })
      const index = directQuestions.value.findIndex(q => q.id === id)
      if (index !== -1) {
        directQuestions.value[index] = updated
      }
      directQuestions.value = sortDirectQuestions(directQuestions.value)
      return updated
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось обновить прямой вопрос'))
    }
  }

  const deleteDirectQuestion = async (id: string): Promise<void> => {
    try {
      await apiFetch(`/agents/${agentId}/knowledge/direct-questions/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token.value}` }
      })
      directQuestions.value = directQuestions.value.filter(q => q.id !== id)
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось удалить прямой вопрос'))
    }
  }

  const toggleDirectQuestion = async (id: string, enabled: boolean): Promise<void> => {
    try {
      await apiFetch(`/agents/${agentId}/knowledge/direct-questions/${id}/toggle`, {
        method: 'PATCH',
        headers: { 
          Authorization: `Bearer ${token.value}`,
          'Content-Type': 'application/json'
        },
        body: { is_enabled: enabled }
      })
      const index = directQuestions.value.findIndex(q => q.id === id)
      if (index !== -1) {
        directQuestions.value[index].is_enabled = enabled
      }
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось изменить статус вопроса'))
    }
  }

  const reorderDirectQuestions = async (ids: string[]): Promise<void> => {
    const previous = [...directQuestions.value]
    const mapById = new Map(previous.map((question) => [question.id, question]))

    const reordered = ids
      .map((id, index) => {
        const question = mapById.get(id)
        if (!question) return null
        return { ...question, order_index: index + 1 }
      })
      .filter(Boolean) as DirectQuestion[]

    const untouched = previous.filter((question) => !ids.includes(question.id))
    directQuestions.value = [...reordered, ...untouched]

    const endpoint = `/agents/${agentId}/knowledge/direct-questions/reorder`
    const attempts: Array<{ method: 'PATCH' | 'POST' | 'PUT'; body: Record<string, unknown> }> = [
      { method: 'PATCH', body: { ids } },
      { method: 'POST', body: { ids } },
      {
        method: 'PATCH',
        body: {
          order: ids.map((id, index) => ({
            id,
            order_index: index + 1
          }))
        }
      },
      {
        method: 'PUT',
        body: {
          order: ids.map((id, index) => ({
            id,
            order_index: index + 1
          }))
        }
      }
    ]

    let lastError: unknown = null
    for (const attempt of attempts) {
      try {
        await apiFetch(endpoint, {
          method: attempt.method,
          headers: {
            Authorization: `Bearer ${token.value}`,
            'Content-Type': 'application/json'
          },
          body: attempt.body
        })
        lastError = null
        break
      } catch (err) {
        lastError = err
      }
    }

    if (!lastError) return

    try {
      await Promise.all(
        ids.map((id, index) =>
          apiFetch(`/agents/${agentId}/knowledge/direct-questions/${id}`, {
            method: 'PUT',
            headers: {
              Authorization: `Bearer ${token.value}`,
              'Content-Type': 'application/json'
            },
            body: { order_index: index + 1 }
          })
        )
      )
      return
    } catch (fallbackErr) {
      directQuestions.value = previous
      throw new Error(getReadableErrorMessage(fallbackErr, getReadableErrorMessage(lastError, 'Не удалось сохранить порядок прямых вопросов')))
    }
  }

  const translateSearchTitle = async (text: string): Promise<string> => {
    const sourceText = text.trim()
    if (!sourceText) return ''

    try {
      const response = await apiFetch<{ translated_text: string }>(
        `/agents/${agentId}/knowledge/direct-questions/translate-search-title`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token.value}`,
            'Content-Type': 'application/json'
          },
          body: {
            text: sourceText,
            target_language_code: 'en'
          }
        }
      )
      return String(response?.translated_text || '').trim()
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось сгенерировать search_title'))
    }
  }

  const importDirectQuestions = async (
    file: File,
    options: DirectQuestionsImportOptions = {}
  ): Promise<DirectQuestionsImportResult> => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('has_header', String(options.hasHeader ?? true))
    formData.append('replace_all', String(options.replaceAll ?? false))
    formData.append('strict', String(options.strict ?? false))
    if (options.sheetName) formData.append('sheet_name', options.sheetName)

    try {
      return await apiFetch<DirectQuestionsImportResult>(
        `/agents/${agentId}/knowledge/direct-questions/import`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token.value}`
          },
          body: formData
        }
      )
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось импортировать прямые вопросы'))
    }
  }

  return {
    directQuestions,
    isLoading,
    error,
    fetchDirectQuestions,
    createDirectQuestion,
    updateDirectQuestion,
    deleteDirectQuestion,
    toggleDirectQuestion,
    reorderDirectQuestions,
    translateSearchTitle,
    importDirectQuestions
  }
}
