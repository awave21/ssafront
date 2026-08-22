<template>
  <AgentPageShell title="Сценарии" :hide-actions="true" :contained="true">
    <div class="flex min-h-0 min-w-0 w-full flex-1 flex-col gap-6">
      <ScenariosList
        :scenarios="scenarios"
        :loading="isLoading"
        :error="error"
        @create="handleCreateScenario"
        @open-catalog="openCatalog"
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
      :preset="activePreset"
      :agent-id="agentId"
      :saving="saveInProgress"
      @close="showEditor = false"
      @save="handleSaveScenario"
    />

    <ConfirmDialog
      :open="Boolean(scenarioPendingDelete)"
      :title="`Удалить сценарий «${scenarioPendingDelete?.name || 'Без названия'}»?`"
      description="Сценарий и его действия будут удалены безвозвратно."
      :busy="deleteInProgress"
      @update:open="!$event && (scenarioPendingDelete = null)"
      @confirm="confirmDeleteScenario"
    />
  </AgentPageShell>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { findScenarioPreset } from '~/utils/scenarioPresets'
import type { ScenarioPreset } from '~/utils/scenarioPresets'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import ScenariosList from '~/components/agents/scenarios/ScenariosList.vue'
import ScenarioEditor from '~/components/agents/scenarios/ScenarioEditor.vue'
import ConfirmDialog from '~/components/common/ConfirmDialog.vue'
import { useScenarios } from '~/composables/useScenarios'
import { useToast } from '~/composables/useToast'
import type { Scenario, ScenarioUpsertPayload } from '~/types/scenario'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})

const route = useRoute()
const router = useRouter()
const agentId = route.params.id as string
const { scenarios, isLoading, error, fetchScenarios, createScenario, updateScenario, deleteScenario, toggleScenario } = useScenarios(agentId)
const { success: toastSuccess, error: toastError } = useToast()

const showEditor = ref(false)
const selectedScenario = ref<Scenario | null>(null)
const saveInProgress = ref(false)
const activePreset = ref<ScenarioPreset | null>(null)
const scenarioPendingDelete = ref<Scenario | null>(null)
const deleteInProgress = ref(false)

const handleCreateScenario = () => {
  selectedScenario.value = null
  activePreset.value = null
  showEditor.value = true
}

const openCatalog = () => {
  router.push(`/agents/${agentId}/scenarios/catalog`)
}

const handleSelectScenario = (scenario: Scenario) => {
  activePreset.value = null
  selectedScenario.value = scenario
  showEditor.value = true
}

const handleDeleteScenario = (scenario: Scenario) => {
  scenarioPendingDelete.value = scenario
}

const confirmDeleteScenario = async () => {
  const scenario = scenarioPendingDelete.value
  if (!scenario || deleteInProgress.value) return

  // Убираем карточку сразу: пустая пауза до ответа сервера читается как
  // «кнопка не сработала». При ошибке возвращаем на прежнее место.
  const index = scenarios.value.findIndex((item) => item.id === scenario.id)
  const snapshot = index >= 0 ? scenarios.value[index] : null
  if (index >= 0) scenarios.value.splice(index, 1)

  scenarioPendingDelete.value = null
  deleteInProgress.value = true
  try {
    await deleteScenario(scenario.id)
    toastSuccess('Сценарий удалён', scenario.name)
  } catch (err: any) {
    if (snapshot) scenarios.value.splice(index, 0, snapshot)
    toastError('Не удалось удалить сценарий', err?.message || '')
  } finally {
    deleteInProgress.value = false
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
  // Пришли из каталога — сразу открываем редактор с заготовкой и убираем
  // preset из адреса, чтобы обновление страницы не открывало панель снова.
  const preset = findScenarioPreset(route.query.preset as string | undefined)
  if (preset) {
    activePreset.value = preset
    selectedScenario.value = null
    showEditor.value = true
    router.replace(`/agents/${agentId}/scenarios`)
  }
})
</script>
