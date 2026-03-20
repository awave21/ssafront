<template>
  <div class="flex flex-col h-full bg-background rounded-md border border-border overflow-hidden">
    <!-- Заголовок -->
    <div class="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between shrink-0">
      <div class="flex flex-col gap-1">
        <div class="flex items-center gap-3">
          <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          <h3 class="font-bold text-slate-900">Тренировочный чат</h3>
        </div>
        <p v-if="chatContextLabel" class="text-[10px] text-slate-500 uppercase tracking-widest">
          {{ chatContextLabel }}
        </p>
      </div>
      <button
        @click="handleClearChat"
        class="text-xs text-slate-500 hover:text-slate-800 transition-colors"
      >
        Очистить историю
      </button>
    </div>

    <!-- Сообщения -->
    <div
      ref="messagesContainer"
      class="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth bg-slate-50/30"
    >
      <!-- Пустое состояние -->
      <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-center space-y-4">
        <div class="w-16 h-16 bg-indigo-50 rounded-full flex items-center justify-center">
          <MessageSquare class="w-8 h-8 text-indigo-500" />
        </div>
        <div>
          <p class="font-medium text-slate-900">Начните диалог</p>
          <p class="text-sm text-slate-500 max-w-[280px] mx-auto mt-1">
            Отправьте сообщение агенту, оцените его ответы и добавьте коррекции для улучшения промпта
          </p>
        </div>
      </div>

      <!-- Список сообщений -->
      <div
        v-for="(msg, index) in messages"
        :key="index"
        class="flex flex-col"
        :class="[msg.role === 'user' ? 'items-end' : 'items-start']"
      >
        <!-- Пузырёк сообщения -->
        <div
          class="max-w-[80%] rounded-lg px-5 py-3 text-sm leading-relaxed markdown-content"
          :class="[
            msg.role === 'user'
              ? 'bg-indigo-600 text-white rounded-tr-none'
              : 'bg-white border border-slate-100 text-slate-800 rounded-tl-none'
          ]"
        >
          <div v-if="msg.role === 'user'" class="whitespace-pre-wrap">{{ msg.content }}</div>
          <div v-else v-html="renderAgentContent(msg.content)" />
        </div>

        <!-- Метаинформация -->
        <div class="flex flex-col gap-1.5 mt-1.5">
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-slate-400 px-1 uppercase font-semibold tracking-wider">
              {{ msg.role === 'user' ? 'Вы' : agentName }}
            </span>
          </div>

          <div
            v-if="msg.role === 'agent' && isDirectQuestionMeta(msg.orchestration_meta?.source)"
            class="inline-flex max-w-[80%] w-fit items-center gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] text-amber-900"
          >
            <span>Сработал прямой вопрос: {{ msg.orchestration_meta?.title || msg.orchestration_meta?.search_title || 'без названия' }}</span>
            <span v-if="msg.orchestration_meta?.score != null" class="font-mono text-amber-700">
              (score: {{ formatScore(msg.orchestration_meta.score) }})
            </span>
          </div>

          <!-- Токены -->
          <div
            v-if="msg.role === 'agent' && msg.tokens && (msg.tokens.prompt != null || msg.tokens.completion != null || msg.tokens.total != null)"
            class="flex flex-wrap gap-1.5 text-[10px]"
          >
            <span v-if="msg.tokens.prompt != null" class="text-slate-500 px-2 py-0.5 bg-slate-50 rounded-md border border-slate-200">
              Промпт: <span class="font-mono font-semibold">{{ msg.tokens.prompt }}</span>
            </span>
            <span v-if="msg.tokens.completion != null" class="text-slate-500 px-2 py-0.5 bg-slate-50 rounded-md border border-slate-200">
              Ответ: <span class="font-mono font-semibold">{{ msg.tokens.completion }}</span>
            </span>
            <span v-if="msg.tokens.total != null" class="text-slate-500 px-2 py-0.5 bg-slate-50 rounded-md border border-slate-200">
              Всего: <span class="font-mono font-semibold">{{ msg.tokens.total }}</span>
            </span>
          </div>

          <!-- Кнопки фидбека для ответов агента -->
          <div
            v-if="msg.role === 'agent'"
            class="flex items-center gap-2 mt-1 group/feedback"
          >
            <!-- Уже оценён положительно -->
            <div v-if="messageFeedback[index] === 'positive'" class="flex items-center gap-1 text-emerald-600 text-xs">
              <ThumbsUp class="w-3.5 h-3.5 fill-emerald-600" />
              <span>Одобрено</span>
            </div>

            <!-- Уже оценён отрицательно -->
            <div v-else-if="messageFeedback[index] === 'negative'" class="flex items-center gap-1 text-red-500 text-xs">
              <ThumbsDown class="w-3.5 h-3.5 fill-red-500" />
              <span>Коррекция добавлена</span>
            </div>

            <!-- Кнопки оценки -->
            <template v-else>
              <button
                @click="handlePositiveFeedback(index, msg)"
                :disabled="isSubmittingFeedback"
                class="p-1.5 rounded-md text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 transition-colors opacity-0 group-hover/feedback:opacity-100 md:opacity-0 max-md:opacity-100"
              >
                <ThumbsUp class="w-3.5 h-3.5" />
              </button>
              <button
                @click="openCorrectionInput(index)"
                :disabled="isSubmittingFeedback"
                class="p-1.5 rounded-md text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors opacity-0 group-hover/feedback:opacity-100 md:opacity-0 max-md:opacity-100"
              >
                <ThumbsDown class="w-3.5 h-3.5" />
              </button>
            </template>
          </div>

          <!-- Поле ввода коррекции -->
          <div
            v-if="msg.role === 'agent' && correctionInputIndex === index"
            class="mt-2 max-w-[80%] space-y-2"
          >
            <textarea
              v-model="correctionText"
              placeholder="Опишите, что было не так и как должен отвечать агент..."
              rows="3"
              class="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:ring-2 focus:ring-red-200 focus:border-red-300 resize-none"
            />
            <div class="flex items-center gap-2">
              <Button
                size="sm"
                variant="destructive"
                :disabled="!correctionText.trim() || isSubmittingFeedback"
                @click="handleNegativeFeedback(index, msg)"
              >
                <Loader2 v-if="isSubmittingFeedback" class="w-3.5 h-3.5 mr-1 animate-spin" />
                Отправить коррекцию
              </Button>
              <Button size="sm" variant="ghost" @click="closeCorrectionInput">
                Отмена
              </Button>
            </div>
          </div>
        </div>
      </div>

      <!-- Индикатор набора -->
      <div v-if="isTyping" class="flex flex-col items-start">
        <div class="bg-white border border-slate-100 rounded-lg rounded-tl-none px-5 py-4">
          <div class="flex gap-1.5">
            <div class="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style="animation-delay: 0ms" />
            <div class="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style="animation-delay: 150ms" />
            <div class="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style="animation-delay: 300ms" />
          </div>
        </div>
      </div>
    </div>

    <!-- Ввод сообщения -->
    <div class="p-4 bg-white border-t border-slate-100 shrink-0">
      <form @submit.prevent="handleSendMessage" class="relative flex items-center gap-3">
        <textarea
          ref="inputArea"
          v-model="userInput"
          @input="autoResize"
          @keydown.enter.exact.prevent="handleSendMessage"
          placeholder="Напишите сообщение..."
          rows="1"
          class="flex-1 bg-slate-50 border border-slate-100 rounded-md px-5 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all resize-none max-h-32"
        />
        <button
          type="submit"
          :disabled="!userInput.trim() || isTyping"
          class="absolute right-2 p-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          <Send class="w-5 h-5" />
        </button>
      </form>
      <p class="text-[10px] text-center text-slate-400 mt-3 uppercase font-medium tracking-widest">
        Режим тренировки — оценивайте ответы агента
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, reactive, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { MessageSquare, Send, ThumbsUp, ThumbsDown, Loader2 } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { createSafeMarkdownRenderer } from '~/utils/safe-markdown'
import type { CreateFeedbackPayload } from '~/types/promptTraining'

const props = defineProps<{
  isSubmittingFeedback: boolean
}>()

const emit = defineEmits<{
  'submit-feedback': [payload: CreateFeedbackPayload]
}>()

const md = createSafeMarkdownRenderer({ linkify: true, breaks: false, typographer: true })

const renderAgentContent = (content: unknown) => {
  if (typeof content !== 'string') return ''
  return md.render(content)
}

const formatScore = (score: unknown) => {
  const numericScore = typeof score === 'number' ? score : Number(score)
  if (!Number.isFinite(numericScore)) return String(score ?? '')
  return numericScore.toFixed(3).replace(/\.?0+$/, '')
}

const isDirectQuestionMeta = (source: unknown) => {
  return source === 'direct_question_match' || source === 'direct_question_tool_call'
}

const store = useAgentEditorStore()
const { messages, userInput, isTyping, chatContextLabel, agent } = storeToRefs(store)
const agentName = ref('Агент')

watch(agent, (v) => { if (v) agentName.value = v.name || 'Агент' }, { immediate: true })

const messagesContainer = ref<HTMLElement | null>(null)
const inputArea = ref<HTMLTextAreaElement | null>(null)

const messageFeedback = reactive<Record<number, 'positive' | 'negative'>>({})
const correctionInputIndex = ref<number | null>(null)
const correctionText = ref('')

const autoResize = () => {
  if (inputArea.value) {
    inputArea.value.style.height = 'auto'
    inputArea.value.style.height = inputArea.value.scrollHeight + 'px'
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const handleSendMessage = async () => {
  if (!userInput.value.trim() || isTyping.value) return
  const sent = await store.sendMessage()
  if (sent && inputArea.value) {
    inputArea.value.style.height = 'auto'
  }
  await scrollToBottom()
}

const handleClearChat = async () => {
  await store.clearChat()
  Object.keys(messageFeedback).forEach(k => delete messageFeedback[Number(k)])
  correctionInputIndex.value = null
  correctionText.value = ''
  await scrollToBottom()
}

const handlePositiveFeedback = (index: number, msg: any) => {
  messageFeedback[index] = 'positive'
  emit('submit-feedback', {
    feedback_type: 'positive',
    run_id: msg.run_id ?? null,
    agent_response: msg.content,
    correction_text: '',
  })
}

const openCorrectionInput = (index: number) => {
  correctionInputIndex.value = index
  correctionText.value = ''
}

const closeCorrectionInput = () => {
  correctionInputIndex.value = null
  correctionText.value = ''
}

const handleNegativeFeedback = (index: number, msg: any) => {
  if (!correctionText.value.trim()) return
  messageFeedback[index] = 'negative'
  emit('submit-feedback', {
    feedback_type: 'negative',
    run_id: msg.run_id ?? null,
    agent_response: msg.content,
    correction_text: correctionText.value.trim(),
  })
  closeCorrectionInput()
}

watch(agent, (value) => {
  if (value) {
    store.ensureChatLoaded()
    scrollToBottom()
  }
}, { immediate: true })

onMounted(() => {
  store.ensureChatLoaded()
})
</script>

<style scoped>
.markdown-content :deep(p) { margin-bottom: 0.5rem; }
.markdown-content :deep(p:last-child) { margin-bottom: 0; }
.markdown-content :deep(ul), .markdown-content :deep(ol) { margin-left: 1.25rem; margin-bottom: 0.5rem; }
.markdown-content :deep(ul) { list-style-type: disc; }
.markdown-content :deep(ol) { list-style-type: decimal; }
.markdown-content :deep(code) { background-color: #f1f5f9; padding: 0.2rem 0.4rem; border-radius: 0.25rem; font-family: monospace; }
.markdown-content :deep(pre) { background-color: #f1f5f9; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; margin-bottom: 0.5rem; }
.markdown-content :deep(pre code) { background-color: transparent; padding: 0; }
</style>
