<template>
  <!-- Кнопка вызова: правый нижний угол. Вертикальные вкладки тестовых чатов
       подняты выше, чтобы не перекрываться с ней. -->
  <Transition name="assistant-fab">
    <button
      v-if="!isOpen"
      type="button"
      class="group fixed bottom-6 right-6 z-[10002] flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_12px_32px_-8px_rgba(59,130,246,0.6)] transition-all duration-300 hover:-translate-y-1 hover:bg-primary/90"
      aria-label="Помощник по настройке агента"
      title="Помощник по настройке агента"
      @click="open"
    >
      <span
        class="absolute inset-0 rounded-2xl bg-primary/30 opacity-0 transition-transform duration-700 group-hover:scale-125 group-hover:opacity-100"
      />
      <Sparkles class="relative h-6 w-6" />
    </button>
  </Transition>

  <Transition name="assistant-panel">
    <section
      v-if="isOpen"
      class="fixed inset-x-4 bottom-4 top-20 z-[10002] flex flex-col overflow-hidden rounded-3xl border border-slate-100 bg-white shadow-[0_24px_64px_-16px_rgba(0,0,0,0.18)] sm:inset-auto sm:bottom-6 sm:right-6 sm:top-auto sm:h-[min(40rem,calc(100vh-7rem))] sm:w-[26rem]"
      role="dialog"
      aria-label="Помощник по настройке агента"
    >
      <header class="flex items-center gap-3 border-b border-slate-100 px-4 py-3">
        <span
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-sky-400 text-white"
        >
          <Sparkles class="h-4 w-4" />
        </span>
        <div class="min-w-0 flex-1">
          <h3 class="truncate text-sm font-bold text-slate-900">Помощник</h3>
          <p class="truncate text-[11px] text-slate-500">Подскажет, что настроить дальше</p>
        </div>
        <button
          v-if="!isEmpty"
          type="button"
          class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
          aria-label="Очистить переписку"
          title="Очистить переписку"
          @click="clear"
        >
          <RotateCcw class="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
          aria-label="Закрыть помощника"
          @click="isOpen = false"
        >
          <X class="h-4 w-4" />
        </button>
      </header>

      <div ref="feedEl" class="flex-1 space-y-4 overflow-y-auto bg-slate-50/40 p-4">
        <div v-if="isEmpty" class="flex h-full flex-col items-center justify-center px-2 text-center">
          <span
            class="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary"
          >
            <Sparkles class="h-6 w-6" />
          </span>
          <p class="mt-4 text-sm font-semibold text-slate-900">Чем помочь с агентом?</p>
          <p class="mt-1 text-xs leading-relaxed text-slate-500">
            Расскажу, какие функции и сценарии подойдут под задачу и куда сохранять данные
          </p>
          <div class="mt-5 flex w-full flex-col gap-2">
            <button
              v-for="sample in samples"
              :key="sample"
              type="button"
              class="rounded-2xl border border-slate-100 bg-white px-3 py-2.5 text-left text-xs leading-relaxed text-slate-600 transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/30 hover:text-slate-900 hover:shadow-[0_12px_28px_-14px_rgba(0,0,0,0.14)]"
              @click="send(sample)"
            >
              {{ sample }}
            </button>
          </div>
        </div>

        <div v-for="message in messages" :key="message.id" class="flex flex-col gap-2">
          <div :class="['flex', message.role === 'user' ? 'justify-end' : 'justify-start']">
            <div
              :class="[
                'max-w-[85%] px-4 py-2.5 text-sm leading-relaxed',
                message.role === 'user'
                  ? 'rounded-2xl rounded-tr-md bg-primary text-white'
                  : message.failed
                    ? 'rounded-2xl rounded-tl-md border border-red-100 bg-red-50 text-red-700'
                    : 'markdown-content rounded-2xl rounded-tl-md border border-slate-100 bg-white text-slate-700 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]',
              ]"
            >
              <span v-if="message.role === 'user' || message.failed">{{ message.content }}</span>
              <span v-else v-html="renderMarkdown(message.content)" />
            </div>
          </div>

          <div v-if="message.suggestions?.length" class="flex flex-col gap-2">
            <button
              v-for="(suggestion, index) in message.suggestions"
              :key="`${message.id}-${index}`"
              type="button"
              class="group flex w-full items-start gap-3 rounded-2xl border border-slate-100 bg-white p-3 text-left transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_12px_28px_-12px_rgba(0,0,0,0.12)]"
              @click="goTo(suggestion)"
            >
              <span
                class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"
              >
                <component :is="suggestionIcon(suggestion.kind)" class="h-4 w-4" />
              </span>
              <span class="min-w-0 flex-1">
                <span class="block text-sm font-semibold text-slate-900">{{ suggestion.title }}</span>
                <span v-if="suggestion.rationale" class="mt-0.5 block text-xs leading-relaxed text-slate-500">
                  {{ suggestion.rationale }}
                </span>
              </span>
              <ArrowRight
                class="mt-1 h-4 w-4 shrink-0 text-slate-300 transition-all duration-300 group-hover:translate-x-0.5 group-hover:text-primary"
              />
            </button>
          </div>

          <div v-if="message.followups?.length" class="flex flex-wrap gap-1.5">
            <button
              v-for="(followup, index) in message.followups"
              :key="`${message.id}-f-${index}`"
              type="button"
              class="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] text-slate-600 transition-colors hover:border-primary/40 hover:text-primary"
              @click="send(followup)"
            >
              {{ followup }}
            </button>
          </div>
        </div>

        <div v-if="isThinking" class="flex justify-start">
          <span
            class="inline-flex items-center gap-1 rounded-2xl rounded-tl-md border border-slate-100 bg-white px-4 py-3"
          >
            <span class="assistant-dot" />
            <span class="assistant-dot" />
            <span class="assistant-dot" />
          </span>
        </div>
      </div>

      <footer class="border-t border-slate-100 p-3">
        <div
          class="flex items-end gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 transition-colors focus-within:border-primary/40"
        >
          <textarea
            v-model="draft"
            rows="1"
            :disabled="isThinking"
            placeholder="Спросите про функции, сценарии, таблицы…"
            aria-label="Сообщение помощнику"
            class="max-h-28 min-h-[1.5rem] flex-1 resize-none border-0 bg-transparent text-sm text-slate-800 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed"
            @keydown.enter.exact.prevent="send(draft)"
          />
          <button
            type="button"
            :disabled="!draft.trim() || isThinking"
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:bg-slate-100 disabled:text-slate-300"
            aria-label="Отправить"
            @click="send(draft)"
          >
            <Loader2 v-if="isThinking" class="h-4 w-4 animate-spin" />
            <Send v-else class="h-4 w-4" />
          </button>
        </div>
        <p class="mt-1.5 px-1 text-[10px] text-slate-400">
          Помощник советует, но ничего не создаёт и не меняет сам
        </p>
      </footer>
    </section>
  </Transition>
</template>

<script setup lang="ts">
import { nextTick, ref, watch, type Component } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight,
  BookOpen,
  FileText,
  Loader2,
  Radio,
  RotateCcw,
  Send,
  Sparkles,
  Table2,
  Wand2,
  Workflow,
  X,
} from 'lucide-vue-next'
import {
  suggestionRoute,
  useAgentAssistant,
  type AssistantSuggestion,
  type AssistantSuggestionKind,
} from '~/composables/useAgentAssistant'
import { createSafeMarkdownRenderer } from '~/utils/safe-markdown'

const props = defineProps<{ agentId: string }>()

const router = useRouter()
const markdown = createSafeMarkdownRenderer()

const { messages, isThinking, isEmpty, ask, clear } = useAgentAssistant(props.agentId)

const isOpen = ref(false)
const draft = ref('')
const feedEl = ref<HTMLElement | null>(null)

const samples = [
  'Как сохранять заявки клиентов?',
  'Что сделать, чтобы ночью отвечал автоответ?',
  'Чем функция отличается от сценария?',
]

const suggestionIcons: Record<AssistantSuggestionKind, Component> = {
  function: Wand2,
  scenario: Workflow,
  table: Table2,
  knowledge: BookOpen,
  prompt: FileText,
  channel: Radio,
}

const suggestionIcon = (kind: AssistantSuggestionKind) => suggestionIcons[kind] || Sparkles

const renderMarkdown = (text: string) => markdown.render(text || '')

const scrollToBottom = async () => {
  await nextTick()
  const el = feedEl.value
  if (el) el.scrollTop = el.scrollHeight
}

const open = () => {
  isOpen.value = true
  scrollToBottom()
}

const send = (text: string) => {
  const question = (text || '').trim()
  if (!question) return
  draft.value = ''
  ask(question)
}

const goTo = (suggestion: AssistantSuggestion) => {
  isOpen.value = false
  router.push(suggestionRoute(props.agentId, suggestion))
}

watch([() => messages.value.length, isThinking], scrollToBottom)
</script>

<style scoped>
.assistant-fab-enter-active,
.assistant-fab-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.assistant-fab-enter-from,
.assistant-fab-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.9);
}

.assistant-panel-enter-active,
.assistant-panel-leave-active {
  transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1),
    transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.assistant-panel-enter-from,
.assistant-panel-leave-to {
  opacity: 0;
  transform: translateY(16px) scale(0.98);
}

.assistant-dot:nth-child(2) {
  animation-delay: 0.15s;
}

.assistant-dot:nth-child(3) {
  animation-delay: 0.3s;
}

.assistant-dot {
  height: 0.375rem;
  width: 0.375rem;
  border-radius: 9999px;
  background-color: rgb(148 163 184);
  animation: assistant-dot 0.9s ease-in-out infinite;
}

@keyframes assistant-dot {
  0%,
  100% {
    opacity: 0.35;
    transform: translateY(0);
  }
  50% {
    opacity: 1;
    transform: translateY(-3px);
  }
}
</style>
