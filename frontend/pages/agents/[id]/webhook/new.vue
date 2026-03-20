<template>
  <div class="h-full flex flex-col">
    <div class="flex-1 min-h-0">
    <AgentFunctionsPanel
      ref="functionsPanelRef"
      :agent-id="agentId"
      :hide-list="true"
      :auto-create="true"
    />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AgentFunctionsPanel from '~/components/agents/AgentFunctionsPanel.vue'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'

const route = useRoute()
const functionsPanelRef = ref<InstanceType<typeof AgentFunctionsPanel>>()
const store = useAgentEditorStore()

const agentId = computed(() => {
  const value = route.params.id
  return Array.isArray(value) ? value[0] : String(value || '')
})

const {
  functionsRunAction,
  functionsDeleteAction,
  functionsDuplicateAction,
  functionsToggleStatusAction,
  functionsSaveAction,
  setFunctionsCreateAction,
  clearFunctionsCreateAction,
  functionsSelectedFunction,
  functionsTesting,
  functionsCanSave,
  breadcrumbTitle,
  breadcrumbAgentName,
  breadcrumbBackPath,
} = useLayoutState()
const createActionOwner = 'webhook-new-page'

const syncBreadcrumb = () => {
  breadcrumbTitle.value = 'Webhook'
  breadcrumbAgentName.value = store.agent?.name || ''
  breadcrumbBackPath.value = `/agents/${agentId.value}/webhook`
}

watch(() => store.agent?.name, () => {
  syncBreadcrumb()
}, { immediate: true })

functionsRunAction.value = () => {
  functionsPanelRef.value?.testTool()
}
functionsDeleteAction.value = () => {
  functionsPanelRef.value?.deleteFunction()
}
functionsToggleStatusAction.value = (isActive: boolean) => {
  functionsPanelRef.value?.toggleFunctionStatus(isActive)
}
functionsSaveAction.value = () => {
  functionsPanelRef.value?.saveFunction()
}
functionsDuplicateAction.value = () => {
  functionsPanelRef.value?.duplicateFunction()
}
setFunctionsCreateAction(createActionOwner, null)

watch(() => functionsPanelRef.value?.selectedFunctionRef || null, (val) => {
  functionsSelectedFunction.value = val
}, { deep: true, immediate: true })

watch(() => functionsPanelRef.value?.testingRef ?? false, (val) => {
  functionsTesting.value = val || false
}, { immediate: true })

watch(() => functionsPanelRef.value?.canSaveRef ?? false, (val) => {
  functionsCanSave.value = val || false
}, { immediate: true })

watch(
  () => agentId.value,
  (id) => {
    if (id) store.ensureAgentLoaded(id)
  },
  { immediate: true },
)

onMounted(() => {
  syncBreadcrumb()
  setTimeout(syncBreadcrumb, 0)
})

onUnmounted(() => {
  functionsRunAction.value = null
  functionsDeleteAction.value = null
  functionsDuplicateAction.value = null
  functionsToggleStatusAction.value = null
  functionsSaveAction.value = null
  clearFunctionsCreateAction(createActionOwner)
  functionsSelectedFunction.value = null
  functionsTesting.value = false
  functionsCanSave.value = false
})

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})
</script>
