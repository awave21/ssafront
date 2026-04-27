<template>
  <div class="fixed bottom-6 right-20 z-40">
    <div
      v-if="open"
      class="absolute bottom-16 right-0 mb-3 h-[30rem] w-[min(24rem,calc(100vw-1.5rem))] overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-500/40 via-sky-500/30 to-fuchsia-500/40 p-[1px] shadow-2xl"
    >
      <div class="relative flex h-full flex-col rounded-2xl border border-white/10 bg-slate-950/95 backdrop-blur-xl overflow-hidden">
        <div class="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_20%_20%,rgba(99,102,241,0.18),transparent_50%),radial-gradient(circle_at_80%_70%,rgba(236,72,153,0.12),transparent_45%)]" />

        <div class="relative z-10 border-b border-white/10 px-4 py-3">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-sm font-semibold text-white">Вопрос к графу</p>
              <p class="text-xs text-slate-300/80">Ответ по снимку графа GraphRAG (как на экране превью)</p>
            </div>
            <button
              type="button"
              class="rounded-md border border-white/15 px-2 py-1 text-[11px] text-slate-200 transition-colors hover:bg-white/10"
              @click="clearChat"
            >
              Очистить
            </button>
          </div>
        </div>

        <div ref="messagesRef" class="relative z-10 flex-1 space-y-3 overflow-y-auto px-4 py-3 text-sm">
          <div
            v-for="(m, idx) in messages"
            :key="`${idx}-${m.role}`"
            class="max-w-[85%] rounded-xl px-3 py-2 shadow-md"
            :class="m.role === 'assistant' ? 'bg-white/10 text-white' : 'ml-auto bg-white/80 text-slate-900 font-medium'"
          >
            <p class="whitespace-pre-wrap leading-relaxed">{{ m.text }}</p>
            <p
              v-if="m.role === 'assistant' && m.usedNodes != null && m.usedRelations != null"
              class="mt-1 text-[10px] text-slate-300/80"
            >
              Контекст: {{ m.usedNodes }} узлов · {{ m.usedRelations }} связей
            </p>
          </div>

          <div v-if="loading" class="max-w-[35%] rounded-xl bg-white/10 px-3 py-2">
            <div class="flex items-center gap-1.5">
              <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-white" />
              <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-white [animation-delay:120ms]" />
              <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-white [animation-delay:240ms]" />
            </div>
          </div>
        </div>

        <div class="relative z-10 border-t border-white/10 p-3">
          <div class="flex items-center gap-2">
            <input
              v-model="question"
              type="text"
              class="flex-1 rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-300/60"
              placeholder="Задайте вопрос по графу..."
              @keydown.enter.prevent="submit"
              @keydown.esc.prevent="open = false"
            >
            <button
              type="button"
              class="rounded-lg bg-white/10 p-2 text-white transition-colors hover:bg-white/20 disabled:opacity-50"
              :disabled="loading || !question.trim()"
              @click="submit"
            >
              <Send class="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <button
      type="button"
      class="inline-flex h-12 w-12 items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg transition-colors hover:bg-indigo-700"
      :title="open ? 'Закрыть вопросы к графу' : 'Задать вопрос по графу'"
      @click="open = !open"
    >
      <MessageCircle class="h-5 w-5" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { MessageCircle, Send } from 'lucide-vue-next'
import { useApiFetch } from '~/composables/useApiFetch'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type { UnifiedGraphAskResponse } from '../../../types/unifiedGraph'

const props = defineProps<{
  agentId: string
}>()

const apiFetch = useApiFetch()
const open = ref(false)
const loading = ref(false)
const question = ref('')
const messagesRef = ref<HTMLElement | null>(null)
const messages = ref<Array<{ role: 'assistant' | 'user'; text: string; usedNodes?: number; usedRelations?: number }>>([
  { role: 'assistant', text: 'Привет! Задайте вопрос — отвечу только по данным графа.' },
])
const storageKey = computed(() => `unified-graph-ask-chat-v1:${props.agentId}`)

const scrollToBottom = async () => {
  await nextTick()
  if (!messagesRef.value) return
  messagesRef.value.scrollTop = messagesRef.value.scrollHeight
}

const submit = async () => {
  if (!props.agentId || !question.value.trim()) return
  const q = question.value.trim()
  messages.value.push({ role: 'user', text: q })
  question.value = ''
  await scrollToBottom()
  loading.value = true
  try {
    const res = await apiFetch<UnifiedGraphAskResponse>(`/agents/${props.agentId}/unified-graph/ask`, {
      method: 'POST',
      body: {
        question: q,
      },
    })
    messages.value.push({
      role: 'assistant',
      text: res.answer,
      usedNodes: res.used_nodes,
      usedRelations: res.used_relations,
    })
  } catch (e: unknown) {
    messages.value.push({
      role: 'assistant',
      text: getReadableErrorMessage(e, 'Не удалось получить ответ по графу'),
    })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

const clearChat = () => {
  messages.value = [{ role: 'assistant', text: 'Чат очищен. Задайте новый вопрос по графу.' }]
  question.value = ''
}

const onGlobalKeydown = (event: KeyboardEvent) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    open.value = !open.value
  }
}

watch(open, async (v) => {
  if (v) await scrollToBottom()
})

watch(
  messages,
  (value) => {
    if (!import.meta.client) return
    sessionStorage.setItem(storageKey.value, JSON.stringify(value))
  },
  { deep: true },
)

onMounted(() => {
  if (import.meta.client) {
    const raw = sessionStorage.getItem(storageKey.value)
    if (raw) {
      try {
        const parsed = JSON.parse(raw)
        if (Array.isArray(parsed) && parsed.length) messages.value = parsed
      } catch {
        // ignore invalid storage data
      }
    }
  }
  window.addEventListener('keydown', onGlobalKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
})
</script>
