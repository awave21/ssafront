<template>
  <AgentPageShell title="Сценарии" :hide-actions="true" :contained="true">
    <div class="flex min-h-0 min-w-0 w-full flex-1 flex-col gap-6">
      <ScenariosList
        :scenarios="scenarios"
        :loading="isLoading"
        :error="error"
        @create="handleCreateScenario"
        @select="handleSelectScenario"
        @toggle="toggleScenario"
        @settings="handleSelectScenario"
        @delete="handleDeleteScenario"
        @retry="fetchScenarios"
      />
    </div>

    <!-- Scenario Editor (Sheet or Modal) -->
    <ScenarioEditor
      v-if="showEditor"
      :is-open="showEditor"
      :scenario="selectedScenario"
      :agent-id="agentId"
      :saving="saveInProgress"
      @close="showEditor = false"
      @save="handleSaveScenario"
    />
  </AgentPageShell>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from '#app'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import ScenariosList from '~/components/agents/scenarios/ScenariosList.vue'
import ScenarioEditor from '~/components/agents/scenarios/ScenarioEditor.vue'
import { useScenarios } from '~/composables/useScenarios'
import { useToast } from '~/composables/useToast'
import type { Scenario, ScenarioUpsertPayload } from '~/types/scenario'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})

const route = useRoute()
const agentId = route.params.id as string
const { scenarios, isLoading, error, fetchScenarios, createScenario, updateScenario, deleteScenario, toggleScenario } = useScenarios(agentId)
const { success: toastSuccess, error: toastError } = useToast()

const showEditor = ref(false)
const selectedScenario = ref<Scenario | null>(null)
const saveInProgress = ref(false)

const handleCreateScenario = () => {
  selectedScenario.value = null
  showEditor.value = true
}

const handleSelectScenario = (scenario: Scenario) => {
  selectedScenario.value = scenario
  showEditor.value = true
}

const handleDeleteScenario = async (scenario: Scenario) => {
  if (!confirm(`Вы уверены, что хотите удалить сценарий «${scenario.name}»?`)) return
  try {
    await deleteScenario(scenario.id)
    toastSuccess('Сценарий удален')
  } catch (err: any) {
    toastError(err.message || 'Не удалось удалить сценарий')
  }
}

const handleSaveScenario = async (payload: ScenarioUpsertPayload) => {
  saveInProgress.value = true
  try {
    if (selectedScenario.value) {
      await updateScenario(selectedScenario.value.id, payload)
      toastSuccess('Сценарий обновлён')
    } else {
      await createScenario(payload)
      toastSuccess('Сценарий создан')
    }
    showEditor.value = false
    selectedScenario.value = null
    await fetchScenarios()
  } catch (err: any) {
    toastError(err.message || 'Не удалось сохранить сценарий')
  } finally {
    saveInProgress.value = false
  }
}

onMounted(() => {
  fetchScenarios()
})
</script>
