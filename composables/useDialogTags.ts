import { ref } from 'vue'
import { useApiFetch } from '~/composables/useApiFetch'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type { DialogTag } from '~/types/dialogTags'

export const useDialogTags = (agentId: string) => {
  const apiFetch = useApiFetch()
  const loading = ref(false)
  const error = ref<string | null>(null)
  const tags = ref<DialogTag[]>([])

  const fetchTags = async (sessionId: string) => {
    loading.value = true
    error.value = null
    try {
      tags.value = await apiFetch<DialogTag[]>(`/agents/${agentId}/dialogs/${sessionId}/tags`)
      return tags.value
    } catch (err: any) {
      error.value = getReadableErrorMessage(err, 'Не удалось загрузить теги диалога')
      tags.value = []
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    tags,
    fetchTags,
  }
}
