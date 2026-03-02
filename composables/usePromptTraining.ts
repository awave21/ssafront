import { ref, readonly, computed } from 'vue'
import { useApiFetch } from './useApiFetch'
import { useToast } from './useToast'
import type {
  TrainingSessionRead,
  TrainingSessionsListResponse,
  TrainingFeedbackRead,
  GeneratedPromptPreview,
  GeneratePromptRequest,
  CreateSessionPayload,
  CreateFeedbackPayload,
} from '~/types/promptTraining'

export const usePromptTraining = (agentId: () => string | undefined) => {
  const apiFetch = useApiFetch()
  const { success: toastSuccess, error: toastError } = useToast()

  const sessions = ref<TrainingSessionRead[]>([])
  const nextCursor = ref<string | null>(null)
  const currentSession = ref<TrainingSessionRead | null>(null)
  const feedbacks = ref<TrainingFeedbackRead[]>([])
  const generatedPreview = ref<GeneratedPromptPreview | null>(null)

  const isLoading = ref(false)
  const isLoadingMore = ref(false)
  const isCreating = ref(false)
  const isLoadingSession = ref(false)
  const isSubmittingFeedback = ref(false)
  const isGenerating = ref(false)
  const isApplying = ref(false)

  const error = ref<string | null>(null)

  const basePath = () => {
    const id = agentId()
    if (!id) throw new Error('Agent ID is required')
    return `/agents/${id}/prompt-training`
  }

  const feedbackCount = computed(() =>
    currentSession.value?.feedback_count ?? feedbacks.value.length
  )

  const canGenerate = computed(() => feedbackCount.value >= 1 && !isGenerating.value)

  const fetchSessions = async () => {
    const id = agentId()
    if (!id) return

    try {
      isLoading.value = true
      error.value = null

      const data = await apiFetch<TrainingSessionsListResponse>(
        `${basePath()}/sessions`,
        { query: { limit: 30 } }
      )

      sessions.value = data.items
      nextCursor.value = data.next_cursor
    } catch (err: any) {
      if (err?.statusCode === 404 || err?.status === 404) {
        sessions.value = []
        nextCursor.value = null
        return
      }
      error.value = err.message || 'Не удалось загрузить сессии'
    } finally {
      isLoading.value = false
    }
  }

  const fetchMoreSessions = async () => {
    if (!agentId() || nextCursor.value === null) return

    try {
      isLoadingMore.value = true

      const data = await apiFetch<TrainingSessionsListResponse>(
        `${basePath()}/sessions`,
        { query: { limit: 30, cursor: nextCursor.value } }
      )

      sessions.value.push(...data.items)
      nextCursor.value = data.next_cursor
    } catch (err: any) {
      error.value = err.message || 'Не удалось загрузить ещё'
    } finally {
      isLoadingMore.value = false
    }
  }

  const createSession = async (payload: CreateSessionPayload) => {
    try {
      isCreating.value = true
      error.value = null

      const session = await apiFetch<TrainingSessionRead>(
        `${basePath()}/sessions`,
        { method: 'POST', body: payload }
      )

      sessions.value.unshift(session)
      currentSession.value = session
      feedbacks.value = [...(session.feedbacks ?? [])]

      return session
    } catch (err: any) {
      toastError('Ошибка', err.message || 'Не удалось создать сессию')
      return null
    } finally {
      isCreating.value = false
    }
  }

  const fetchSession = async (sessionId: string) => {
    try {
      isLoadingSession.value = true
      error.value = null

      const session = await apiFetch<TrainingSessionRead>(
        `${basePath()}/sessions/${sessionId}`
      )

      currentSession.value = session
      feedbacks.value = [...(session.feedbacks ?? [])]

      return session
    } catch (err: any) {
      error.value = err.message || 'Не удалось загрузить сессию'
      return null
    } finally {
      isLoadingSession.value = false
    }
  }

  const submitFeedback = async (sessionId: string, payload: CreateFeedbackPayload) => {
    try {
      isSubmittingFeedback.value = true

      const feedback = await apiFetch<TrainingFeedbackRead>(
        `${basePath()}/sessions/${sessionId}/feedback`,
        { method: 'POST', body: payload }
      )

      feedbacks.value.push(feedback)

      if (currentSession.value && currentSession.value.id === sessionId) {
        currentSession.value = {
          ...currentSession.value,
          feedback_count: currentSession.value.feedback_count + 1,
        }
      }

      return feedback
    } catch (err: any) {
      toastError('Ошибка', err.message || 'Не удалось отправить фидбек')
      return null
    } finally {
      isSubmittingFeedback.value = false
    }
  }

  const generatePrompt = async (sessionId: string, request?: GeneratePromptRequest) => {
    try {
      isGenerating.value = true
      error.value = null

      const body = request?.meta_model ? { meta_model: request.meta_model } : undefined
      const preview = await apiFetch<GeneratedPromptPreview>(
        `${basePath()}/sessions/${sessionId}/generate`,
        { method: 'POST', body }
      )

      generatedPreview.value = preview
      return preview
    } catch (err: any) {
      toastError('Ошибка генерации', err.message || 'Не удалось сгенерировать промпт')
      return null
    } finally {
      isGenerating.value = false
    }
  }

  const applyPrompt = async (sessionId: string, editedPrompt?: string) => {
    try {
      isApplying.value = true

      const body = editedPrompt ? { generated_prompt: editedPrompt } : undefined
      const session = await apiFetch<TrainingSessionRead>(
        `${basePath()}/sessions/${sessionId}/apply`,
        { method: 'POST', body }
      )

      currentSession.value = session
      generatedPreview.value = null

      const idx = sessions.value.findIndex(s => s.id === sessionId)
      if (idx !== -1) sessions.value[idx] = session

      return session
    } catch (err: any) {
      if (err?.statusCode === 409) {
        toastError('Сессия уже завершена', 'Обновите данные сессии')
        await fetchSession(sessionId)
      } else if (err?.statusCode === 422) {
        toastError('Ошибка', 'Сначала сгенерируйте промпт')
      } else {
        toastError('Ошибка применения', err.message || 'Не удалось применить промпт')
      }
      return null
    } finally {
      isApplying.value = false
    }
  }

  const clearGeneratedPreview = () => {
    generatedPreview.value = null
  }

  const clearCurrentSession = () => {
    currentSession.value = null
    feedbacks.value = []
    generatedPreview.value = null
  }

  return {
    sessions: readonly(sessions),
    nextCursor: readonly(nextCursor),
    currentSession: readonly(currentSession),
    feedbacks: readonly(feedbacks),
    generatedPreview: readonly(generatedPreview),

    isLoading: readonly(isLoading),
    isLoadingMore: readonly(isLoadingMore),
    isCreating: readonly(isCreating),
    isLoadingSession: readonly(isLoadingSession),
    isSubmittingFeedback: readonly(isSubmittingFeedback),
    isGenerating: readonly(isGenerating),
    isApplying: readonly(isApplying),
    error: readonly(error),

    feedbackCount,
    canGenerate,

    fetchSessions,
    fetchMoreSessions,
    createSession,
    fetchSession,
    submitFeedback,
    generatePrompt,
    applyPrompt,
    clearGeneratedPreview,
    clearCurrentSession,
  }
}
