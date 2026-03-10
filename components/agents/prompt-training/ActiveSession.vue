<template>
  <div class="flex flex-col h-full">
    <!-- Заголовок с кнопкой "Назад" -->
    <div class="flex items-center gap-3 px-6 py-3 border-b border-border shrink-0">
      <button
        @click="$emit('back')"
        class="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
      >
        <ArrowLeft class="w-4 h-4" />
      </button>
      <div class="flex items-center gap-2">
        <h2 class="text-sm font-semibold text-foreground">Активная тренировка</h2>
        <span class="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700">
          Активна
        </span>
      </div>
    </div>

    <!-- Desktop: два столбца / Mobile: табы -->
    <div class="flex-1 min-h-0">
      <!-- Desktop layout -->
      <div class="hidden md:grid md:grid-cols-2 md:gap-0 h-full">
        <div class="border-r border-border min-h-0">
          <TrainingChat
            :is-submitting-feedback="isSubmittingFeedback"
            @submit-feedback="$emit('submit-feedback', $event)"
          />
        </div>
        <div class="min-h-0">
          <CorrectionsPanel
            :feedbacks="feedbacks"
            @submit-feedback="$emit('submit-feedback', $event)"
          />
        </div>
      </div>

      <!-- Mobile layout -->
      <div class="md:hidden h-full flex flex-col">
        <Tabs v-model="mobileTab" class="flex flex-col h-full">
          <TabsList class="grid w-full grid-cols-2 shrink-0">
            <TabsTrigger value="chat">Чат</TabsTrigger>
            <TabsTrigger value="corrections">
              Коррекции
              <span v-if="feedbackCount > 0" class="ml-1 text-[10px] bg-primary text-primary-foreground rounded-full px-1.5">
                {{ feedbackCount }}
              </span>
            </TabsTrigger>
          </TabsList>
          <TabsContent value="chat" class="flex-1 min-h-0 mt-0">
            <TrainingChat
              :is-submitting-feedback="isSubmittingFeedback"
              @submit-feedback="$emit('submit-feedback', $event)"
            />
          </TabsContent>
          <TabsContent value="corrections" class="flex-1 min-h-0 mt-0">
            <CorrectionsPanel
              :feedbacks="feedbacks"
              @submit-feedback="$emit('submit-feedback', $event)"
            />
          </TabsContent>
        </Tabs>
      </div>
    </div>

    <!-- Sticky нижняя панель -->
    <div class="px-6 py-3 border-t border-border bg-background flex items-center justify-between shrink-0">
      <div class="flex items-center gap-3">
        <span class="text-sm text-muted-foreground">
          Собрано <strong class="text-foreground">{{ feedbackCount }}</strong>
          {{ pluralize(feedbackCount, 'коррекция', 'коррекции', 'коррекций') }}
        </span>
        <span v-if="session.meta_model" class="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
          {{ session.meta_model }}
        </span>
      </div>

      <div class="flex items-center gap-2">
        <Tooltip v-if="!canGenerate && feedbackCount === 0">
          <TooltipTrigger as-child>
            <span>
              <Button disabled>
                <Sparkles class="w-4 h-4 mr-2" />
                Сгенерировать промпт
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent>Добавьте хотя бы одну коррекцию</TooltipContent>
        </Tooltip>

        <Button
          v-else
          :disabled="!canGenerate"
          @click="handleGenerate"
        >
          <Loader2 v-if="isGenerating" class="w-4 h-4 mr-2 animate-spin" />
          <Sparkles v-else class="w-4 h-4 mr-2" />
          {{ isGenerating ? 'Мета-агент анализирует коррекции...' : 'Сгенерировать промпт' }}
        </Button>
      </div>
    </div>

    <!-- Модалка diff-предпросмотра -->
    <PromptDiffDialog
      :open="!!generatedPreview"
      :preview="generatedPreview"
      :is-applying="isApplying"
      @update:open="handleDiffDialogClose"
      @apply="(prompt?: string) => $emit('apply', prompt)"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ArrowLeft, Sparkles, Loader2 } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '~/components/ui/tabs'
import { Tooltip, TooltipTrigger, TooltipContent } from '~/components/ui/tooltip'
import TrainingChat from './TrainingChat.vue'
import CorrectionsPanel from './CorrectionsPanel.vue'
import PromptDiffDialog from './PromptDiffDialog.vue'
import type { TrainingFeedbackRead, TrainingSessionRead, GeneratedPromptPreview, CreateFeedbackPayload } from '~/types/promptTraining'

defineProps<{
  session: TrainingSessionRead
  feedbacks: readonly TrainingFeedbackRead[]
  feedbackCount: number
  canGenerate: boolean
  isGenerating: boolean
  isApplying: boolean
  isSubmittingFeedback: boolean
  generatedPreview: GeneratedPromptPreview | null
}>()

const emit = defineEmits<{
  'submit-feedback': [payload: CreateFeedbackPayload]
  generate: []
  apply: [prompt?: string]
  back: []
  'dismiss-preview': []
}>()

const mobileTab = ref('chat')

const handleGenerate = () => {
  emit('generate')
}

const handleDiffDialogClose = (open: boolean) => {
  if (!open) emit('dismiss-preview')
}

const pluralize = (n: number, one: string, few: string, many: string) => {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod100 >= 11 && mod100 <= 19) return many
  if (mod10 === 1) return one
  if (mod10 >= 2 && mod10 <= 4) return few
  return many
}
</script>
