<template>
  <div
    class="group relative min-w-0 max-w-full cursor-pointer overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-shadow duration-500 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
    @click="$emit('click')"
  >
    <!-- Только фон масштабируется; без translate у карточки — клик по корзине не промахивается -->
    <div
      class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-indigo-500/5 transition-transform duration-700 group-hover:scale-150"
    />
    <div class="flex items-center justify-between gap-4">
      <div class="flex items-center gap-2 min-w-0 flex-1 sm:gap-4">
        <button
          v-if="reorderable"
          type="button"
          class="direct-question-drag-handle shrink-0 cursor-grab touch-none rounded-xl p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 active:cursor-grabbing"
          aria-label="Перетащить вопрос"
          title="Перетащить"
          @click.stop
        >
          <GripVertical class="h-5 w-5" />
        </button>
        <div class="h-11 w-11 flex-shrink-0 rounded-xl bg-indigo-50 flex items-center justify-center transition-colors group-hover:bg-indigo-100">
          <MessageSquare class="w-5 h-5 text-indigo-600" />
        </div>
        <div class="min-w-0 flex-1">
          <h4 class="font-bold text-slate-900 truncate">{{ question.title }}</h4>
          <p class="text-xs text-slate-600 mt-0.5 line-clamp-1 break-all">
            {{ question.content }}
          </p>
          <div v-if="question.tags.length > 0" class="mt-1 flex flex-wrap gap-1 min-w-0">
            <span
              v-for="tag in question.tags"
              :key="tag"
              class="max-w-full truncate rounded-full border border-indigo-100 bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700"
            >
              #{{ tag }}
            </span>
          </div>
        </div>
      </div>

      <div class="relative z-20 flex items-center gap-3 shrink-0" @click.stop>
        <!-- Indicators -->
        <div class="flex items-center gap-1.5 mr-2">
          <TooltipProvider :delay-duration="300">
            <Tooltip>
              <TooltipTrigger as-child>
                <div 
                  class="p-1.5 rounded-full transition-colors"
                  :class="question.interrupt_dialog ? 'bg-red-50 text-red-500' : 'text-slate-300'"
                >
                  <Octagon class="w-4 h-4" />
                </div>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                <p class="text-xs">{{ question.interrupt_dialog ? 'Прерывает диалог' : 'Не прерывает диалог' }}</p>
              </TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger as-child>
                <div 
                  class="p-1.5 rounded-full transition-colors"
                  :class="question.notify_telegram ? 'bg-green-50 text-green-500' : 'text-slate-300'"
                >
                  <Bell class="w-4 h-4" />
                </div>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                <p class="text-xs">{{ question.notify_telegram ? 'Уведомляет в Telegram' : 'Без уведомлений' }}</p>
              </TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger as-child>
                <div
                  class="p-1.5 rounded-full transition-colors"
                  :class="question.followup?.enabled ? 'bg-indigo-50 text-indigo-500' : 'text-slate-300'"
                >
                  <Clock3 class="w-4 h-4" />
                </div>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                <p class="text-xs">
                  {{ question.followup?.enabled ? `Фоллоу-ап включен (${question.followup?.delay_minutes ?? 60} мин)` : 'Фоллоу-ап выключен' }}
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        <Switch
          :model-value="question.is_enabled"
          @update:model-value="(val: boolean) => $emit('toggle', val)"
          :title="question.is_enabled ? 'Выключить' : 'Включить'"
        />
        
        <button
          type="button"
          class="rounded-xl p-2 text-slate-400 opacity-0 transition-opacity duration-150 hover:bg-rose-50 hover:text-rose-600 group-hover:opacity-100 group-focus-within:opacity-100 max-sm:opacity-100"
          title="Удалить"
          @click.stop="$emit('delete')"
        >
          <Trash2 class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Bell, Clock3, GripVertical, MessageSquare, Octagon, Trash2 } from 'lucide-vue-next'
import type { DirectQuestion } from '~/types/knowledge'
import { Switch } from '~/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '~/components/ui/tooltip'

withDefaults(
  defineProps<{
    question: DirectQuestion
    /** Показать ручку drag-n-drop (только когда список в режиме сортировки) */
    reorderable?: boolean
  }>(),
  { reorderable: false }
)

defineEmits<{
  (e: 'click'): void
  (e: 'toggle', enabled: boolean): void
  (e: 'delete'): void
}>()
</script>
