<template>
  <div class="flex flex-col h-full border border-border rounded-md bg-background overflow-hidden">
    <!-- Заголовок -->
    <div class="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between shrink-0">
      <h3 class="font-bold text-slate-900">Коррекции</h3>
      <Button size="sm" variant="outline" @click="showAddRule = true">
        <Plus class="w-3.5 h-3.5 mr-1" />
        Добавить правило
      </Button>
    </div>

    <!-- Список коррекций -->
    <div class="flex-1 overflow-y-auto p-4 space-y-3">
      <!-- Пустое состояние -->
      <div v-if="!feedbacks.length" class="flex flex-col items-center justify-center h-full text-center py-8">
        <ClipboardList class="w-10 h-10 text-muted-foreground/40 mb-3" />
        <p class="text-sm text-muted-foreground">
          Пока нет коррекций
        </p>
        <p class="text-xs text-muted-foreground/60 mt-1">
          Оценивайте ответы агента или добавьте правило вручную
        </p>
      </div>

      <!-- Элементы -->
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

        <!-- Превью ответа агента -->
        <p
          v-if="feedback.agent_response"
          class="text-[11px] text-muted-foreground/70 line-clamp-2 bg-slate-50 rounded px-2 py-1"
        >
          {{ truncate(feedback.agent_response, 100) }}
        </p>

        <!-- Текст коррекции -->
        <p v-if="feedback.correction_text" class="text-sm text-foreground">
          {{ feedback.correction_text }}
        </p>
      </div>
    </div>

    <!-- Модалка "Добавить правило" -->
    <AddRuleDialog
      :open="showAddRule"
      @update:open="showAddRule = $event"
      @submit="handleAddRule"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Plus, ThumbsUp, ThumbsDown, Pencil, Pin, ClipboardList } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { FEEDBACK_TYPE_LABELS, type TrainingFeedbackRead, type CreateFeedbackPayload } from '~/types/promptTraining'
import AddRuleDialog from './AddRuleDialog.vue'

defineProps<{
  feedbacks: readonly TrainingFeedbackRead[]
}>()

const emit = defineEmits<{
  'submit-feedback': [payload: CreateFeedbackPayload]
}>()

const showAddRule = ref(false)

const feedbackIcon: Record<string, { icon: any; class: string }> = {
  positive: { icon: ThumbsUp, class: 'text-emerald-600' },
  negative: { icon: ThumbsDown, class: 'text-red-500' },
  correction: { icon: Pencil, class: 'text-amber-600' },
  instruction: { icon: Pin, class: 'text-violet-600' },
}

const formatTime = (iso: string) => {
  const d = new Date(iso)
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

const truncate = (text: string, max: number) =>
  text.length > max ? text.slice(0, max) + '...' : text

const handleAddRule = (ruleText: string) => {
  emit('submit-feedback', {
    feedback_type: 'instruction',
    correction_text: ruleText,
  })
  showAddRule.value = false
}
</script>
