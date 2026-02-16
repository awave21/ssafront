<template>
  <div class="h-full">
    <AgentFunctionsPanel ref="functionsPanelRef" :agent-id="route.params.id as string" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import AgentFunctionsPanel from '~/components/agents/AgentFunctionsPanel.vue'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'

const route = useRoute()
const functionsPanelRef = ref<InstanceType<typeof AgentFunctionsPanel>>()
const store = useAgentEditorStore()

const { 
  functionsRunAction, 
  functionsDeleteAction, 
  functionsDuplicateAction,
  functionsToggleStatusAction,
  functionsSaveAction,
  functionsSelectedFunction,
  functionsTesting,
  functionsCanSave,
  breadcrumbTitle,
  breadcrumbAgentName
} = useLayoutState()

// Set breadcrumb
breadcrumbTitle.value = 'Функции'
watch(() => store.agent?.name, (name) => {
  breadcrumbAgentName.value = name || ''
}, { immediate: true })

// Provide actions to layout immediately
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

// Watch for changes in panel state and sync to layout
watch(() => functionsPanelRef.value?.selectedFunction, (val) => {
  functionsSelectedFunction.value = val
}, { deep: true, immediate: true })

watch(() => functionsPanelRef.value?.testing, (val) => {
  functionsTesting.value = val || false
}, { immediate: true })

watch(() => functionsPanelRef.value?.canSave, (val) => {
  functionsCanSave.value = val || false
}, { immediate: true })

// Load agent data
const resolveAgentId = (value: string | string[] | undefined) =>
  Array.isArray(value) ? value[0] : value

watch(
  () => route.params.id,
  (id) => {
    const resolved = resolveAgentId(id as string | string[] | undefined)
    if (resolved) {
      store.ensureAgentLoaded(resolved)
    }
  },
  { immediate: true }
)

onUnmounted(() => {
  functionsRunAction.value = null
  functionsDeleteAction.value = null
  functionsDuplicateAction.value = null
  functionsToggleStatusAction.value = null
  functionsSaveAction.value = null
  functionsSelectedFunction.value = null
  functionsTesting.value = false
  functionsCanSave.value = false
  breadcrumbTitle.value = ''
  breadcrumbAgentName.value = ''
})

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})
</script>
