<template>
  <div class="bg-background rounded-md border border-border p-4 sm:p-5 space-y-5">
    <div class="mb-6">
      <h3 class="text-lg font-bold text-slate-900">Инструменты и подключения</h3>
      <p class="text-sm text-slate-500 mt-1">
        Подключите внешние инструменты и API для расширения возможностей вашего агента.
        Мы поддерживаем различные CRM-системы и сервисы.
      </p>
    </div>

    <div class="space-y-5">
      <IntegrationCard
        title="SQNS"
        description="Интеграция с CRM для управления визитами и бронированием."
        :status="isSqnsEnabled ? (sqnsStatus?.sqnsStatus === 'error' ? 'error' : 'active') : 'inactive'"
        :status-label="sqnsStatusLabel"
        :host="sqnsHostLabel"
        :last-sync="formattedSqnsSyncAt"
        :error="sqnsErrorMessage"
        :warning="sqnsStatus?.sqnsWarning"
        :is-syncing="isSqnsSyncing"
        :icon="Link"
        @enable="showSqnsModal = true"
        @disable="handleSqnsDisable"
        @sync="handleSqnsSync"
      />

      <IntegrationCard
        title="Klientiks CRM"
        description="Эффективный инструмент для управления медицинской клиникой и медицинскими работниками."
        status="soon"
        status-label="скоро"
        :icon="Link"
      />
    </div>

    <SQNSModal
      :is-open="showSqnsModal"
      :is-submitting="isSqnsSubmitting"
      @close="showSqnsModal = false"
      @submit="handleSqnsSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { useAgents } from '~/composables/useAgents'
import { useToast } from '~/composables/useToast'
import { getReadableErrorMessage } from '~/utils/api-errors'
import { storeToRefs } from 'pinia'
import { Database, Link } from 'lucide-vue-next'
import IntegrationCard from '~/components/IntegrationCard.vue'
import SQNSModal from '~/components/SQNSModal.vue'

const store = useAgentEditorStore()
const {
  agent,
  sqnsStatus,
  isSqnsEnabled,
  sqnsStatusLabel,
  sqnsHostLabel,
  formattedSqnsSyncAt,
  sqnsErrorMessage
} = storeToRefs(store)

const showSqnsModal = ref(false)
const isSqnsSubmitting = ref(false)
const isSqnsSyncing = ref(false)

const { success: toastSuccess, error: toastError } = useToast()

watch(agent, async (value) => {
  if (!value) return
  await store.ensureSqnsStatusLoaded()
  await store.ensureSqnsHints()
}, { immediate: true })

const handleSqnsSubmit = async (payload: { email: string; password: string }) => {
  isSqnsSubmitting.value = true
  try {
    const success = await store.enableSqnsIntegration(payload)
    if (success) {
      await store.ensureSqnsHints()
      showSqnsModal.value = false
    }
  } finally {
    isSqnsSubmitting.value = false
  }
}

const handleSqnsDisable = async () => {
  await store.disableSqnsIntegration()
}

const handleSqnsSync = async () => {
  if (!agent.value) return
  isSqnsSyncing.value = true
  try {
    const { syncSqns } = useAgents()
    const result = await syncSqns(agent.value.id)
    toastSuccess(
      'Синхронизация завершена',
      `Обновлено: ${result.resources_synced} специалистов, ${result.services_synced} услуг, ${result.categories_synced} категорий`
    )
    await store.loadSqnsStatusForAgent()
  } catch (err: any) {
    toastError('Ошибка синхронизации', getReadableErrorMessage(err, 'Не удалось выполнить синхронизацию'))
  } finally {
    isSqnsSyncing.value = false
  }
}
</script>
