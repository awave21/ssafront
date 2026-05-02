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

      <!-- Meta row: identity · channel · agent status -->
      <div class="flex items-center gap-1.5 flex-wrap mt-0.5">
        <span
          v-if="secondaryIdentity"
          class="text-xs truncate"
          :class="[isTelegram ? 'text-blue-600' : 'text-slate-600']"
        >{{ secondaryIdentity }}</span>

        <span v-if="secondaryIdentity && integrationChannelLabel" class="text-slate-300 text-xs">·</span>

        <span v-if="integrationChannelLabel" class="text-xs text-slate-500 truncate">
          {{ integrationChannelLabel }}
        </span>

        <span class="text-slate-300 text-xs">·</span>

        <template v-if="isStreaming && isEnabled">
          <Loader2 class="w-3 h-3 text-indigo-600 animate-spin" />
          <span class="text-xs text-indigo-600 font-medium">В работе...</span>
        </template>
        <template v-else-if="!isEnabled">
          <span class="w-1.5 h-1.5 bg-slate-400 rounded-full flex-shrink-0" />
          <span class="text-xs text-slate-500">{{ agent.name }} · Выкл.</span>
        </template>
        <template v-else>
          <span class="w-1.5 h-1.5 bg-green-500 rounded-full flex-shrink-0" />
          <span class="text-xs text-slate-500">{{ agent.name }}</span>
        </template>
      </div>
    </div>

    <!-- Clear History Button -->
    <button
      @click="confirmClearHistory"
      :disabled="isClearing"
      class="p-2 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
      title="Очистить историю диалога"
    >
      <Loader2 v-if="isClearing" class="w-4 h-4 animate-spin" />
      <Trash2 v-else class="w-4 h-4" />
    </button>

    <!-- Toggle Switch -->
    <div class="flex items-center gap-2 flex-shrink-0">
      <span class="text-xs text-slate-500 hidden sm:block">
        {{ isEnabled ? 'Агент' : 'Пауза' }}
      </span>
      <button
        @click="toggleEnabled"
        class="relative w-11 h-6 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        :class="[
          isEnabled ? 'bg-indigo-600' : 'bg-slate-300'
        ]"
        role="switch"
        :aria-checked="isEnabled"
        :title="isEnabled ? 'Выключить агента для этого диалога' : 'Включить агента для этого диалога'"
      >
        <span
          class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform"
          :class="[
            isEnabled ? 'translate-x-5' : 'translate-x-0'
          ]"
        />
      </button>
    </div>

    <!-- Confirm Clear History Modal -->
    <div
      v-if="showConfirm"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      @click.self="showConfirm = false"
    >
      <div class="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
        <h3 class="text-base font-semibold text-slate-900 mb-2">Очистить историю?</h3>
        <p class="text-sm text-slate-500 mb-5">
          Все сообщения этого диалога будут удалены. Агент забудет контекст переписки. Действие необратимо.
        </p>
        <div class="flex gap-3 justify-end">
          <button
            @click="showConfirm = false"
            class="px-4 py-2 text-sm rounded-lg text-slate-600 hover:bg-slate-100 transition-colors"
          >
            Отмена
          </button>
          <button
            @click="doClearHistory"
            class="px-4 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors"
          >
            Очистить
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowLeft, Loader2, Trash2 } from 'lucide-vue-next'
import { useDialogs } from '../../composables/useDialogs'
import { useMessages } from '../../composables/useMessages'
import type { Agent } from '../../composables/useAgents'
import type { Dialog } from '../../types/dialogs'
import {
  isTelegramDialog,
  resolveDialogSecondaryIdentity,
  resolveDialogUserTitle,
  resolveIntegrationChannelLabel
} from '~/utils/dialogIdentity'

const props = defineProps<{
  agent: Agent
  dialog?: Dialog
  isStreaming?: boolean
}>()

defineEmits<{
  (e: 'back'): void
}>()

const { toggleDialogAgentStatus } = useDialogs()
const { clearHistory } = useMessages()

const showConfirm = ref(false)
const isClearing = ref(false)

const confirmClearHistory = () => {
  showConfirm.value = true
}

const doClearHistory = async () => {
  if (!props.dialog?.id) return
  showConfirm.value = false
  isClearing.value = true
  await clearHistory(props.agent.id, props.dialog.id)
  isClearing.value = false
}

// Computed — agent is active unless explicitly paused for this dialog
const isEnabled = computed(() => (props.dialog?.agent_status ?? 'active') === 'active')

const isTelegram = computed(() => {
  return isTelegramDialog(props.dialog || {})
})

const integrationChannelLabel = computed(() => {
  return resolveIntegrationChannelLabel(props.dialog || {})
})

const secondaryIdentity = computed(() => {
  return resolveDialogSecondaryIdentity(props.dialog || {}) || ''
})

const dialogTitle = computed(() => {
  return resolveDialogUserTitle(props.dialog || {}) || 'Диалог'
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
