<template>
  <div
    class="flex flex-col h-screen w-screen font-sans antialiased"
    :style="{ '--widget-primary': settings.primary_color }"
  >
    <!-- Header -->
    <div
      class="flex items-center justify-between px-4 py-3 flex-shrink-0 shadow-sm"
      :style="{ backgroundColor: settings.primary_color }"
    >
      <div class="flex items-center gap-3 min-w-0">
        <div class="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
          <MessageCircle class="w-5 h-5 text-white" />
        </div>
        <div class="min-w-0">
          <p class="text-white font-bold text-sm leading-tight truncate">{{ settings.title }}</p>
          <p v-if="settings.subtitle" class="text-white/70 text-xs truncate">{{ settings.subtitle }}</p>
        </div>
      </div>
      <button
        @click="closeWidget"
        class="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 transition-colors flex-shrink-0"
        aria-label="Закрыть"
      >
        <X class="w-4 h-4 text-white" />
      </button>
    </div>

    <!-- Messages area -->
    <div
      ref="messagesEl"
      class="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-slate-50"
    >
      <!-- Welcome message -->
      <div v-if="settings.welcome_message && messages.length === 0" class="flex justify-start">
        <div class="max-w-[85%] rounded-2xl rounded-tl-sm px-4 py-2.5 bg-white border border-slate-100 shadow-sm">
          <p class="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">{{ settings.welcome_message }}</p>
        </div>
      </div>

      <template v-for="(msg, idx) in messages" :key="idx">
        <div :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'">
          <div
            :class="[
              'max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
              msg.role === 'user'
                ? 'rounded-tr-sm text-white'
                : 'rounded-tl-sm text-slate-800 bg-white border border-slate-100 shadow-sm',
            ]"
            :style="msg.role === 'user' ? { backgroundColor: settings.primary_color } : {}"
          >
            <p class="whitespace-pre-wrap">{{ msg.content }}</p>
          </div>
        </div>
      </template>

      <!-- Typing indicator -->
      <div v-if="isTyping" class="flex justify-start">
        <div class="rounded-2xl rounded-tl-sm px-4 py-3 bg-white border border-slate-100 shadow-sm">
          <div class="flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style="animation-delay: 0ms" />
            <span class="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style="animation-delay: 150ms" />
            <span class="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style="animation-delay: 300ms" />
          </div>
        </div>
      </div>

      <div ref="bottomEl" />
    </div>

    <!-- Error -->
    <div v-if="loadError" class="px-4 py-2 bg-red-50 border-t border-red-100">
      <p class="text-xs text-red-600">{{ loadError }}</p>
    </div>

    <!-- Composer -->
    <div class="flex-shrink-0 border-t border-slate-200 bg-white px-3 py-3">
      <form @submit.prevent="sendMessage" class="flex items-end gap-2">
        <textarea
          ref="inputEl"
          v-model="inputText"
          rows="1"
          placeholder="Введите сообщение..."
          :disabled="isTyping || !apiKey"
          @keydown.enter.exact.prevent="sendMessage"
          class="flex-1 resize-none rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:border-transparent disabled:opacity-50"
          :style="{ '--tw-ring-color': settings.primary_color + '50' }"
          style="max-height: 120px;"
        />
        <button
          type="submit"
          :disabled="!inputText.trim() || isTyping || !apiKey"
          class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 transition-colors disabled:opacity-40"
          :style="{ backgroundColor: settings.primary_color }"
        >
          <Send class="w-4 h-4 text-white" />
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { MessageCircle, Send, X } from 'lucide-vue-next'
import { useRoute } from '#app'

definePageMeta({ layout: false, middleware: [] })

type ChatMessage = { role: 'user' | 'assistant'; content: string }

const route = useRoute()
const apiKey = ref('')
const visitorId = ref('')
const sessionId = ref('')
const loadError = ref<string | null>(null)
const isTyping = ref(false)
const inputText = ref('')
const messages = ref<ChatMessage[]>([])
const messagesEl = ref<HTMLElement | null>(null)
const bottomEl = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)

const settings = ref({
  title: 'Чат с нами',
  subtitle: '',
  welcome_message: '',
  primary_color: '#3B82F6',
  position: 'bottom-right',
  launcher_icon: 'chat',
})

const VISITOR_KEY = 'chatmedbot:visitor'
const HISTORY_PREFIX = 'chatmedbot:history:'

function getOrCreateVisitorId(): string {
  let id = localStorage.getItem(VISITOR_KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(VISITOR_KEY, id)
  }
  return id
}

function loadLocalHistory(sid: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(HISTORY_PREFIX + sid)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveLocalHistory(sid: string, msgs: ChatMessage[]) {
  try {
    localStorage.setItem(HISTORY_PREFIX + sid, JSON.stringify(msgs.slice(-50)))
  } catch {}
}

function scrollToBottom() {
  nextTick(() => bottomEl.value?.scrollIntoView({ behavior: 'smooth' }))
}

async function loadConfig() {
  const apiBase = window.location.origin
  try {
    const res = await fetch(`${apiBase}/api/v1/widget/config?key=${encodeURIComponent(apiKey.value)}`)
    if (!res.ok) throw new Error(`Config error ${res.status}`)
    const data = await res.json()
    settings.value = { ...settings.value, ...data.settings }
  } catch (e: any) {
    loadError.value = 'Виджет временно недоступен'
  }
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isTyping.value || !apiKey.value) return
  inputText.value = ''
  messages.value.push({ role: 'user', content: text })
  saveLocalHistory(sessionId.value, messages.value)
  scrollToBottom()
  isTyping.value = true

  const apiBase = window.location.origin
  try {
    const res = await fetch(`${apiBase}/api/v1/integrations/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey.value,
      },
      body: JSON.stringify({ message: text, session_id: sessionId.value }),
    })

    if (!res.ok || !res.body) {
      throw new Error(`HTTP ${res.status}`)
    }

    let assistantMsg = { role: 'assistant' as const, content: '' }
    messages.value.push(assistantMsg)
    const msgIdx = messages.value.length - 1

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (line.startsWith('data:')) {
          const raw = line.slice(5).trim()
          if (!raw || raw === '[DONE]') continue
          try {
            const event = JSON.parse(raw)
            if (event.type === 'text_delta' && event.text) {
              messages.value[msgIdx].content += event.text
              scrollToBottom()
            } else if (event.type === 'result' && event.output) {
              if (!messages.value[msgIdx].content) {
                messages.value[msgIdx].content = event.output
              }
              scrollToBottom()
            }
          } catch {}
        }
      }
    }
    saveLocalHistory(sessionId.value, messages.value)
  } catch (e: any) {
    messages.value.push({ role: 'assistant', content: 'Произошла ошибка. Попробуйте ещё раз.' })
  } finally {
    isTyping.value = false
    scrollToBottom()
  }
}

function closeWidget() {
  window.parent?.postMessage({ type: 'chatmedbot:close' }, '*')
}

onMounted(async () => {
  const key = route.query.key as string
  const vid = (route.query.v as string) || getOrCreateVisitorId()
  apiKey.value = key || ''
  visitorId.value = vid

  if (!key) {
    loadError.value = 'API ключ не указан'
    return
  }

  // Compute stable session_id from visitor id (no api_key_id needed)
  sessionId.value = `web:${vid}`
  messages.value = loadLocalHistory(sessionId.value)
  scrollToBottom()
  await loadConfig()
})
</script>

<style>
html, body { margin: 0; padding: 0; overflow: hidden; }
</style>
