<template>
  <div class="flex flex-col h-full">
    <!-- Заголовок -->
    <div class="flex items-center gap-3 px-6 py-3 border-b border-border shrink-0">
      <button
        @click="$emit('back')"
        class="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
      >
        <ArrowLeft class="w-4 h-4" />
      </button>
      <div class="flex items-center gap-2">
        <h2 class="text-sm font-semibold text-foreground">Сессия тренировки</h2>
        <span
          class="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
          :class="statusClasses[session.status]"
        >
          {{ SESSION_STATUS_LABELS[session.status] }}
        </span>
      </div>
      <span class="text-xs text-muted-foreground ml-auto">
        {{ formatDate(session.created_at) }}
      </span>
    </div>

    <!-- Содержимое -->
    <div class="flex-1 overflow-y-auto p-6 space-y-6">
      <!-- Информация о сессии -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="border border-border rounded-lg p-4">
          <p class="text-xs text-muted-foreground uppercase tracking-wider mb-1">Базовая версия</p>
          <p class="text-sm font-semibold text-foreground">
            {{ session.base_prompt_version ? `v${session.base_prompt_version}` : 'Не указана' }}
          </p>
        </div>
        <div class="border border-border rounded-lg p-4">
          <p class="text-xs text-muted-foreground uppercase tracking-wider mb-1">Коррекций</p>
          <p class="text-sm font-semibold text-foreground">{{ session.feedback_count }}</p>
        </div>
        <div class="border border-border rounded-lg p-4">
          <p class="text-xs text-muted-foreground uppercase tracking-wider mb-1">Мета-модель</p>
          <p class="text-sm font-semibold text-foreground">{{ session.meta_model }}</p>
        </div>
        <div class="border border-border rounded-lg p-4">
          <p class="text-xs text-muted-foreground uppercase tracking-wider mb-1">Модель агента</p>
          <p class="text-sm font-semibold text-foreground">{{ session.agent_model || 'Не указана' }}</p>
        </div>
      </div>

      <!-- Сгенерированный промпт (для completed) -->
      <div v-if="session.status === 'completed' && session.generated_prompt" class="space-y-4">
        <!-- Reasoning -->
        <div v-if="session.generated_prompt_reasoning" class="bg-muted/50 border border-border rounded-lg p-4">
          <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Обоснование изменений
          </p>
          <p class="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
            {{ session.generated_prompt_reasoning }}
          </p>
        </div>

        <!-- Промпт -->
        <div class="border border-border rounded-lg overflow-hidden">
          <div class="px-4 py-2 bg-emerald-50 border-b border-border flex items-center justify-between">
            <span class="text-xs font-semibold text-emerald-700">Сгенерированный промпт</span>
            <span v-if="session.generated_version_id" class="text-[10px] text-emerald-600">
              Применён как новая версия
            </span>
          </div>
          <div class="p-4 text-sm font-mono leading-relaxed whitespace-pre-wrap max-h-[400px] overflow-y-auto">
            {{ session.generated_prompt }}
          </div>
        </div>
      </div>

      <!-- Список коррекций (readonly) -->
      <div class="space-y-2">
        <h3 class="text-sm font-semibold text-foreground">Коррекции</h3>

        <div v-if="!feedbacks.length" class="text-sm text-muted-foreground py-4 text-center">
          Нет коррекций в этой сессии
        </div>

        <div
          v-for="feedback in feedbacks"
          :key="feedback.id"
          class="border border-border rounded-lg p-3 space-y-1.5"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-1.5">
              <component
                :is="feedbackIcon[feedback.feedback_type].icon"
                class="w-3.5 h-3.5"
                :class="feedbackIcon[feedback.feedback_type].class"
              />
              <span class="text-xs font-medium" :class="feedbackIcon[feedback.feedback_type].class">
                {{ FEEDBACK_TYPE_LABELS[feedback.feedback_type] }}
              </span>
            </div>
            <span class="text-[10px] text-muted-foreground">
              {{ formatTime(feedback.created_at) }}
            </span>
          </div>

          <p
            v-if="feedback.agent_response"
            class="text-[11px] text-muted-foreground/70 line-clamp-2 bg-slate-50 rounded px-2 py-1"
          >
            {{ truncate(feedback.agent_response, 100) }}
          </p>

          <p v-if="feedback.correction_text" class="text-sm text-foreground">
            {{ feedback.correction_text }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft, ThumbsUp, ThumbsDown, Pencil, Pin } from 'lucide-vue-next'
import {
  SESSION_STATUS_LABELS,
  FEEDBACK_TYPE_LABELS,
  type TrainingSessionRead,
  type TrainingFeedbackRead,
} from '~/types/promptTraining'

defineProps<{
  session: TrainingSessionRead
  feedbacks: readonly TrainingFeedbackRead[]
}>()

defineEmits<{
  back: []
}>()

const statusClasses: Record<string, string> = {
  active: 'bg-emerald-100 text-emerald-700',
  completed: 'bg-blue-100 text-blue-700',
  cancelled: 'bg-slate-100 text-slate-600',
}

const feedbackIcon: Record<string, { icon: any; class: string }> = {
  positive: { icon: ThumbsUp, class: 'text-emerald-600' },
  negative: { icon: ThumbsDown, class: 'text-red-500' },
  correction: { icon: Pencil, class: 'text-amber-600' },
  instruction: { icon: Pin, class: 'text-violet-600' },
}

const formatDate = (iso: string) => {
  const d = new Date(iso)
  return d.toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })
}

const formatTime = (iso: string) => {
  const d = new Date(iso)
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

const truncate = (text: string, max: number) =>
  text.length > max ? text.slice(0, max) + '...' : text
</script>
