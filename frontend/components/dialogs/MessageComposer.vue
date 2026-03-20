<template>
  <div class="bg-white border-t border-slate-200 px-4 py-3 flex-shrink-0">
    <!-- Manager Mode Notice (agent disabled) -->
    <div
      v-if="!agentEnabled"
      class="mb-3 px-3 py-2 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center gap-2"
    >
      <UserCheck class="w-4 h-4 text-emerald-600 flex-shrink-0" />
      <span class="text-xs text-emerald-700">
        Режим менеджера. Сообщения будут отправлены от вашего имени.
      </span>
    </div>

    <!-- Input Area -->
    <div class="flex items-end gap-2">
      <!-- Attach Image Button -->
      <button
        @click="triggerFileInput"
        :disabled="isSending || isStreaming"
        class="p-2.5 rounded-xl text-slate-500 hover:text-slate-700 hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
        title="Прикрепить изображение"
      >
        <ImageIcon class="w-5 h-5" />
      </button>
      
      <input
        ref="fileInputRef"
        type="file"
        accept="image/*"
        class="hidden"
        @change="handleFileSelect"
      />

      <!-- Text Input -->
      <div class="flex-1 relative">
        <textarea
          ref="textareaRef"
          v-model="messageText"
          @keydown="handleKeydown"
          @input="adjustTextareaHeight"
          :disabled="isSending || isStreaming"
          placeholder="Напишите сообщение..."
          rows="1"
          class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm resize-none placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          :style="{ maxHeight: '150px' }"
        />
      </div>

      <!-- Voice Button (placeholder) -->
      <button
        :disabled="true"
        class="p-2.5 rounded-xl text-slate-400 cursor-not-allowed transition-colors flex-shrink-0"
        title="Голосовое сообщение (скоро)"
      >
        <Mic class="w-5 h-5" />
      </button>

      <!-- Send Button -->
      <button
        @click="send"
        :disabled="!canSend"
        class="p-2.5 rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors flex-shrink-0"
        title="Отправить"
      >
        <Loader2 v-if="isSending" class="w-5 h-5 animate-spin" />
        <Send v-else class="w-5 h-5" />
      </button>
    </div>

    <!-- Character count (optional) -->
    <div v-if="messageText.length > 500" class="mt-1 text-right">
      <span
        class="text-xs"
        :class="messageText.length > 4000 ? 'text-red-500' : 'text-slate-400'"
      >
        {{ messageText.length }} / 4000
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { Send, ImageIcon, Mic, Loader2, UserCheck } from 'lucide-vue-next'

const props = defineProps<{
  isSending?: boolean
  isStreaming?: boolean
  agentEnabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'send', content: string): void
  (e: 'attach-image', file: File): void
}>()

// Refs
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const messageText = ref('')

// Computed
const canSend = computed(() => {
  return messageText.value.trim().length > 0 &&
         messageText.value.length <= 4000 &&
         !props.isSending &&
         !props.isStreaming
})

// Methods
const send = () => {
  if (!canSend.value) return
  
  emit('send', messageText.value.trim())
  messageText.value = ''
  
  nextTick(() => {
    adjustTextareaHeight()
    textareaRef.value?.focus()
  })
}

const handleKeydown = (event: KeyboardEvent) => {
  // Enter to send, Shift+Enter for new line
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    send()
  }
}

const adjustTextareaHeight = () => {
  if (!textareaRef.value) return
  
  textareaRef.value.style.height = 'auto'
  textareaRef.value.style.height = `${Math.min(textareaRef.value.scrollHeight, 150)}px`
}

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  
  if (file) {
    emit('attach-image', file)
  }
  
  // Reset input
  input.value = ''
}

// Reset textarea height when clearing
watch(messageText, (newValue) => {
  if (!newValue) {
    nextTick(adjustTextareaHeight)
  }
})
</script>
