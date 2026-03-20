<template>
  <!-- Two Column Layout: fills parent completely -->
  <div
    class="fixed inset-0 top-[60px] flex overflow-hidden bg-muted transition-all duration-300"
    :class="[isCollapsed ? 'lg:left-16' : 'lg:left-64']"
  >
    <!-- Left Column: Dialogs List (hidden on mobile when chat is open) -->
    <div
      :class="[
        'w-full lg:w-80 xl:w-96 flex-shrink-0 border-r border-border bg-background',
        !showMobileList && selectedDialogId ? 'hidden lg:flex lg:flex-col' : 'flex flex-col'
      ]"
    >
      <DialogsSidebar
        :agents="agents"
        :selected-agent-id="selectedAgentId"
        :selected-dialog-id="selectedDialogId"
        :is-loading="isLoadingAgents"
        @select-agent="handleSelectAgent"
        @select-dialog="handleSelectDialog"
        @create-dialog="handleCreateDialog"
      />
    </div>

    <!-- Right Column: Chat Area -->
    <div
      :class="[
        'flex-1 flex flex-col bg-muted',
        showMobileList && selectedDialogId ? 'hidden lg:flex' : 'flex'
      ]"
    >
      <ChatArea
        v-if="selectedDialogId && selectedAgent"
        :key="selectedDialogId"
        :dialog-id="selectedDialogId"
        :agent="selectedAgent"
        :ws-send-message="wsSendMessage"
        :is-ws-connected="isConnected"
        @back="showMobileList = true"
      />
      <DialogsEmptyState
        v-else
        type="no-dialog"
        @create="handleCreateDialog"
      />
    </div>

    <!-- Auth Modal -->
    <AuthModal
      :is-open="showAuthModal"
      @close="showAuthModal = false"
      @authenticated="handleAuthSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAgents } from '../composables/useAgents'
import { useDialogs } from '../composables/useDialogs'
import { useAuth } from '../composables/useAuth'
import { useAgentWebSocket } from '../composables/useAgentWebSocket'
import type { Agent } from '../composables/useAgents'

// Explicit component imports
import DialogsSidebar from '../components/dialogs/DialogsSidebar.vue'
import ChatArea from '../components/dialogs/ChatArea.vue'
import DialogsEmptyState from '../components/dialogs/DialogsEmptyState.vue'
import AuthModal from '../components/AuthModal.vue'

// Layout state
const { pageTitle, isCollapsed } = useLayoutState()

// Auth
const { isAuthenticated } = useAuth()
const showAuthModal = ref(false)

// Route
const route = useRoute()
const router = useRouter()

// Agents
const { agents, isLoading: isLoadingAgents, fetchAgents } = useAgents()

// Dialogs
const { fetchDialogs, createDialog } = useDialogs()

// Selected state
const selectedAgentId = ref<string | null>(route.query.agentId as string || null)
const selectedDialogId = ref<string | null>(route.query.dialogId as string || null)

// Mobile view state (show chat if dialog is preselected)
const showMobileList = ref(!selectedDialogId.value)
const joinedDialogId = ref<string | null>(null)

// WebSocket connection (replaces SSE)
const { 
  connectionState,
  isConnected,
  sendMessage: wsSendMessage,
  joinDialog,
  leaveDialog
} = useAgentWebSocket(computed(() => selectedAgentId.value))

// Computed
const selectedAgent = computed<Agent | undefined>(() => {
  if (!selectedAgentId.value) return undefined
  return agents.value.find(a => a.id === selectedAgentId.value)
})

// Handlers
const handleSelectAgent = async (agentId: string) => {
  selectedAgentId.value = agentId
  selectedDialogId.value = null
  router.push({ query: { ...route.query, agentId, dialogId: undefined } })
  await fetchDialogs(agentId)
}

const handleSelectDialog = (dialogId: string) => {
  selectedDialogId.value = dialogId
  showMobileList.value = false
  router.push({ query: { ...route.query, dialogId } })
}

// Keep selected IDs in sync with URL query changes
watch(() => route.query.agentId, (agentId) => {
  selectedAgentId.value = typeof agentId === 'string' ? agentId : null
})

watch(() => route.query.dialogId, (dialogId) => {
  selectedDialogId.value = typeof dialogId === 'string' ? dialogId : null
  if (selectedDialogId.value) showMobileList.value = false
})

// Sync WebSocket dialog subscription with current state
watch([isConnected, selectedDialogId], ([connected, dialogId]) => {
  if (!connected) {
    joinedDialogId.value = null
    return
  }

  if (joinedDialogId.value && joinedDialogId.value !== dialogId) {
    leaveDialog(joinedDialogId.value)
    joinedDialogId.value = null
  }

  if (dialogId && joinedDialogId.value !== dialogId) {
    const joined = joinDialog(dialogId)
    if (joined) {
      joinedDialogId.value = dialogId
    } else {
      console.warn('[Page] Failed to join dialog (WebSocket not ready):', dialogId)
    }
  }
}, { immediate: true })

const handleCreateDialog = async () => {
  if (!selectedAgentId.value) {
    if (agents.value.length > 0) {
      await handleSelectAgent(agents.value[0].id)
    }
    return
  }

  const newDialog = await createDialog(selectedAgentId.value)
  if (newDialog) {
    handleSelectDialog(newDialog.id)
  }
}

const handleAuthSuccess = () => {
  showAuthModal.value = false
  loadInitialData()
}

// Load initial data
const loadInitialData = async () => {
  await fetchAgents()
  
  if (selectedAgentId.value) {
    await fetchDialogs(selectedAgentId.value)
  } else if (agents.value.length > 0) {
    await handleSelectAgent(agents.value[0].id)
  }
}

// Watch for auth changes
watch(isAuthenticated, (authenticated) => {
  if (authenticated) loadInitialData()
})

// Initialize
onMounted(() => {
  pageTitle.value = 'Диалоги'
  
  if (isAuthenticated.value) {
    loadInitialData()
  } else {
    showAuthModal.value = true
  }
})

// Define page meta (Nuxt compiler macro)

definePageMeta({
  middleware: 'auth'
})
</script>
