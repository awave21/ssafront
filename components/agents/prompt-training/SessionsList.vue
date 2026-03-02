<template>
  <div class="flex flex-col gap-6 p-6">
    <!-- Заголовок -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-semibold text-foreground">Тренировочные сессии</h2>
        <p class="text-sm text-muted-foreground mt-1">
          Обучайте промпт агента через диалог и коррекции
        </p>
      </div>
      <Popover v-model:open="showCreatePopover">
        <PopoverTrigger as-child>
          <Button :disabled="isCreating || isLoadingModels">
            <Loader2 v-if="isCreating" class="w-4 h-4 mr-2 animate-spin" />
            <Plus v-else class="w-4 h-4 mr-2" />
            Новая тренировка
          </Button>
        </PopoverTrigger>
        <PopoverContent class="w-80" align="end">
          <div class="space-y-3">
            <div>
              <p class="text-sm font-medium text-foreground">Модель обучения</p>
              <p class="text-xs text-muted-foreground mt-0.5">Мета-модель для генерации промпта</p>
            </div>
            <Select v-model="selectedMetaModel">
              <SelectTrigger class="w-full">
                <SelectValue placeholder="По умолчанию (платформа)" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup v-for="group in modelGroups" :key="group.group">
                  <SelectLabel class="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                    {{ group.group }}
                  </SelectLabel>
                  <SelectItem
                    v-for="option in group.options"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <Button
              class="w-full"
              :disabled="isCreating"
              @click="handleCreate"
            >
              <Loader2 v-if="isCreating" class="w-4 h-4 mr-2 animate-spin" />
              Начать тренировку
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    </div>

    <!-- Загрузка -->
    <div v-if="isLoading" class="flex items-center justify-center py-16">
      <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
    </div>

    <!-- Пустое состояние -->
    <div v-else-if="!sessions.length" class="flex flex-col items-center justify-center py-16 text-center">
      <div class="w-16 h-16 bg-violet-50 rounded-full flex items-center justify-center mb-4">
        <GraduationCap class="w-8 h-8 text-violet-500" />
      </div>
      <h3 class="text-base font-semibold text-foreground mb-1">Нет тренировочных сессий</h3>
      <p class="text-sm text-muted-foreground max-w-sm mb-6">
        Начните тренировку, чтобы улучшить системный промпт агента через диалог и обратную связь
      </p>
      <Button :disabled="isCreating" @click="showCreatePopover = true">
        <Loader2 v-if="isCreating" class="w-4 h-4 mr-2 animate-spin" />
        <Plus v-else class="w-4 h-4 mr-2" />
        Начать тренировку
      </Button>
    </div>

    <!-- Список сессий -->
    <div v-else class="space-y-3">
      <div
        v-for="session in sessions"
        :key="session.id"
        class="border border-border rounded-lg p-4 hover:bg-muted/50 cursor-pointer transition-colors"
        @click="$emit('select', session.id)"
      >
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <span class="text-sm font-medium text-foreground">
              {{ formatDate(session.created_at) }}
            </span>
            <span
              class="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
              :class="statusClasses[session.status]"
            >
              {{ SESSION_STATUS_LABELS[session.status] }}
            </span>
          </div>
          <ChevronRight class="w-4 h-4 text-muted-foreground" />
        </div>

        <div class="flex items-center gap-4 text-xs text-muted-foreground">
          <span class="flex items-center gap-1">
            <MessageSquareText class="w-3.5 h-3.5" />
            {{ session.feedback_count }} {{ pluralize(session.feedback_count, 'коррекция', 'коррекции', 'коррекций') }}
          </span>
          <span v-if="session.base_prompt_version" class="flex items-center gap-1">
            <FileText class="w-3.5 h-3.5" />
            Базовая версия: v{{ session.base_prompt_version }}
          </span>
          <span v-if="session.generated_version_id" class="flex items-center gap-1 text-primary">
            <CheckCircle2 class="w-3.5 h-3.5" />
            Промпт применён
          </span>
        </div>
      </div>

      <!-- Загрузить ещё -->
      <div v-if="hasMore" class="flex justify-center pt-2">
        <Button variant="ghost" :disabled="isLoadingMore" @click="$emit('load-more')">
          <Loader2 v-if="isLoadingMore" class="w-4 h-4 mr-2 animate-spin" />
          Загрузить ещё
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  Loader2,
  Plus,
  ChevronRight,
  GraduationCap,
  MessageSquare as MessageSquareText,
  FileText,
  CheckCircle2,
} from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Popover, PopoverTrigger, PopoverContent } from '~/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '~/components/ui/select'
import { SelectGroup, SelectLabel } from 'radix-vue'
import { SESSION_STATUS_LABELS, type TrainingSessionRead } from '~/types/promptTraining'
import type { ActiveModelGroup } from '~/composables/useActiveModels'

defineProps<{
  sessions: readonly TrainingSessionRead[]
  isLoading: boolean
  isLoadingMore: boolean
  isCreating: boolean
  hasMore: boolean
  modelGroups: ActiveModelGroup[]
  isLoadingModels: boolean
}>()

const emit = defineEmits<{
  create: [metaModel?: string]
  select: [sessionId: string]
  'load-more': []
}>()

const showCreatePopover = ref(false)
const selectedMetaModel = ref('')

const handleCreate = () => {
  showCreatePopover.value = false
  emit('create', selectedMetaModel.value || undefined)
  selectedMetaModel.value = ''
}

const statusClasses: Record<string, string> = {
  active: 'bg-emerald-100 text-emerald-700',
  completed: 'bg-blue-100 text-blue-700',
  cancelled: 'bg-slate-100 text-slate-600',
}

const formatDate = (iso: string) => {
  const d = new Date(iso)
  return d.toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })
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
