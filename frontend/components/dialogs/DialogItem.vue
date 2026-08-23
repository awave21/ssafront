<template>
  <div
    class="relative group"
    @contextmenu.prevent="showContextMenu"
  >
    <button
      @click="$emit('click')"
      class="w-full px-4 py-3 flex items-start gap-3 text-left border-b border-slate-100 transition-colors"
      :class="[
        isSelected
          ? 'bg-indigo-50'
          : 'hover:bg-slate-50'
      ]"
    >
      <!-- Dialog Icon -->
      <div
        class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
        :class="[
          isMessenger
            ? (isSelected ? 'bg-blue-100' : 'bg-blue-50')
            : 'bg-slate-100'
        ]"
      >
        <Send
          v-if="isMessenger"
          class="w-5 h-5 text-blue-500"
        />
        <MessageSquare
          v-else
          class="w-5 h-5 text-slate-500"
        />
      </div>

      <!-- Content -->
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-1.5">
          <h3
            class="text-sm font-semibold truncate"
            :class="[
              isSelected ? 'text-indigo-900' : 'text-slate-900'
            ]"
          >
            {{ dialogTitle }}
          </h3>

          <!-- Status / Unread indicator -->
          <StatusIndicator
            v-if="displayStatus"
            :status="displayStatus"
            :count="dialog.unread_count"
          />

          <!-- Канал (виджет/веб) — если нет мессенджер-идентификатора -->
          <span
            v-if="channelTag"
            class="px-1.5 py-0.5 text-[10px] font-medium rounded bg-blue-100 text-blue-700 max-w-[120px] truncate"
            :title="channelTag"
          >
            {{ channelTag }}
          </span>
        </div>

        <!-- Идентификатор контакта -->
        <p
          v-if="secondaryIdentity"
          class="text-xs text-blue-600 truncate mt-0.5"
        >
          {{ secondaryIdentity }}
        </p>

        <p class="text-xs text-slate-500 truncate mt-0.5">
          {{ dialog.last_message_preview || 'Нет сообщений' }}
        </p>
      </div>

      <!-- Right Column -->
      <div class="flex flex-col items-end gap-1.5 flex-shrink-0">
        <!-- Time -->
        <span class="text-xs text-slate-500">
          {{ formattedTime }}
        </span>

        <!-- Agent Status Badge: only show when paused -->
        <span
          v-if="!isDialogAgentActive"
          class="px-1.5 py-0.5 text-[10px] font-medium rounded-full bg-amber-100 text-amber-700 flex items-center gap-0.5"
        >
          <PauseCircle class="w-3 h-3" />
          Пауза
        </span>
      </div>
    </button>

    <!-- Context Menu Trigger (mobile long press fallback) -->
    <button
      @click.stop="showContextMenu"
      class="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-slate-200 transition-opacity"
    >
      <MoreVertical class="w-4 h-4 text-slate-500" />
    </button>

    <!-- Context Menu -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-100 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition duration-75 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
      >
        <div
          v-if="isContextMenuOpen"
          ref="contextMenuRef"
          class="fixed bg-white rounded-xl shadow-lg border border-slate-200 py-1 z-[100] min-w-[160px]"
          :style="{ top: `${menuPosition.y}px`, left: `${menuPosition.x}px` }"
        >
          <button
            @click="startRename"
            class="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2"
          >
            <Pencil class="w-4 h-4" />
            Переименовать
          </button>
          <button
            @click="confirmDelete"
            class="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
          >
            <Trash2 class="w-4 h-4" />
            Удалить
          </button>
        </div>
      </Transition>
    </Teleport>

    <!-- Rename Modal -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div
          v-if="isRenameModalOpen"
          class="fixed inset-0 z-[110] flex items-center justify-center p-4"
        >
          <div class="absolute inset-0 bg-black/50" @click="isRenameModalOpen = false" />
          <div class="relative bg-white rounded-2xl shadow-xl p-6 max-w-sm w-full">
            <h3 class="text-lg font-bold text-slate-900 mb-4">Переименовать диалог</h3>
            <input
              v-model="newTitle"
              type="text"
              placeholder="Название диалога"
              class="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              @keyup.enter="submitRename"
              ref="renameInputRef"
            />
            <div class="flex gap-3 mt-4">
              <button
                @click="isRenameModalOpen = false"
                class="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors"
              >
                Отмена
              </button>
              <button
                @click="submitRename"
                :disabled="!newTitle.trim()"
                class="flex-1 px-4 py-2.5 rounded-xl text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
              >
                Сохранить
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Delete Confirmation -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div
          v-if="isDeleteModalOpen"
          class="fixed inset-0 z-[110] flex items-center justify-center p-4"
        >
          <div class="absolute inset-0 bg-black/50" @click="isDeleteModalOpen = false" />
          <div class="relative bg-white rounded-2xl shadow-xl p-6 max-w-sm w-full">
            <h3 class="text-lg font-bold text-slate-900 mb-2">Удалить диалог?</h3>
            <p class="text-sm text-slate-500 mb-6">
              Это действие нельзя отменить. Все сообщения будут удалены.
            </p>
            <div class="flex gap-3">
              <button
                @click="isDeleteModalOpen = false"
                class="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors"
              >
                Отмена
              </button>
              <button
                @click="submitDelete"
                class="flex-1 px-4 py-2.5 rounded-xl text-sm font-bold text-white bg-red-600 hover:bg-red-700 transition-colors"
              >
                Удалить
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { MessageSquare, Send, MoreVertical, Pencil, Trash2, PauseCircle } from 'lucide-vue-next'
import StatusIndicator from './StatusIndicator.vue'
import type { Dialog, DialogStatus } from '../../types/dialogs'
import {
  isTelegramDialog,
  resolveDialogPlatform,
  resolveDialogSecondaryIdentity,
  resolveDialogUserTitle,
  resolveIntegrationChannelLabel
} from '~/utils/dialogIdentity'

const props = defineProps<{
  dialog: Dialog
  isSelected: boolean
}>()

const emit = defineEmits<{
  (e: 'click'): void
  (e: 'rename', dialogId: string, newTitle: string): void
  (e: 'delete', dialogId: string): void
}>()

// Context menu
const isContextMenuOpen = ref(false)
const contextMenuRef = ref<HTMLElement | null>(null)
const menuPosition = ref({ x: 0, y: 0 })

// Rename modal
const isRenameModalOpen = ref(false)
const newTitle = ref('')
const renameInputRef = ref<HTMLInputElement | null>(null)

// Delete modal
const isDeleteModalOpen = ref(false)

// Close context menu on outside click
onClickOutside(contextMenuRef, () => {
  isContextMenuOpen.value = false
})

// Messenger-каналы получают иконку «отправки» в синем круге, веб/виджет — message-square
const MESSENGER_PLATFORMS = new Set(['telegram', 'telegram_phone', 'whatsapp', 'max'])

const isMessenger = computed(() => {
  if (isTelegramDialog(props.dialog)) return true
  const platform = resolveDialogPlatform(props.dialog)
  return platform ? MESSENGER_PLATFORMS.has(platform) : false
})

const secondaryIdentity = computed(() => {
  return resolveDialogSecondaryIdentity(props.dialog)
})

// Метка канала показывается для веб/виджет-диалогов (когда нет мессенджер-идентификатора)
const channelTag = computed(() => {
  if (isMessenger.value || secondaryIdentity.value) return ''
  const label = resolveIntegrationChannelLabel(props.dialog)
  if (label) return label
  return 'Виджет'
})

const dialogTitle = computed(() => {
  return resolveDialogUserTitle(props.dialog) || 'Диалог'
})

const formattedTime = computed(() => {
  if (!props.dialog.last_message_at) return ''

  const date = new Date(props.dialog.last_message_at)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) {
    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  } else if (diffDays === 1) {
    return 'Вчера'
  } else if (diffDays < 7) {
    return date.toLocaleDateString('ru-RU', { weekday: 'short' })
  } else {
    const isOlderThanYear = diffDays >= 365
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      ...(isOlderThanYear ? { year: 'numeric' } : {})
    })
  }
})

// Per-dialog agent active state
const isDialogAgentActive = computed(() => (props.dialog.agent_status ?? 'active') === 'active')

// Determine which status indicator to show (priority: IN_PROGRESS > ERROR > UNREAD > NEW)
const displayStatus = computed((): DialogStatus | null => {
  const status = props.dialog.status

  // Don't show IN_PROGRESS if agent is paused for this dialog
  if (status === 'IN_PROGRESS' && !isDialogAgentActive.value) {
    // Fall through to next priority
    if (props.dialog.unread_count > 0) return 'UNREAD'
    return null
  }

  if (status === 'IN_PROGRESS') return 'IN_PROGRESS'
  if (status === 'ERROR') return 'ERROR'
  if (props.dialog.unread_count > 0) return 'UNREAD'
  if (status === 'NEW') return 'NEW'

  return null
})

// Methods
const showContextMenu = (event: MouseEvent) => {
  event.preventDefault()
  menuPosition.value = { x: event.clientX, y: event.clientY }
  isContextMenuOpen.value = true
}

const startRename = () => {
  isContextMenuOpen.value = false
  newTitle.value = props.dialog.title || ''
  isRenameModalOpen.value = true
  nextTick(() => {
    renameInputRef.value?.focus()
    renameInputRef.value?.select()
  })
}

const submitRename = () => {
  if (!newTitle.value.trim()) return
  emit('rename', props.dialog.id, newTitle.value.trim())
  isRenameModalOpen.value = false
}

const confirmDelete = () => {
  isContextMenuOpen.value = false
  isDeleteModalOpen.value = true
}

const submitDelete = () => {
  emit('delete', props.dialog.id)
  isDeleteModalOpen.value = false
}
</script>

<style scoped>
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
