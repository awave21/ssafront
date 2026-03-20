<template>
  <div class="bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-3 flex-shrink-0">
    <!-- Back Button (mobile) -->
    <button
      @click="$emit('back')"
      class="lg:hidden p-2 -ml-2 rounded-lg text-slate-600 hover:bg-slate-100 transition-colors"
    >
      <ArrowLeft class="w-5 h-5" />
    </button>

    <!-- User Avatar -->
    <div
      class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
      :class="[
        isTelegram
          ? 'bg-blue-100'
          : 'bg-gradient-to-br from-indigo-500 to-purple-600'
      ]"
    >
      <!-- Telegram Icon -->
      <svg
        v-if="isTelegram"
        class="w-5 h-5 text-blue-600"
        viewBox="0 0 24 24"
        fill="currentColor"
      >
        <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
      </svg>
      <!-- Default: User Initials -->
      <span v-else class="text-white font-bold text-sm">
        {{ userInitials }}
      </span>
    </div>

    <!-- User/Dialog Info -->
    <div class="flex-1 min-w-0">
      <!-- User name / Dialog title -->
      <h2 class="text-sm font-semibold text-slate-900 truncate">
        {{ dialogTitle }}
      </h2>
      
      <!-- Username -->
      <p
        v-if="isTelegram && username"
        class="text-xs text-blue-600 truncate"
      >
        @{{ username }}
      </p>
      
      <!-- Agent name & Status -->
      <div class="flex items-center gap-1.5 mt-0.5">
        <template v-if="isStreaming && isEnabled">
          <Loader2 class="w-3 h-3 text-indigo-600 animate-spin" />
          <span class="text-xs text-indigo-600 font-medium">В работе...</span>
        </template>
        <template v-else-if="!isEnabled">
          <span class="w-2 h-2 bg-slate-400 rounded-full" />
          <span class="text-xs text-slate-500">{{ agent.name }} · Выкл.</span>
        </template>
        <template v-else>
          <span class="w-2 h-2 bg-green-500 rounded-full" />
          <span class="text-xs text-slate-500">{{ agent.name }}</span>
        </template>
      </div>
    </div>

    <!-- Toggle Switch -->
    <div class="flex items-center gap-2">
      <button
        @click="toggleEnabled"
        class="relative w-11 h-6 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        :class="[
          isEnabled ? 'bg-indigo-600' : 'bg-slate-300'
        ]"
        role="switch"
        :aria-checked="isEnabled"
        :title="isEnabled ? 'Выключить агента' : 'Включить агента'"
      >
        <span
          class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform"
          :class="[
            isEnabled ? 'translate-x-5' : 'translate-x-0'
          ]"
        />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowLeft, Loader2 } from 'lucide-vue-next'
import { useDialogs } from '../../composables/useDialogs'
import type { Agent } from '../../composables/useAgents'
import type { Dialog } from '../../types/dialogs'

const props = defineProps<{
  agent: Agent
  dialog?: Dialog
  isStreaming?: boolean
}>()

defineEmits<{
  (e: 'back'): void
}>()

// Per-dialog agent status
const { toggleDialogAgentStatus } = useDialogs()

// Computed — agent is active unless explicitly paused for this dialog
const isEnabled = computed(() => (props.dialog?.agent_status ?? 'active') === 'active')

const isTelegram = computed(() => {
  return props.dialog?.platform === 'telegram' || props.dialog?.id?.startsWith('telegram:')
})

const username = computed(() => {
  return props.dialog?.user_info?.username || ''
})

const dialogTitle = computed(() => {
  const userInfo = props.dialog?.user_info
  // Prioritize user info for title
  if (userInfo?.first_name || userInfo?.last_name) {
    return [userInfo.first_name, userInfo.last_name].filter(Boolean).join(' ')
  }
  if (userInfo?.username) return `@${userInfo.username}`
  // For Telegram dialogs without user_info, extract ID from dialog ID
  if (isTelegram.value && props.dialog?.id) {
    const telegramId = props.dialog.id.replace('telegram:', '')
    return `Telegram #${telegramId}`
  }
  // Fallback - don't use dialog.title as it contains message preview
  return 'Диалог'
})

const userInitials = computed(() => {
  const userInfo = props.dialog?.user_info
  if (userInfo?.first_name) {
    const first = userInfo.first_name.charAt(0)
    const last = userInfo.last_name?.charAt(0) || ''
    return (first + last).toUpperCase()
  }
  if (userInfo?.username) {
    return userInfo.username.charAt(0).toUpperCase()
  }
  return '?'
})

// Methods
const toggleEnabled = async () => {
  if (!props.dialog?.id) return
  await toggleDialogAgentStatus(props.agent.id, props.dialog)
}
</script>
