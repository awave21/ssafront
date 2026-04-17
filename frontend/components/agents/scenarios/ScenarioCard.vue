<template>
  <div
    class="group relative cursor-pointer overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
    @click="$emit('click')"
  >
    <div
      class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-indigo-500/5 transition-transform duration-700 group-hover:scale-150"
    />
    <div class="flex items-center justify-between gap-4">
      <div class="flex items-center gap-4 min-w-0">
        <div class="h-11 w-11 flex-shrink-0 rounded-xl bg-indigo-50 flex items-center justify-center transition-colors group-hover:bg-indigo-100">
          <component :is="triggerIcon" class="w-5 h-5 text-indigo-600" />
        </div>
        <div class="min-w-0">
          <h4 class="font-bold text-slate-900 truncate">{{ scenario.name }}</h4>
          <p class="text-xs text-slate-500 mt-0.5 flex items-center gap-1.5">
            <span class="font-medium text-indigo-600/80">{{ triggerLabel }}</span>
            <span class="text-slate-300">•</span>
            <span class="truncate">{{ conditionLabel }}</span>
            <span class="text-slate-300">•</span>
            <span>{{ actionsCountLabel }}</span>
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3" @click.stop>
        <button
          @click="$emit('settings')"
          class="rounded-xl p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
          title="Настройки"
        >
          <Settings class="w-4 h-4" />
        </button>
        <button
          type="button"
          @click="$emit('delete')"
          class="rounded-xl p-2 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600"
          title="Удалить сценарий"
        >
          <Trash2 class="w-4 h-4" />
        </button>
        <Switch
          :model-value="scenario.enabled"
          @update:model-value="(val: boolean) => $emit('toggle', val)"
          :title="scenario.enabled ? 'Выключить' : 'Включить'"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { 
  MessageSquare, 
  Clock, 
  UserCheck, 
  UserMinus, 
  Zap, 
  AlertTriangle,
  Settings,
  Trash2,
  Play,
  ArrowRightCircle,
  LogOut,
  Repeat
} from 'lucide-vue-next'
import type { Scenario } from '~/types/scenario'
import { Switch } from '~/components/ui/switch'
import { pluralize } from '~/utils/pluralize'

const props = defineProps<{
  scenario: Scenario
}>()

const emit = defineEmits<{
  (e: 'click'): void
  (e: 'toggle', enabled: boolean): void
  (e: 'settings'): void
  (e: 'delete'): void
}>()

const triggerIcon = computed(() => {
  const icons: Record<string, any> = {
    client_message: MessageSquare,
    agent_message: ArrowRightCircle,
    manager_message: UserCheck,
    client_return: Repeat,
    dialog_start: Play,
    send_error: AlertTriangle,
    spend_limit: AlertTriangle,
    pre_run: Zap,
    post_run: LogOut,
    post_tool: Settings
  }
  return icons[props.scenario.trigger_mode] || Zap
})

const triggerLabel = computed(() => {
  const labels: Record<string, string> = {
    client_message: 'Сообщение клиента',
    agent_message: 'Сообщение агента',
    manager_message: 'Сообщение менеджера',
    client_return: 'Возврат клиента',
    dialog_start: 'Начало диалога',
    send_error: 'Ошибка отправки',
    spend_limit: 'Лимит трат',
    pre_run: 'Перед запуском',
    post_run: 'После завершения',
    post_tool: 'После инструмента'
  }
  return labels[props.scenario.trigger_mode] || props.scenario.trigger_mode
})

const conditionLabel = computed(() => {
  const labels: Record<string, string> = {
    keyword: 'Ключевые слова',
    regex: 'Регулярное выражение',
    semantic: 'Смысловое соответствие',
    always: 'Всегда',
    schedule_time: 'По времени',
    schedule_weekday: 'По дням недели',
    dialog_source: 'Источник диалога',
    start_param: 'Параметр запуска',
    after_scenario: 'После сценария',
    client_return_gap: 'Интервал возврата',
    json_context: 'Контекст JSON'
  }
  return labels[props.scenario.condition_type] || props.scenario.condition_type
})

const actionsCountLabel = computed(() =>
  pluralize(props.scenario.actions?.length || 0, ['действие', 'действия', 'действий'])
)
</script>
