<template>
  <!-- Tool Call / Tool Result — compact pill that expands into a request/response card -->
  <div v-if="isToolMessage" class="flex justify-start w-full">
    <div class="max-w-[85%] sm:max-w-[70%] lg:max-w-[470px]">
      <!-- Collapsed: inline pill -->
      <button
        v-if="!isToolExpanded"
        @click="isToolExpanded = true"
        class="inline-flex items-center gap-1.5 pl-2.5 pr-2.5 py-1 rounded-full bg-blue-600/10 hover:bg-blue-600/15 transition-colors"
      >
        <Zap class="w-3 h-3 text-blue-600 shrink-0" />
        <span class="text-[11px] font-semibold text-blue-600 font-mono">{{ toolNameDisplay }}</span>
        <span v-if="toolDuration" class="text-[10px] text-slate-400">{{ toolDuration }}</span>
        <ChevronDown class="w-3 h-3 text-blue-600 shrink-0" />
      </button>

      <!-- Expanded: request / response card -->
      <div
        v-else
        class="rounded-xl border border-slate-200 bg-white overflow-hidden"
      >
        <!-- Head (clickable to collapse) -->
        <button
          class="w-full flex items-center gap-2 px-3 py-2.5 bg-blue-600/[0.04] text-left"
          @click="isToolExpanded = false"
        >
          <Zap class="w-3.5 h-3.5 text-blue-600 shrink-0" />
          <span class="text-xs font-semibold text-blue-600 font-mono truncate">{{ toolNameDisplay }}</span>
          <span
            v-if="isToolResult && toolOk"
            class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-green-100 shrink-0"
          >
            <Check class="w-2.5 h-2.5 text-green-600" />
            <span class="text-[10px] font-semibold text-green-600">Успешно</span>
          </span>
          <span
            v-else-if="isToolResult"
            class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-red-100 shrink-0"
          >
            <span class="text-[10px] font-semibold text-red-600">Ошибка</span>
          </span>
          <span class="flex-1" />
          <span v-if="toolDuration" class="text-[11px] text-slate-500 shrink-0">{{ toolDuration }}</span>
          <ChevronUp class="w-3.5 h-3.5 text-slate-400 shrink-0" />
        </button>

        <!-- Body -->
        <div class="px-3 py-3">
          <div class="text-[10px] tracking-[0.5px] text-slate-400 mb-1.5">
            {{ isToolResult ? 'ОТВЕТ' : 'ЗАПРОС' }}
          </div>
          <div class="rounded-lg bg-slate-100 p-2.5 overflow-x-auto">
            <pre
              class="text-[11px] leading-[18px] font-mono whitespace-pre-wrap break-all"
              :class="isToolResult ? 'text-cyan-600' : 'text-slate-700'"
            >{{ toolBodyText }}</pre>
          </div>
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
        class="px-4 py-2.5 relative"
        :class="bubbleClasses"
      >
        <!-- Text Message -->
        <template v-if="message.type === 'text'">
          <div
            class="text-sm whitespace-pre-wrap break-words prose prose-sm max-w-none"
            :class="[
              isOutgoing ? 'prose-invert' : '',
              message.is_deleted ? 'italic opacity-60' : ''
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
        <!-- Edit / delete labels -->
        <span v-if="message.is_deleted" class="text-[10px] text-slate-400 italic">удалено</span>
        <span v-else-if="message.is_edited" class="text-[10px] text-slate-400 italic">изменено</span>

        <!-- Time -->
        <span class="text-[10px] text-slate-400" :title="fullDateTime">
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

      <!-- Run meta (агент: токены · время · стоимость) -->
      <div
        v-if="runMeta"
        class="mt-0.5 px-1 text-[10px] text-slate-400"
        :class="isOutgoing ? 'text-right' : 'text-left'"
      >
        {{ runMeta }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Play, Pause, Zap, Check, ChevronDown, ChevronUp } from 'lucide-vue-next'
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

// Tool card collapse state (collapsed by default)
const isToolExpanded = ref(false)

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
  const ui = props.message.user_info
  if (ui) {
    const fullName = [ui.first_name, ui.last_name].filter(Boolean).join(' ')
    if (fullName) return fullName
    if (ui.username) return `@${ui.username}`
  }
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
const isToolResult = computed(() => props.message.type === 'tool_result')
const toolOk = computed(() => (props.message.tool_status ?? 'success') !== 'error')

const toolNameDisplay = computed(() => {
  const name = props.message.tool_name?.trim() || 'function'
  return `${name}()`
})

const toolDuration = computed(() => {
  const ms = props.message.duration_ms
  if (typeof ms === 'number' && ms > 0) {
    return ms < 1000 ? `${ms} мс` : `${(ms / 1000).toFixed(1)} с`
  }
  const seconds = props.message.duration_seconds
  if (!seconds || seconds <= 0) return ''
  if (seconds < 1) return `${Math.round(seconds * 1000)} мс`
  return `${seconds.toFixed(1)} с`
})

const bubbleClasses = computed(() => {
  if (isManager.value) return 'bg-emerald-600 text-white rounded-[16px_16px_4px_16px]'
  if (isAgent.value) return 'bg-indigo-600 text-white rounded-[16px_16px_4px_16px]'
  if (isSystem.value) return 'bg-slate-100 border border-slate-200 text-slate-700 rounded-[16px_16px_16px_4px]'
  return 'bg-white border border-slate-200 text-slate-900 rounded-[16px_16px_16px_4px]'
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

const toolBodyText = computed(() => {
  if (isToolResult.value) {
    if (props.message.result !== undefined && props.message.result !== null) {
      return formatJson(props.message.result)
    }
    return props.message.content || '—'
  }
  if (props.message.args) return formatJson(props.message.args)
  return props.message.content || '—'
})

const formattedTime = computed(() => {
  const date = new Date(props.message.created_at)
  return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
})

const fullDateTime = computed(() => {
  const date = new Date(props.message.created_at)
  return date.toLocaleString('ru-RU', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
})

const formattedDuration = computed(() => {
  const seconds = props.message.duration_seconds || 0
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
})

// Мета запуска для ответа агента — показываем только реальные значения
const runMeta = computed(() => {
  if (!isAgent.value) return ''
  const parts: string[] = []
  const { tokens, latency_ms, cost_rub } = props.message
  if (typeof tokens === 'number' && tokens > 0) {
    parts.push(`${new Intl.NumberFormat('ru-RU').format(tokens)} токенов`)
  }
  if (typeof latency_ms === 'number' && latency_ms > 0) {
    parts.push(`${(latency_ms / 1000).toFixed(1)} с`)
  }
  if (typeof cost_rub === 'number' && cost_rub > 0) {
    parts.push(
      `${new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(cost_rub)} ₽`
    )
  }
  return parts.join(' · ')
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
