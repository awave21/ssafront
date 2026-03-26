<template>
  <Transition name="widget-fab">
    <button
      v-if="!isOpen"
      type="button"
      class="fixed right-0 bottom-8 lg:bottom-10 z-[10002] inline-flex items-center justify-center rounded-l-2xl bg-indigo-600 px-3 py-5 text-white shadow-xl transition-all duration-200 hover:-translate-y-0.5 hover:bg-indigo-700"
      @click="isOpen = true"
      aria-label="Проверка векторного поиска"
      title="Проверка векторного поиска (RAG)"
    >
      <span class="flex items-center gap-2 [writing-mode:vertical-rl] rotate-180">
        <FileSearch class="h-5 w-5 shrink-0 animate-pulse" />
        <span class="text-sm lg:text-base font-bold tracking-wide">Векторный тест</span>
      </span>
    </button>
  </Transition>

  <Sheet :open="isOpen" @update:open="isOpen = $event">
    <SheetContent side="right" class-name="w-screen md:w-[50vw] md:max-w-none p-0 flex flex-col">
      <div class="flex h-full flex-col overflow-hidden bg-background">
        <div class="flex items-center justify-between border-b border-slate-100 bg-slate-50/50 px-6 py-4">
          <div class="flex flex-col gap-1">
            <h3 class="font-bold text-slate-900">Проверка векторного поиска</h3>
            <p class="max-w-md text-[10px] uppercase tracking-widest text-slate-500">
              Тот же путь, что <span class="font-mono normal-case tracking-normal">search_knowledge_files</span> — чанки из pgvector и ответ модели агента только по ним
            </p>
          </div>
          <button type="button" class="text-xs text-slate-500 transition-colors hover:text-slate-800" @click="clearHistory">
            Очистить историю
          </button>
        </div>

        <div ref="scrollRef" class="flex-1 space-y-6 overflow-y-auto scroll-smooth bg-slate-50/30 p-6">
          <div
            v-if="messages.length === 0"
            class="flex h-full flex-col items-center justify-center space-y-4 text-center"
          >
            <div class="flex h-16 w-16 items-center justify-center rounded-full bg-indigo-50">
              <FileSearch class="h-8 w-8 text-indigo-500" />
            </div>
            <div>
              <p class="font-medium text-slate-900">Задайте вопрос по загруженным файлам</p>
              <p class="mx-auto mt-1 max-w-[280px] text-sm text-slate-500">
                Увидите найденные чанки и ответ модели агента без полного чата и других инструментов
              </p>
            </div>
          </div>

          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            class="flex flex-col gap-2"
            :class="msg.role === 'user' ? 'items-end' : 'items-start'"
          >
            <div
              class="max-w-[85%] rounded-lg px-5 py-3 text-sm leading-relaxed"
              :class="
                msg.role === 'user'
                  ? 'rounded-tr-none bg-indigo-600 text-white'
                  : 'rounded-tl-none border border-slate-100 bg-white text-slate-800'
              "
            >
              <div v-if="msg.role === 'user'" class="whitespace-pre-wrap">{{ msg.content }}</div>
              <template v-else>
                <div v-if="msg.chunks?.length" class="mb-3 space-y-2">
                  <p class="text-[10px] font-bold uppercase tracking-wider text-slate-500">Найденные чанки</p>
                  <p class="text-[10px] text-slate-400">
                    Номер #N совпадает с «Фрагмент N» в контексте модели; указание источника в ответе может ошибаться — сверяйте с текстом чанка.
                  </p>
                  <details
                    v-for="(c, ci) in msg.chunks"
                    :key="`${c.chunk_id}-${ci}`"
                    class="rounded-lg border border-slate-100 bg-slate-50/80 text-left"
                  >
                    <summary class="cursor-pointer px-3 py-2 text-[11px] font-semibold text-slate-700">
                      #{{ c.fragment_index ?? ci + 1 }} · {{ c.title || 'Без названия' }}
                      <span v-if="c.chunk_index != null" class="ml-1 font-mono text-[10px] font-normal text-slate-500">
                        (чанк {{ c.chunk_index }})
                      </span>
                      <span class="ml-2 font-mono text-[10px] font-normal text-indigo-600">
                        rel {{ c.relevance.toFixed(3) }}
                      </span>
                    </summary>
                    <pre
                      class="max-h-40 overflow-auto whitespace-pre-wrap border-t border-slate-100 p-3 text-[11px] text-slate-600"
                    >{{ c.excerpt }}</pre>
                  </details>
                </div>
                <div
                  v-if="msg.answerError"
                  class="mb-2 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-xs text-rose-800"
                >
                  {{ msg.answerError }}
                </div>
                <div
                  v-if="msg.answer"
                  class="markdown-content border-t border-slate-100 pt-3"
                  v-html="renderMd(msg.answer)"
                />
                <div v-else-if="!msg.chunks?.length && !msg.answerError" class="text-xs text-slate-500">Нет ответа.</div>
              </template>
            </div>
            <span class="px-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              {{ msg.role === 'user' ? 'Вы' : 'Ответ' }}
            </span>
          </div>

          <div v-if="isLoading" class="flex justify-start">
            <div class="rounded-lg rounded-tl-none border border-slate-100 bg-white px-5 py-4 text-xs text-slate-500">
              Запрос…
            </div>
          </div>
        </div>

        <div class="border-t border-slate-100 bg-white p-4">
          <form class="relative flex items-end gap-3" @submit.prevent="submit">
            <textarea
              ref="inputRef"
              v-model="input"
              rows="1"
              :disabled="isLoading"
              placeholder="Например: какие условия доставки?"
              class="max-h-32 min-h-[44px] flex-1 resize-none rounded-md border border-slate-100 bg-slate-50 py-3 pl-5 pr-14 text-sm text-slate-900 placeholder:text-slate-400 transition-all focus:bg-white focus:ring-2 focus:ring-indigo-500"
              @input="autoResize"
              @keydown.enter.exact.prevent="submit"
            />
            <button
              type="submit"
              :disabled="isLoading || !input.trim()"
              class="absolute bottom-2 right-2 rounded-lg bg-indigo-600 p-2 text-white transition-all hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Отправить"
            >
              <Send class="h-5 w-5" />
            </button>
          </form>
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { FileSearch, Send } from 'lucide-vue-next'
import { Sheet, SheetContent } from '~/components/ui/sheet'
import { useApiFetch } from '~/composables/useApiFetch'
import { useToast } from '~/composables/useToast'
import { createSafeMarkdownRenderer } from '~/utils/safe-markdown'

type Chunk = {
  fragment_index?: number
  chunk_id: string
  file_id: string
  chunk_index: number | null
  title: string
  relevance: number
  excerpt: string
}

type RagMsg = {
  role: 'user' | 'assistant'
  content?: string
  chunks?: Chunk[]
  answer?: string | null
  answerError?: string | null
}

const props = defineProps<{
  agentId: string
}>()

const apiFetch = useApiFetch()
const { error: toastError } = useToast()
const isOpen = ref(false)
const input = ref('')
const inputRef = ref<HTMLTextAreaElement | null>(null)
const isLoading = ref(false)
const messages = ref<RagMsg[]>([])
const scrollRef = ref<HTMLElement | null>(null)

const md = createSafeMarkdownRenderer({
  linkify: true,
  breaks: false,
  typographer: true
})

const renderMd = (content: string) => md.render(content)

const autoResize = () => {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 128)}px`
}

const scrollBottom = async () => {
  await nextTick()
  const el = scrollRef.value
  if (el) el.scrollTop = el.scrollHeight
}

const clearHistory = async () => {
  messages.value = []
  input.value = ''
  if (inputRef.value) inputRef.value.style.height = 'auto'
  await scrollBottom()
}

const submit = async () => {
  const q = input.value.trim()
  if (!q || isLoading.value) return
  messages.value.push({ role: 'user', content: q })
  input.value = ''
  if (inputRef.value) inputRef.value.style.height = 'auto'
  isLoading.value = true
  await scrollBottom()
  try {
    const data = await apiFetch<{
      chunks: Chunk[]
      answer?: string | null
      answer_error?: string | null
    }>(`/agents/${props.agentId}/knowledge/files/vector-test`, {
      method: 'POST',
      body: { query: q, limit: 5 }
    })
    messages.value.push({
      role: 'assistant',
      chunks: Array.isArray(data?.chunks) ? data.chunks : [],
      answer: data?.answer ?? null,
      answerError: data?.answer_error ?? null
    })
  } catch (e: any) {
    const msg = e?.data?.detail ?? e?.message ?? 'Запрос не удался'
    toastError(typeof msg === 'string' ? msg : 'Ошибка проверки RAG')
    messages.value.push({
      role: 'assistant',
      chunks: [],
      answer: null,
      answerError: typeof msg === 'string' ? msg : 'Ошибка запроса'
    })
  } finally {
    isLoading.value = false
    await scrollBottom()
  }
}
</script>

<style scoped>
.markdown-content :deep(p) {
  margin-bottom: 0.5rem;
}
.markdown-content :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin-left: 1.25rem;
  margin-bottom: 0.5rem;
}
.markdown-content :deep(code) {
  background-color: #f1f5f9;
  padding: 0.15rem 0.35rem;
  border-radius: 0.25rem;
  font-size: 0.85em;
}

.widget-fab-enter-active,
.widget-fab-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.widget-fab-enter-from,
.widget-fab-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.96);
}
</style>
