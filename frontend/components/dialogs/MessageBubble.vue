<template>
  <!-- Tool Call / Tool Result — compact inline card, full width -->
  <div v-if="isToolMessage" class="flex justify-start w-full">
    <div class="w-full max-w-[85%] sm:max-w-[70%] lg:max-w-[60%]">
      <div
        class="rounded-xl border text-xs font-mono overflow-hidden"
        :class="message.type === 'tool_call'
          ? 'border-amber-200 bg-amber-50'
          : 'border-emerald-200 bg-emerald-50'"
      >
        <!-- Header -->
        <div
          class="flex items-center gap-2 px-3 py-1.5 border-b"
          :class="message.type === 'tool_call'
            ? 'border-amber-200 bg-amber-100/60'
            : 'border-emerald-200 bg-emerald-100/60'"
        >
          <Wrench v-if="message.type === 'tool_call'" class="w-3 h-3 text-amber-600 shrink-0" />
          <CheckSquare v-else class="w-3 h-3 text-emerald-600 shrink-0" />
          <span
            class="font-semibold text-[11px]"
            :class="message.type === 'tool_call' ? 'text-amber-700' : 'text-emerald-700'"
          >
            {{ message.type === 'tool_call' ? 'Вызов функции' : 'Результат функции' }}
          </span>
          <span
            v-if="message.tool_name"
            class="ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold tracking-wide"
            :class="message.type === 'tool_call'
              ? 'bg-amber-200 text-amber-800'
              : 'bg-emerald-200 text-emerald-800'"
          >
            {{ message.tool_name }}
          </span>
          <span class="ml-auto text-[10px] text-slate-400">{{ formattedTime }}</span>
        </div>
        <!-- Args / Result body -->
        <div class="px-3 py-2 space-y-1.5">
          <template v-if="message.type === 'tool_call' && message.args">
            <div class="text-[10px] text-slate-500 uppercase tracking-wide mb-1">Аргументы</div>
            <pre class="whitespace-pre-wrap break-all text-slate-700 leading-relaxed">{{ formatJson(message.args) }}</pre>
          </template>
          <template v-else-if="message.type === 'tool_result'">
            <div class="text-[10px] text-slate-500 uppercase tracking-wide mb-1">Ответ</div>
            <pre class="whitespace-pre-wrap break-all text-slate-700 leading-relaxed">{{ formatResultContent }}</pre>
          </template>
          <template v-else-if="message.content">
            <pre class="whitespace-pre-wrap break-all text-slate-700 leading-relaxed">{{ message.content }}</pre>
          </template>
        </div>
      </div>
    </div>
  </div>

  <!-- Regular messages -->
  <div
    v-else
    class="flex"
    :class="[
      isOutgoing ? 'justify-end' : 'justify-start'
    ]"
  >
    <div
      class="max-w-[85%] sm:max-w-[70%] lg:max-w-[60%]"
      :class="[
        isOutgoing ? 'order-1' : 'order-2'
      ]"
    >
      <!-- Sender Label (сервер: sender_label / sender_kind; иначе по role) -->
      <div
        class="text-[11px] font-medium mb-1 px-1"
        :class="senderLabelClass"
      >
        {{ senderDisplayLabel }}
      </div>

      <!-- Message Bubble -->
      <div
        class="rounded-2xl px-4 py-2.5 relative"
        :class="bubbleClasses"
      >
        <!-- Text Message -->
        <template v-if="message.type === 'text'">
          <div
            class="text-sm whitespace-pre-wrap break-words prose prose-sm max-w-none"
            :class="[
              isOutgoing ? 'prose-invert' : ''
            ]"
            v-html="renderedContent"
          />
        </template>

        <!-- Image Message -->
        <template v-else-if="message.type === 'image'">
          <img
            :src="message.content"
            alt="Image"
            class="rounded-lg max-w-full cursor-pointer hover:opacity-90 transition-opacity"
            @click="$emit('image-click', message.content)"
          />
        </template>

        <!-- Voice Message -->
        <template v-else-if="message.type === 'voice'">
          <div class="flex items-center gap-3 min-w-[200px]">
            <button
              @click="togglePlay"
              class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 transition-colors"
              :class="[
                isOutgoing
                  ? 'bg-white/20 hover:bg-white/30 text-white'
                  : 'bg-slate-200 hover:bg-slate-300 text-slate-700'
              ]"
            >
              <Pause v-if="isPlaying" class="w-5 h-5" />
              <Play v-else class="w-5 h-5 ml-0.5" />
            </button>
            
            <div class="flex-1">
              <!-- Progress bar -->
              <div
                class="h-1 rounded-full overflow-hidden"
                :class="[
                  isOutgoing ? 'bg-white/30' : 'bg-slate-300'
                ]"
              >
                <div
                  class="h-full transition-all"
                  :class="[
                    isOutgoing ? 'bg-white' : 'bg-slate-600'
                  ]"
                  :style="{ width: `${playProgress}%` }"
                />
              </div>
              
              <!-- Duration -->
              <span
                class="text-xs mt-1 block"
                :class="[
                  isOutgoing ? 'text-white/70' : 'text-slate-500'
                ]"
              >
                {{ formattedDuration }}
              </span>
            </div>
          </div>
        </template>

        <!-- Streaming indicator -->
        <div v-if="message.status === 'streaming'" class="flex items-center gap-1 mt-1">
          <span class="w-1.5 h-1.5 bg-current rounded-full animate-pulse opacity-60" />
        </div>
      </div>

      <!-- Message Meta -->
      <div
        class="flex items-center gap-2 mt-1 px-1"
        :class="[
          isOutgoing ? 'justify-end' : 'justify-start'
        ]"
      >
        <!-- Time -->
        <span class="text-[10px] text-slate-400">
          {{ formattedTime }}
        </span>

        <!-- Status (outgoing messages: agent + manager) -->
        <template v-if="isOutgoing">
          <MessageDeliveryStatus
            :status="message.status"
            @retry="$emit('retry')"
          />
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Play, Pause, Wrench, CheckSquare } from 'lucide-vue-next'
import type { Message } from '../../types/dialogs'
import MessageDeliveryStatus from './MessageDeliveryStatus.vue'
import { createSafeMarkdownRenderer } from '~/utils/safe-markdown'

const props = defineProps<{
  message: Message
}>()

defineEmits<{
  (e: 'retry'): void
  (e: 'image-click', url: string): void
}>()

// Markdown renderer
const md = createSafeMarkdownRenderer({
  linkify: true,
  breaks: true
})

// Audio playback
const isPlaying = ref(false)
const playProgress = ref(0)
const audioRef = ref<HTMLAudioElement | null>(null)

// Computed
const isAgent = computed(() => props.message.role === 'agent')
const isManager = computed(() => props.message.role === 'manager')
const isSystem = computed(() => props.message.role === 'system')
const isOutgoing = computed(() => isAgent.value || isManager.value)

const senderDisplayLabel = computed(() => {
  const fromApi = props.message.sender_label?.trim()
  if (fromApi) return fromApi
  if (isSystem.value) return 'Система'
  if (isManager.value) {
    if (props.message.sender_kind === 'wappi_operator') {
      return props.message.user_info?.integration_channel_label
        ? `Оператор (${props.message.user_info.integration_channel_label})`
        : 'Оператор (мессенджер)'
    }
    return 'Менеджер'
  }
  if (isAgent.value) return 'Агент'
  if (props.message.sender_kind === 'contact') return 'Клиент'
  return 'Пользователь'
})

const senderLabelClass = computed(() => {
  if (isSystem.value) return 'text-left text-slate-400'
  if (isManager.value) return 'text-right text-emerald-600'
  if (isAgent.value) return 'text-right text-indigo-600'
  return 'text-left text-slate-500'
})
const isToolMessage = computed(() => props.message.type === 'tool_call' || props.message.type === 'tool_result')

const bubbleClasses = computed(() => {
  if (isManager.value) return 'bg-emerald-600 text-white rounded-br-sm'
  if (isAgent.value) return 'bg-indigo-600 text-white rounded-br-sm'
  if (isSystem.value) return 'bg-slate-100 border border-slate-200 text-slate-700 rounded-bl-sm'
  return 'bg-white border border-slate-200 text-slate-900 rounded-bl-sm shadow-sm'
})

const renderedContent = computed(() => {
  if (props.message.type !== 'text') return ''
  return md.render(props.message.content)
})

const formatJson = (value: unknown): string => {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const formatResultContent = computed(() => {
  if (props.message.result !== undefined && props.message.result !== null) {
    return formatJson(props.message.result)
  }
  return props.message.content || '—'
})

const formattedTime = computed(() => {
  const date = new Date(props.message.created_at)
  return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
})

const formattedDuration = computed(() => {
  const seconds = props.message.duration_seconds || 0
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
})

// Methods
const togglePlay = () => {
  if (!audioRef.value) {
    audioRef.value = new Audio(props.message.content)
    
    audioRef.value.addEventListener('timeupdate', () => {
      if (audioRef.value) {
        playProgress.value = (audioRef.value.currentTime / audioRef.value.duration) * 100
      }
    })
    
    audioRef.value.addEventListener('ended', () => {
      isPlaying.value = false
      playProgress.value = 0
    })
  }

  if (isPlaying.value) {
    audioRef.value.pause()
  } else {
    audioRef.value.play()
  }
  
  isPlaying.value = !isPlaying.value
}
</script>

<style scoped>
.prose p {
  margin: 0;
}
.prose p + p {
  margin-top: 0.5em;
}
.prose code {
  background: rgba(0, 0, 0, 0.1);
  padding: 0.125em 0.25em;
  border-radius: 0.25em;
  font-size: 0.875em;
}
.prose pre {
  background: rgba(0, 0, 0, 0.1);
  padding: 0.75em;
  border-radius: 0.5em;
  overflow-x: auto;
}
.prose a {
  color: inherit;
  text-decoration: underline;
}
</style>
