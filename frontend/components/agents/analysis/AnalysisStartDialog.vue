<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="sm:max-w-[400px]">
      <DialogHeader>
        <DialogTitle>Запуск анализа</DialogTitle>
        <DialogDescription>
          Выберите период диалогов для анализа переписки
        </DialogDescription>
      </DialogHeader>

      <div class="grid gap-4 py-3">
        <!-- Период -->
        <div class="space-y-2">
          <label class="text-sm font-medium">Период анализа</label>
          <div class="flex gap-2">
            <Button
              v-for="preset in PERIOD_PRESETS"
              :key="preset.value"
              :variant="form.window_hours === preset.value ? 'default' : 'secondary'"
              size="sm"
              class="flex-1"
              @click="form.window_hours = preset.value"
            >
              {{ preset.label }}
            </Button>
          </div>
        </div>

        <!-- Только с менеджером -->
        <div class="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2">
          <span class="text-sm">Только с вмешательством менеджера</span>
          <Switch v-model="form.only_with_manager" />
        </div>

        <!-- Расширенные настройки -->
        <Button
          variant="link"
          size="sm"
          class="h-auto w-fit p-0"
          @click="isAdvancedOpen = !isAdvancedOpen"
        >
          {{ isAdvancedOpen ? 'Скрыть расширенные настройки' : 'Расширенные настройки' }}
        </Button>

        <div v-if="isAdvancedOpen" class="grid gap-3 border-t border-border pt-3">
          <div class="grid grid-cols-2 gap-2">
            <div class="space-y-1">
              <label class="text-[10px] uppercase text-muted-foreground">Макс. диалогов</label>
              <Input v-model="form.max_dialogs" type="number" min="1" placeholder="100" />
            </div>
            <div class="space-y-1">
              <label class="text-[10px] uppercase text-muted-foreground">Глубина истории</label>
              <Input v-model="form.history_limit" type="number" min="1" placeholder="10" />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div class="space-y-1">
              <label class="text-[10px] uppercase text-muted-foreground">Лимит токенов</label>
              <Input v-model="form.max_tokens_per_job" type="number" min="1" placeholder="50000" />
            </div>
            <div class="space-y-1">
              <label class="text-[10px] uppercase text-muted-foreground">Лимит LLM-запросов</label>
              <Input v-model="form.max_llm_requests_per_job" type="number" min="1" placeholder="500" />
            </div>
          </div>
          <div class="space-y-1">
            <label class="text-[10px] uppercase text-muted-foreground">Мета-модель</label>
            <Input v-model="form.meta_model" type="text" placeholder="gpt-4o" />
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button class="w-full" :disabled="isStarting" @click="handleStart">
          <Loader2 v-if="isStarting" class="mr-2 h-4 w-4 animate-spin" />
          <Play v-else class="mr-2 h-4 w-4" />
          Начать анализ
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { Loader2, Play } from 'lucide-vue-next'
import Button from '~/components/ui/button/Button.vue'
import Input from '~/components/ui/input/Input.vue'
import Switch from '~/components/ui/switch/Switch.vue'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '~/components/ui/dialog'
import type { AnalysisStartPayload, AnalysisWindowHours } from '~/types/agent-analysis'

defineProps<{
  open: boolean
  isStarting: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  start: [payload: Omit<AnalysisStartPayload, 'idempotency_key'>]
}>()

const PERIOD_PRESETS: Array<{ value: AnalysisWindowHours; label: string }> = [
  { value: 24, label: 'Сутки' },
  { value: 72, label: '3 дня' },
  { value: 168, label: 'Неделя' },
]

const isAdvancedOpen = ref(false)

const form = reactive({
  window_hours: 72 as AnalysisWindowHours,
  only_with_manager: false,
  max_dialogs: '',
  history_limit: '',
  max_tokens_per_job: '',
  max_llm_requests_per_job: '',
  meta_model: '',
})

const toOptionalNumber = (value: string): number | undefined => {
  const trimmed = value.trim()
  if (!trimmed) return undefined
  const parsed = Number(trimmed)
  if (!Number.isFinite(parsed) || parsed <= 0) return undefined
  return Math.floor(parsed)
}

const handleStart = () => {
  emit('start', {
    window_hours: form.window_hours,
    only_with_manager: form.only_with_manager,
    max_dialogs: toOptionalNumber(form.max_dialogs),
    history_limit: toOptionalNumber(form.history_limit),
    max_tokens_per_job: toOptionalNumber(form.max_tokens_per_job),
    max_llm_requests_per_job: toOptionalNumber(form.max_llm_requests_per_job),
    meta_model: form.meta_model.trim() || undefined,
  })
}
</script>
