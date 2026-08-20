<template>
  <div :class="expanded ? 'fixed inset-y-0 right-0 z-40 flex' : 'fixed bottom-6 right-20 z-40'">
    <div
      v-if="open"
      :class="[
        'overflow-hidden bg-gradient-to-br from-indigo-500/40 via-sky-500/30 to-fuchsia-500/40 p-[1px] shadow-2xl',
        expanded
          ? 'h-full w-[min(36rem,calc(100vw-1.5rem))] rounded-l-2xl'
          : 'absolute bottom-16 right-0 mb-3 h-[40rem] w-[min(30rem,calc(100vw-1.5rem))] rounded-2xl',
      ]"
    >
      <div
        :class="[
          'relative flex h-full flex-col border border-white/10 bg-slate-950/95 backdrop-blur-xl overflow-hidden',
          expanded ? 'rounded-l-2xl' : 'rounded-2xl',
        ]"
      >
        <div class="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_20%_20%,rgba(99,102,241,0.18),transparent_50%),radial-gradient(circle_at_80%_70%,rgba(236,72,153,0.12),transparent_45%)]" />

        <!-- Header -->
        <div class="relative z-10 border-b border-white/10 px-4 py-3">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-sm font-semibold text-white">Спросить у графа</p>
              <p class="text-[11px] text-slate-400">Режим: как у LLM-агента в проде</p>
            </div>
            <div class="flex items-center gap-1">
              <button
                type="button"
                class="rounded-md border border-white/15 p-1.5 text-slate-200 transition-colors hover:bg-white/10"
                :title="expanded ? 'Свернуть в виджет' : 'Развернуть на всю высоту'"
                @click="toggleExpanded"
              >
                <PanelRightClose v-if="expanded" class="h-3.5 w-3.5" />
                <PanelRightOpen v-else class="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                class="rounded-md border border-white/15 px-2 py-1 text-[11px] text-slate-200 transition-colors hover:bg-white/10"
                @click="clearChat"
              >
                Очистить
              </button>
            </div>
          </div>
        </div>

        <!-- Messages -->
        <div ref="messagesRef" class="relative z-10 flex-1 space-y-3 overflow-y-auto px-4 py-3 text-sm">
          <div
            v-for="(m, idx) in messages"
            :key="`${idx}-${m.role}`"
            class="max-w-[95%] rounded-xl px-3 py-2 shadow-md"
            :class="m.role === 'assistant' ? 'bg-white/10 text-white' : 'ml-auto bg-white/80 text-slate-900 font-medium'"
          >
            <p class="whitespace-pre-wrap leading-relaxed">{{ m.text }}</p>

            <!-- Meta: latency + tokens -->
            <div
              v-if="m.role === 'assistant' && (m.latencyMs != null || m.tokens)"
              class="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-slate-300/80"
            >
              <span
                class="rounded bg-indigo-500/30 px-1.5 py-0.5 font-semibold uppercase tracking-wide text-indigo-100"
              >neo4j_hybrid</span>
              <span v-if="m.latencyMs != null">{{ (m.latencyMs / 1000).toFixed(1) }} с</span>
              <span v-if="m.tokens">in={{ m.tokens.in }} out={{ m.tokens.out }}</span>
            </div>

            <!-- Retrieved nodes -->
            <details
              v-if="m.role === 'assistant' && m.retrievedNodes && m.retrievedNodes.length"
              class="mt-2 rounded-md border border-white/10 bg-black/30 text-[11px] text-slate-200"
            >
              <summary class="cursor-pointer select-none px-2 py-1.5 text-slate-300 hover:text-white">
                Что нашёл retriever ({{ m.retrievedNodes.length }})
              </summary>
              <div class="space-y-2 px-2 py-2">
                <div
                  v-for="(node, ni) in m.retrievedNodes"
                  :key="ni"
                  class="rounded-md border border-white/8 bg-white/5 px-2 py-1.5 text-[11px]"
                >
                  <div class="flex items-center gap-2">
                    <span class="rounded bg-indigo-500/40 px-1 py-0.5 text-[10px] font-semibold text-indigo-200">
                      {{ node.node_label }}
                    </span>
                    <span class="font-medium text-white">{{ node.title }}</span>
                    <span class="ml-auto shrink-0 text-slate-400">[{{ node.score.toFixed(3) }}]</span>
                  </div>
                  <div v-if="node.specialists?.length" class="mt-1 text-slate-300">
                    <span class="text-slate-500">specs: </span>{{ node.specialists.map(s => s.name).join(', ') }}
                  </div>
                  <div v-if="node.service_name" class="mt-0.5 text-slate-300">
                    <span class="text-slate-500">svc: </span>{{ node.service_name }}
                  </div>
                  <div v-if="node.objections?.length" class="mt-0.5 text-slate-400">
                    <span class="text-slate-500">obj: </span>{{ node.objections.join(', ') }}
                  </div>
                  <div v-if="node.tactics?.length" class="mt-0.5 text-slate-400">
                    <span class="text-slate-500">tac: </span>{{ node.tactics.join(', ') }}
                  </div>
                </div>
              </div>
            </details>

            <!-- SQNS Candidates -->
            <details
              v-if="m.role === 'assistant' && ((m.serviceCandidates?.length ?? 0) + (m.specialistCandidates?.length ?? 0) + (m.categoryCandidates?.length ?? 0) > 0)"
              class="mt-2 rounded-md border border-white/10 bg-black/30 text-[11px] text-slate-200"
            >
              <summary class="cursor-pointer select-none px-2 py-1.5 text-slate-300 hover:text-white">
                SQNS кандидаты ({{ (m.serviceCandidates?.length ?? 0) + (m.specialistCandidates?.length ?? 0) + (m.categoryCandidates?.length ?? 0) }})
              </summary>
              <div class="space-y-1 px-2 py-2">
                <div v-if="m.serviceCandidates?.length">
                  <p class="mb-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-400">Услуги</p>
                  <div
                    v-for="(c, ci) in m.serviceCandidates"
                    :key="`svc-${ci}`"
                    class="flex items-center gap-2 rounded bg-white/5 px-2 py-1"
                  >
                    <span class="font-medium text-white">{{ c.name }}</span>
                    <span class="text-slate-400">[{{ c.score.toFixed(3) }}]</span>
                    <span v-if="c.additional_info" class="ml-auto shrink-0 text-slate-400">{{ c.additional_info }}</span>
                  </div>
                </div>
                <div v-if="m.specialistCandidates?.length">
                  <p class="mb-1 mt-1.5 text-[10px] font-semibold uppercase tracking-wide text-sky-400">Специалисты</p>
                  <div
                    v-for="(c, ci) in m.specialistCandidates"
                    :key="`spec-${ci}`"
                    class="flex items-center gap-2 rounded bg-white/5 px-2 py-1"
                  >
                    <span class="font-medium text-white">{{ c.name }}</span>
                    <span class="text-slate-400">[{{ c.score.toFixed(3) }}]</span>
                    <span v-if="c.additional_info" class="ml-auto shrink-0 text-slate-400">{{ c.additional_info }}</span>
                  </div>
                </div>
                <div v-if="m.categoryCandidates?.length">
                  <p class="mb-1 mt-1.5 text-[10px] font-semibold uppercase tracking-wide text-violet-400">Категории</p>
                  <div
                    v-for="(c, ci) in m.categoryCandidates"
                    :key="`cat-${ci}`"
                    class="flex items-center gap-2 rounded bg-white/5 px-2 py-1"
                  >
                    <span class="font-medium text-white">{{ c.name }}</span>
                    <span class="text-slate-400">[{{ c.score.toFixed(3) }}]</span>
                  </div>
                </div>
              </div>
            </details>

            <!-- Prompts -->
            <details
              v-if="m.role === 'assistant' && (m.systemPrompt || m.userPrompt)"
              class="mt-2 rounded-md border border-white/10 bg-black/30 text-[11px] text-slate-200"
            >
              <summary class="cursor-pointer select-none px-2 py-1 text-slate-300 hover:text-white">
                Что отправили в LLM
              </summary>
              <div class="space-y-2 px-2 py-2">
                <div class="flex flex-wrap gap-1">
                  <button
                    v-for="(tab, ti) in promptTabsFor(m)"
                    :key="`${idx}-tab-${ti}`"
                    type="button"
                    class="rounded px-1.5 py-0.5 text-[10px]"
                    :class="(m.activeTab ?? 0) === ti ? 'bg-indigo-500 text-white' : 'bg-white/10 text-slate-200 hover:bg-white/20'"
                    @click="m.activeTab = ti"
                  >
                    {{ tab.label }}
                  </button>
                  <button
                    type="button"
                    class="ml-auto rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-300 hover:bg-white/15"
                    @click="copyText(promptTabsFor(m)[m.activeTab ?? 0]?.content ?? '')"
                  >
                    Копировать
                  </button>
                </div>
                <pre class="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded bg-black/40 p-2 text-[11px] leading-snug text-slate-100">{{ promptTabsFor(m)[m.activeTab ?? 0]?.content ?? '' }}</pre>
              </div>
            </details>
          </div>

          <div v-if="loading" class="max-w-[35%] rounded-xl bg-white/10 px-3 py-2">
            <div class="flex items-center gap-1.5">
              <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-white" />
              <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-white [animation-delay:120ms]" />
              <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-white [animation-delay:240ms]" />
            </div>
          </div>
        </div>

        <!-- Input -->
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
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { MessageCircle, PanelRightClose, PanelRightOpen, Send } from 'lucide-vue-next'
import { useApiFetch } from '~/composables/useApiFetch'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type { RetrievedNode, SqnsCandidate, UnifiedGraphAskResponse } from '../../../types/unifiedGraph'

const props = defineProps<{
  agentId: string
}>()

type ChatMessage = {
  role: 'assistant' | 'user'
  text: string
  latencyMs?: number | null
  tokens?: { in: number; out: number }
  retrievedNodes?: RetrievedNode[]
  serviceCandidates?: SqnsCandidate[]
  specialistCandidates?: SqnsCandidate[]
  categoryCandidates?: SqnsCandidate[]
  systemPrompt?: string | null
  userPrompt?: string | null
  activeTab?: number
}

const apiFetch = useApiFetch()
const open = ref(false)
const expanded = ref(false)
const loading = ref(false)
const question = ref('')
const messagesRef = ref<HTMLElement | null>(null)
const messages = ref<ChatMessage[]>([
  { role: 'assistant', text: 'Привет! Задайте вопрос — отвечу так же, как LLM-агент в живом диалоге.' },
])
const storageKey = (id: string) => `unified-graph-ask-chat-v4:${id}`
const expandedKey = (id: string) => `unified-graph-ask-expanded:${id}`

const promptTabsFor = (m: ChatMessage): Array<{ label: string; content: string }> => {
  const tabs: Array<{ label: string; content: string }> = []
  if (m.systemPrompt) tabs.push({ label: 'system', content: m.systemPrompt })
  if (m.userPrompt) tabs.push({ label: 'user', content: m.userPrompt })
  return tabs
}

const copyText = async (text: string) => {
  if (!text || !import.meta.client) return
  try {
    await navigator.clipboard.writeText(text)
  }
  catch {
    // ignore
  }
}

const toggleExpanded = () => {
  expanded.value = !expanded.value
  if (import.meta.client) {
    try {
      window.localStorage.setItem(expandedKey(props.agentId), expanded.value ? '1' : '0')
    }
    catch {
      // ignore
    }
  }
}

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
      body: { question: q },
    })
    messages.value.push({
      role: 'assistant',
      text: res.answer,
      latencyMs: res.latency_ms ?? null,
      tokens: res.tokens,
      retrievedNodes: res.retrieved_nodes ?? [],
      serviceCandidates: res.service_candidates ?? [],
      specialistCandidates: res.specialist_candidates ?? [],
      categoryCandidates: res.category_candidates ?? [],
      systemPrompt: res.system_prompt ?? null,
      userPrompt: res.user_prompt ?? null,
      activeTab: 0,
    })
  }
  catch (e: unknown) {
    messages.value.push({
      role: 'assistant',
      text: getReadableErrorMessage(e, 'Не удалось получить ответ по графу'),
    })
  }
  finally {
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
    sessionStorage.setItem(storageKey(props.agentId), JSON.stringify(value))
  },
  { deep: true },
)

onMounted(() => {
  if (import.meta.client) {
    const raw = sessionStorage.getItem(storageKey(props.agentId))
    if (raw) {
      try {
        const parsed = JSON.parse(raw)
        if (Array.isArray(parsed) && parsed.length) messages.value = parsed
      }
      catch {
        // ignore invalid storage data
      }
    }
    try {
      const savedExpanded = window.localStorage.getItem(expandedKey(props.agentId))
      if (savedExpanded === '1') expanded.value = true
    }
    catch {
      // ignore
    }
  }
  window.addEventListener('keydown', onGlobalKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
})
</script>
