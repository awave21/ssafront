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
        :icon="Link"
        @enable="showSqnsModal = true"
        @disable="handleSqnsDisable"
      >
        <template #extra>
          <div v-if="sqnsToolsList.length" class="space-y-2">
            <p class="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Подключённые инструменты</p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <div
                v-for="tool in sqnsToolsList"
                :key="tool.name"
                class="flex items-center gap-2.5 bg-white/50 rounded-md p-2.5 border border-indigo-100/30"
              >
                <div class="w-7 h-7 bg-indigo-100 rounded flex items-center justify-center shrink-0">
                  <Database class="w-3.5 h-3.5 text-indigo-600" />
                </div>
                <div class="min-w-0">
                  <p class="text-xs font-medium text-slate-800 truncate">{{ tool.displayName }}</p>
                  <p v-if="tool.description" class="text-[10px] text-slate-400 truncate">{{ tool.description }}</p>
                </div>
              </div>
            </div>
          </div>
        </template>
      </IntegrationCard>

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
  sqnsErrorMessage,
  sqnsToolsList
} = storeToRefs(store)

const showSqnsModal = ref(false)
const isSqnsSubmitting = ref(false)


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
</script>
