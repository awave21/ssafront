<template>
  <div :class="expanded ? 'fixed inset-y-0 right-0 z-40 flex' : 'fixed bottom-6 right-20 z-40'">
    <div
      v-if="open"
      :class="[
        'overflow-hidden bg-gradient-to-br from-indigo-500/40 via-sky-500/30 to-fuchsia-500/40 p-[1px] shadow-2xl',
        expanded
          ? 'h-full w-[min(32rem,calc(100vw-1.5rem))] rounded-l-2xl'
          : 'absolute bottom-16 right-0 mb-3 h-[36rem] w-[min(28rem,calc(100vw-1.5rem))] rounded-2xl',
      ]"
    >
      <div
        :class="[
          'relative flex h-full flex-col border border-white/10 bg-slate-950/95 backdrop-blur-xl overflow-hidden',
          expanded ? 'rounded-l-2xl' : 'rounded-2xl',
        ]"
      >
        <div class="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_20%_20%,rgba(99,102,241,0.18),transparent_50%),radial-gradient(circle_at_80%_70%,rgba(236,72,153,0.12),transparent_45%)]" />

        <div class="relative z-10 border-b border-white/10 px-4 py-3 space-y-2">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-sm font-semibold text-white">Вопрос к графу</p>
              <p class="text-xs text-slate-300/80">Сравните режимы поиска Microsoft GraphRAG</p>
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
          <div class="flex flex-wrap items-center gap-1">
            <button
              v-for="m in methodOptions"
              :key="m.value"
              type="button"
              class="rounded-md px-2 py-1 text-[11px] font-medium transition-colors"
              :class="method === m.value
                ? 'bg-indigo-500 text-white shadow-sm'
                : 'border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10'"
              :title="m.hint"
              @click="setMethod(m.value)"
            >
              {{ m.label }}
            </button>
          </div>
          <div
            v-if="activeMethodDescription"
            class="rounded-md border border-indigo-400/20 bg-indigo-500/10 px-2.5 py-1.5 text-[11px] leading-snug text-slate-100"
          >
            <p class="font-semibold text-indigo-100">{{ activeMethodDescription.title }}</p>
            <p class="mt-0.5 text-slate-300">{{ activeMethodDescription.body }}</p>
            <p v-if="activeMethodDescription.bestFor" class="mt-0.5 text-slate-400">
              <span class="text-slate-500">Когда выбирать:</span> {{ activeMethodDescription.bestFor }}
            </p>
          </div>
        </div>

        <div ref="messagesRef" class="relative z-10 flex-1 space-y-3 overflow-y-auto px-4 py-3 text-sm">
          <div
            v-for="(m, idx) in messages"
            :key="`${idx}-${m.role}`"
            class="max-w-[92%] rounded-xl px-3 py-2 shadow-md"
            :class="m.role === 'assistant' ? 'bg-white/10 text-white' : 'ml-auto bg-white/80 text-slate-900 font-medium'"
          >
            <p class="whitespace-pre-wrap leading-relaxed">{{ m.text }}</p>
            <div
              v-if="m.role === 'assistant' && (m.method || m.usedNodes != null || m.latencyMs != null)"
              class="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-slate-300/80"
            >
              <span v-if="m.method" class="rounded bg-indigo-500/30 px-1.5 py-0.5 font-semibold uppercase tracking-wide text-indigo-100">
                {{ m.method }}
              </span>
              <span v-if="m.usedNodes != null && m.usedRelations != null">
                Контекст:
                {{ m.usedNodes }}{{ m.totalNodes ? ` из ${m.totalNodes}` : '' }} узлов
                · {{ m.usedRelations }}{{ m.totalRelations ? ` из ${m.totalRelations}` : '' }} связей
              </span>
              <span v-if="m.latencyMs != null">{{ (m.latencyMs / 1000).toFixed(1) }} с</span>
            </div>

            <details
              v-if="m.role === 'assistant' && hasPromptDetails(m)"
              class="mt-2 rounded-md border border-white/10 bg-black/30 text-[11px] text-slate-200"
            >
              <summary class="cursor-pointer select-none px-2 py-1 text-slate-300 hover:text-white">
                Показать промт ({{ promptTabsFor(m).length }})
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
import { MessageCircle, PanelRightClose, PanelRightOpen, Send } from 'lucide-vue-next'
import { useApiFetch } from '~/composables/useApiFetch'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type {
  GraphPromptTemplate,
  GraphSearchMethod,
  UnifiedGraphAskResponse,
} from '../../../types/unifiedGraph'

const props = defineProps<{
  agentId: string
}>()

type ChatMessage = {
  role: 'assistant' | 'user'
  text: string
  method?: GraphSearchMethod
  usedNodes?: number
  usedRelations?: number
  totalNodes?: number
  totalRelations?: number
  latencyMs?: number | null
  systemPrompt?: string | null
  userPrompt?: string | null
  command?: string | null
  stderrTail?: string | null
  promptTemplates?: GraphPromptTemplate[]
  activeTab?: number
}

const apiFetch = useApiFetch()
const open = ref(false)
const expanded = ref(false)
const loading = ref(false)
const question = ref('')
const messagesRef = ref<HTMLElement | null>(null)
const method = ref<GraphSearchMethod>('drift')
const messages = ref<ChatMessage[]>([
  { role: 'assistant', text: 'Привет! Выберите режим поиска и задайте вопрос — отвечу по данным графа.' },
])
const storageKey = computed(() => `unified-graph-ask-chat-v2:${props.agentId}`)
const methodKey = computed(() => `unified-graph-ask-method:${props.agentId}`)
const expandedKey = computed(() => `unified-graph-ask-expanded:${props.agentId}`)

type MethodOption = {
  value: GraphSearchMethod
  label: string
  hint: string
  title: string
  body: string
  bestFor: string
}

const methodOptions: MethodOption[] = [
  {
    value: 'naive',
    label: 'Naive',
    hint: 'Все доступные узлы превью + LLM. Без эмбеддингов, без ранжирования.',
    title: 'Naive — превью графа в LLM без ретривала',
    body: 'Сериализует все узлы и связи из preview-снимка (до лимита loader-а 800/2000) в JSON и кладёт в системный промпт целиком. Без эмбеддингов и без ранжирования по вопросу — как если бы вы сами скопировали кусок графа в чат.',
    bestFor: 'Быстрая отладка / визуальная проверка содержимого графа. Не для продакшна — модель видит весь срез, но не понимает, что важно для вопроса.',
  },
  {
    value: 'basic',
    label: 'Basic',
    hint: 'Векторный поиск по text_units (graphrag basic).',
    title: 'Basic — стандартный векторный RAG',
    body: 'Эмбеддинг-поиск по text_units (исходные чанки документов), без графовой структуры. Это baseline-RAG для сравнения с графовыми режимами.',
    bestFor: 'Простые фактологические вопросы, у которых ответ дословно лежит в одном чанке. Для сравнения качества с local/drift.',
  },
  {
    value: 'local',
    label: 'Local',
    hint: 'Entity-centric поиск: entities + relationships + text_units.',
    title: 'Local — entity-centric поиск по графу',
    body: 'Ищет по эмбеддингам сущностей, подтягивает связанные relationships, claims, text_units и community reports соседей. Контекст собирается с пропорциями (text_unit_prop / community_prop / top_k_entities).',
    bestFor: 'Вопросы про конкретную сущность — «кто проводит пилинг», «что входит в услугу X», «какие специалисты работают с Y».',
  },
  {
    value: 'global',
    label: 'Global',
    hint: 'Map-reduce по community reports. Дорого, для обзорных вопросов.',
    title: 'Global — map-reduce по community reports',
    body: 'Параллельно опрашивает все community reports иерархии Лейдена (map), затем сводит их в финальный ответ (reduce). Дорого по токенам и по времени (10–60 с).',
    bestFor: 'Обзорные/аналитические вопросы по всему корпусу — «какие основные направления клиники», «общий тон возражений пациентов».',
  },
  {
    value: 'drift',
    label: 'Drift',
    hint: 'Local + community context. Рекомендуемый дефолт.',
    title: 'Drift — Local, обогащённый community-инсайтами',
    body: 'Стартует как Local, но расширяет запрос инсайтами из community reports и итеративно генерирует follow-up подвопросы (Dynamic Reasoning and Inference with Flexible Traversal). Качество выше Local, стоимость ниже Global.',
    bestFor: 'Сложные вопросы, где нужны и сущности, и широкий контекст. Рекомендуемый дефолт после версии 0.4.',
  },
]

const activeMethodDescription = computed(() => methodOptions.find(o => o.value === method.value) ?? null)

const toggleExpanded = () => {
  expanded.value = !expanded.value
  if (import.meta.client) {
    try {
      window.localStorage.setItem(expandedKey.value, expanded.value ? '1' : '0')
    }
    catch {
      // ignore
    }
  }
}

const setMethod = (m: GraphSearchMethod) => {
  method.value = m
  if (import.meta.client) {
    try {
      window.localStorage.setItem(methodKey.value, m)
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

const hasPromptDetails = (m: ChatMessage): boolean => {
  if (m.systemPrompt || m.userPrompt || m.command || m.stderrTail) return true
  return Array.isArray(m.promptTemplates) && m.promptTemplates.length > 0
}

const promptTabsFor = (m: ChatMessage): Array<{ label: string; content: string }> => {
  const tabs: Array<{ label: string; content: string }> = []
  if (m.systemPrompt) tabs.push({ label: 'system', content: m.systemPrompt })
  if (m.userPrompt) tabs.push({ label: 'user', content: m.userPrompt })
  if (m.command) tabs.push({ label: 'command', content: m.command })
  for (const t of (m.promptTemplates ?? [])) {
    tabs.push({ label: t.name.replace('.txt', ''), content: t.content })
  }
  if (m.stderrTail) tabs.push({ label: 'stderr', content: m.stderrTail })
  return tabs
}

const copyText = async (text: string) => {
  if (!text || !import.meta.client) return
  try {
    await navigator.clipboard.writeText(text)
  }
  catch {
    // ignore — clipboard может быть недоступен
  }
}

const submit = async () => {
  if (!props.agentId || !question.value.trim()) return
  const q = question.value.trim()
  const m = method.value
  messages.value.push({ role: 'user', text: q, method: m })
  question.value = ''
  await scrollToBottom()
  loading.value = true
  try {
    const res = await apiFetch<UnifiedGraphAskResponse>(`/agents/${props.agentId}/unified-graph/ask`, {
      method: 'POST',
      body: { question: q, method: m },
    })
    messages.value.push({
      role: 'assistant',
      text: res.answer,
      method: res.method ?? m,
      usedNodes: res.used_nodes,
      usedRelations: res.used_relations,
      totalNodes: res.total_nodes,
      totalRelations: res.total_relations,
      latencyMs: res.latency_ms ?? null,
      systemPrompt: res.system_prompt ?? null,
      userPrompt: res.user_prompt ?? null,
      command: res.command ?? null,
      stderrTail: res.stderr_tail ?? null,
      promptTemplates: res.prompt_templates ?? [],
      activeTab: 0,
    })
  } catch (e: unknown) {
    messages.value.push({
      role: 'assistant',
      text: getReadableErrorMessage(e, 'Не удалось получить ответ по графу'),
      method: m,
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
    try {
      const savedMethod = window.localStorage.getItem(methodKey.value)
      if (savedMethod && methodOptions.some(o => o.value === savedMethod)) {
        method.value = savedMethod as GraphSearchMethod
      }
      const savedExpanded = window.localStorage.getItem(expandedKey.value)
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
