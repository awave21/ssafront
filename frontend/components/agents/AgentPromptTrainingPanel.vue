<template>
  <div class="flex flex-col h-full">
    <!-- Загрузка -->
    <div v-if="isLoading" class="flex items-center justify-center py-20">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <!-- Активная сессия -->
    <ActiveSession
      v-else-if="currentSession && currentSession.status === 'active'"
      :session="currentSession"
      :feedbacks="feedbacks"
      :feedback-count="feedbackCount"
      :can-generate="canGenerate"
      :is-generating="isGenerating"
      :is-applying="isApplying"
      :is-submitting-feedback="isSubmittingFeedback"
      :generated-preview="generatedPreview"
      @submit-feedback="handleSubmitFeedback"
      @generate="handleGenerate"
      @apply="(prompt?: string) => handleApply(prompt)"
      @dismiss-preview="clearGeneratedPreview"
      @back="handleBack"
    />

    <!-- Завершённая / отменённая сессия -->
    <CompletedSession
      v-else-if="currentSession && currentSession.status !== 'active'"
      :session="currentSession"
      :feedbacks="feedbacks"
      @back="handleBack"
    />

    <!-- Список сессий / пустое состояние -->
    <SessionsList
      v-else
      :sessions="sessions"
      :is-loading="isLoading"
      :is-loading-more="isLoadingMore"
      :is-creating="isCreating"
      :has-more="nextCursor !== null"
      :model-groups="modelGroups"
      :is-loading-models="isLoadingModels"
      @create="handleCreateSession"
      @select="handleSelectSession"
      @load-more="fetchMoreSessions"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Loader2 } from 'lucide-vue-next'
import { usePromptTraining } from '~/composables/usePromptTraining'
import { useActiveModels } from '~/composables/useActiveModels'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { useToast } from '~/composables/useToast'
import type { CreateFeedbackPayload } from '~/types/promptTraining'
import SessionsList from '~/components/agents/prompt-training/SessionsList.vue'
import ActiveSession from '~/components/agents/prompt-training/ActiveSession.vue'
import CompletedSession from '~/components/agents/prompt-training/CompletedSession.vue'

const route = useRoute()
const router = useRouter()
const store = useAgentEditorStore()
const { success: toastSuccess, error: toastError } = useToast()
const { modelGroups, isLoading: isLoadingModels, fetchActiveModels } = useActiveModels()

const {
  sessions,
  nextCursor,
  currentSession,
  feedbacks,
  generatedPreview,
  feedbackCount,
  canGenerate,
  isLoading,
  isLoadingMore,
  isCreating,
  isSubmittingFeedback,
  isGenerating,
  isApplying,
  fetchSessions,
  fetchMoreSessions,
  createSession,
  fetchSession,
  submitFeedback,
  generatePrompt,
  applyPrompt,
  clearGeneratedPreview,
  clearCurrentSession,
} = usePromptTraining(() => route.params.id as string)

const getFirstActiveModel = () => {
  for (const group of modelGroups.value) {
    const firstOption = group.options[0]
    if (firstOption?.value) return firstOption.value
  }
  return ''
}

const handleCreateSession = async (metaModel?: string) => {
  const resolvedMetaModel = metaModel || getFirstActiveModel()
  const payload = resolvedMetaModel ? { meta_model: resolvedMetaModel } : {}
  const session = await createSession(payload)
  if (session) {
    router.replace({ query: { ...route.query, session: session.id } })
  }
}

const handleSelectSession = async (sessionId: string) => {
  router.replace({ query: { ...route.query, session: sessionId } })
  await fetchSession(sessionId)
}

const handleBack = () => {
  clearCurrentSession()
  const { session: _, ...rest } = route.query
  router.replace({ query: rest })
}

const handleSubmitFeedback = async (payload: CreateFeedbackPayload) => {
  if (!currentSession.value) return
  await submitFeedback(currentSession.value.id, payload)
}

const handleGenerate = async () => {
  if (!currentSession.value) return
  const resolvedMetaModel = currentSession.value.meta_model || getFirstActiveModel()
  if (!resolvedMetaModel) {
    toastError('Ошибка генерации', 'Нет доступной мета-модели для обучения')
    return
  }
  const request = { meta_model: resolvedMetaModel }
  await generatePrompt(currentSession.value.id, request)
}

const handleApply = async (editedPrompt?: string) => {
  if (!currentSession.value) return
  const session = await applyPrompt(currentSession.value.id, editedPrompt)
  if (session) {
    toastSuccess(
      `Промпт v${session.base_prompt_version ?? ''} активирован`,
      'Новый системный промпт успешно применён'
    )
    // Обновляем данные агента
    if (store.agent) {
      await store.ensureAgentLoaded(store.agent.id)
      if (store.promptHistory) {
        store.promptHistory.fetchHistory()
      }
    }
  }
}

onMounted(async () => {
  fetchActiveModels()
  await fetchSessions()
  const sessionId = route.query.session as string
  if (sessionId) {
    await fetchSession(sessionId)
  }
})

watch(
  () => route.query.session,
  async (sessionId) => {
    if (sessionId && typeof sessionId === 'string') {
      await fetchSession(sessionId)
    } else {
      clearCurrentSession()
    }
  }
)
</script>
