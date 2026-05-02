<template>
  <div class="bg-white border-t border-slate-200 px-4 py-3 flex-shrink-0">
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
          placeholder="Написать клиенту..."
          rows="1"
          class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm resize-none placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          :style="{ maxHeight: '150px' }"
        />
      </div>

      <!-- Voice Button (coming soon) -->
      <span
        class="p-2.5 rounded-xl text-slate-300 flex-shrink-0 select-none"
        title="Голосовое сообщение (скоро)"
      >
        <Mic class="w-5 h-5" />
      </span>

      <!-- Send Button -->
      <button
        @click="send"
        :disabled="!canSend"
        class="p-2.5 rounded-xl bg-emerald-600 text-white hover:bg-emerald-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors flex-shrink-0"
        title="Отправить"
      >
        <Loader2 v-if="isSending" class="w-5 h-5 animate-spin" />
        <Send v-else class="w-5 h-5" />
      </button>
    </div>

    <!-- Character count -->
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
import { Send, ImageIcon, Mic, Loader2 } from 'lucide-vue-next'

const props = defineProps<{
  isSending?: boolean
  isStreaming?: boolean
}>()

const emit = defineEmits<{
  (e: 'send-manager', content: string): void
  (e: 'attach-image', file: File): void
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const messageText = ref('')

const canSend = computed(() =>
  messageText.value.trim().length > 0 &&
  messageText.value.length <= 4000 &&
  !props.isSending &&
  !props.isStreaming
)

const send = () => {
  if (!canSend.value) return
  emit('send-manager', messageText.value.trim())
  messageText.value = ''
  nextTick(() => {
    adjustTextareaHeight()
    textareaRef.value?.focus()
  })
}

const handleKeydown = (event: KeyboardEvent) => {
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
  if (file) emit('attach-image', file)
  input.value = ''
}

watch(messageText, (newValue) => {
  if (!newValue) nextTick(adjustTextareaHeight)
})
</script>
