<template>
  <div class="h-full flex flex-col">
    <!-- Agent Selector -->
    <div class="p-4 border-b border-slate-200">
      <div class="relative" ref="dropdownRef">
        <button
          @click="isAgentDropdownOpen = !isAgentDropdownOpen"
          class="w-full flex items-center gap-3 px-3 py-2.5 bg-slate-50 hover:bg-slate-100 rounded-xl transition-colors"
        >
          <!-- Agent Avatar -->
          <div class="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center flex-shrink-0">
            <span class="text-white font-bold text-sm">
              {{ selectedAgentInitials }}
            </span>
          </div>
          
          <!-- Agent Name -->
          <div class="flex-1 text-left min-w-0">
            <p class="text-sm font-semibold text-slate-900 truncate">
              {{ selectedAgentName }}
            </p>
            <p class="text-xs text-slate-500">
              {{ agents.length }} {{ agentsCountLabel }}
            </p>
          </div>
          
          <!-- Chevron -->
          <ChevronDown
            class="w-5 h-5 text-slate-400 transition-transform"
            :class="{ 'rotate-180': isAgentDropdownOpen }"
          />
        </button>

        <!-- Dropdown -->
        <Transition
          enter-active-class="transition duration-150 ease-out"
          enter-from-class="opacity-0 scale-95"
          enter-to-class="opacity-100 scale-100"
          leave-active-class="transition duration-100 ease-in"
          leave-from-class="opacity-100 scale-100"
          leave-to-class="opacity-0 scale-95"
        >
          <div
            v-if="isAgentDropdownOpen"
            class="absolute top-full left-0 right-0 mt-2 bg-white rounded-xl shadow-lg border border-slate-200 z-50 max-h-64 overflow-y-auto"
          >
            <div class="p-2">
              <button
                v-for="agent in agents"
                :key="agent.id"
                @click="selectAgent(agent.id)"
                class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors"
                :class="[
                  agent.id === selectedAgentId
                    ? 'bg-indigo-50 text-indigo-900'
                    : 'hover:bg-slate-50 text-slate-700'
                ]"
              >
                <div class="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center flex-shrink-0">
                  <span class="text-white font-bold text-xs">
                    {{ getAgentInitials(agent.name) }}
                  </span>
                </div>
                <span class="text-sm font-medium truncate">{{ agent.name }}</span>
                <Check v-if="agent.id === selectedAgentId" class="w-4 h-4 text-indigo-600 ml-auto flex-shrink-0" />
              </button>
              
              <div v-if="agents.length === 0" class="px-3 py-4 text-center text-sm text-slate-500">
                Нет доступных агентов
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Search -->
    <div class="px-4 py-3">
      <div class="relative">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Поиск диалогов..."
          class="w-full pl-9 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
        />
      </div>
    </div>

    <!-- Dialogs List -->
    <div class="flex-1 overflow-y-auto">
      <div v-if="isLoading || isDialogsLoading" class="flex items-center justify-center py-8">
        <Loader2 class="w-6 h-6 text-indigo-600 animate-spin" />
      </div>

      <div v-else-if="filteredDialogs.length === 0" class="px-4 py-8 text-center">
        <MessageSquare class="w-12 h-12 text-slate-300 mx-auto mb-3" />
        <p class="text-sm text-slate-500">
          {{ searchQuery ? 'Диалоги не найдены' : 'Нет диалогов' }}
        </p>
        <button
          v-if="!searchQuery && selectedAgentId"
          @click="$emit('create-dialog')"
          class="mt-3 text-sm text-indigo-600 hover:text-indigo-700 font-medium"
        >
          Создать первый диалог
        </button>
      </div>

      <TransitionGroup
        v-else
        tag="div"
        class="divide-y divide-slate-100"
        name="dialog-list"
      >
        <DialogItem
          v-for="dialog in filteredDialogs"
          :key="dialog.id"
          :dialog="dialog"
          :is-selected="dialog.id === selectedDialogId"
          @click="$emit('select-dialog', dialog.id)"
          @rename="handleRenameDialog"
          @delete="handleDeleteDialog"
        />
      </TransitionGroup>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { ChevronDown, Search, Check, Loader2, MessageSquare } from 'lucide-vue-next'
import { useDialogs } from '../../composables/useDialogs'
import DialogItem from './DialogItem.vue'
import type { Agent } from '../../composables/useAgents'

const props = defineProps<{
  agents: readonly Agent[]
  selectedAgentId: string | null
  selectedDialogId: string | null
  isLoading?: boolean
}>()

const emit = defineEmits<{
  (e: 'select-agent', agentId: string): void
  (e: 'select-dialog', dialogId: string): void
  (e: 'create-dialog'): void
}>()

// Dialogs composable
const { dialogs, isLoading: isDialogsLoading, updateDialog, deleteDialog } = useDialogs()

// Agent dropdown
const dropdownRef = ref<HTMLElement | null>(null)
const isAgentDropdownOpen = ref(false)

// Search
const searchQuery = ref('')

// Close dropdown on outside click
onClickOutside(dropdownRef, () => {
  isAgentDropdownOpen.value = false
})

// Computed
const selectedAgent = computed(() => {
  return props.agents.find(a => a.id === props.selectedAgentId)
})

const selectedAgentName = computed(() => {
  return selectedAgent.value?.name || 'Выберите агента'
})

const selectedAgentInitials = computed(() => {
  return getAgentInitials(selectedAgent.value?.name || '')
})

const agentsCountLabel = computed(() => {
  const count = props.agents.length
  if (count === 1) return 'агент'
  if (count >= 2 && count <= 4) return 'агента'
  return 'агентов'
})

const filteredDialogs = computed(() => {
  if (!searchQuery.value.trim()) return dialogs.value
  
  const query = searchQuery.value.toLowerCase()
  return dialogs.value.filter(dialog => {
    const title = dialog.title || 'Диалог'
    const preview = dialog.last_message_preview || ''
    return title.toLowerCase().includes(query) || preview.toLowerCase().includes(query)
  })
})

// Methods
const getAgentInitials = (name: string): string => {
  if (!name) return '?'
  return name
    .split(' ')
    .map(word => word.charAt(0))
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

const selectAgent = (agentId: string) => {
  isAgentDropdownOpen.value = false
  emit('select-agent', agentId)
}

const handleRenameDialog = async (dialogId: string, newTitle: string) => {
  if (!props.selectedAgentId) return
  await updateDialog(props.selectedAgentId, dialogId, { title: newTitle })
}

const handleDeleteDialog = async (dialogId: string) => {
  if (!props.selectedAgentId) return
  await deleteDialog(props.selectedAgentId, dialogId)
}

// Watch for agent changes to clear search
watch(() => props.selectedAgentId, () => {
  searchQuery.value = ''
})
</script>

<style scoped>
/* Smooth reorder when dialog moves to top */
.dialog-list-move {
  transition: transform 0.25s ease;
}
/* New dialog appearing */
.dialog-list-enter-active {
  transition: opacity 0.2s ease-out, transform 0.2s ease-out;
}
.dialog-list-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}
/* Dialog removed */
.dialog-list-leave-active {
  transition: opacity 0.15s ease-in;
  position: absolute;
  width: 100%;
}
.dialog-list-leave-to {
  opacity: 0;
}
</style>
