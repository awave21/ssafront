<template>
  <div
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
      <!-- Sender Label -->
      <div
        class="text-[11px] font-medium mb-1 px-1"
        :class="[
          isManager ? 'text-right text-emerald-600'
            : isAgent ? 'text-right text-indigo-600'
            : 'text-left text-slate-500'
        ]"
      >
        {{ isManager ? 'Менеджер' : isAgent ? 'Агент' : 'Пользователь' }}
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
          <!-- Sending -->
          <Loader2
            v-if="message.status === 'sending'"
            class="w-3 h-3 text-slate-400 animate-spin"
          />
          
          <!-- Sent -->
          <Check
            v-else-if="message.status === 'sent'"
            class="w-3 h-3 text-slate-400"
          />
          
          <!-- Failed -->
          <div
            v-else-if="message.status === 'failed'"
            class="flex items-center gap-1"
          >
            <AlertCircle class="w-3 h-3 text-red-500" />
            <button
              @click="$emit('retry')"
              class="text-[10px] text-red-500 hover:text-red-600 font-medium"
            >
              Повторить
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Play, Pause, Check, Loader2, AlertCircle } from 'lucide-vue-next'
import type { Message } from '../../types/dialogs'
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
const isOutgoing = computed(() => isAgent.value || isManager.value)

const bubbleClasses = computed(() => {
  if (isManager.value) return 'bg-emerald-600 text-white rounded-br-sm'
  if (isAgent.value) return 'bg-indigo-600 text-white rounded-br-sm'
  return 'bg-white border border-slate-200 text-slate-900 rounded-bl-sm shadow-sm'
})

const renderedContent = computed(() => {
  if (props.message.type !== 'text') return ''
  return md.render(props.message.content)
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
