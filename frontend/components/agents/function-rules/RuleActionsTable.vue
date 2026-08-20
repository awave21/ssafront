<template>
  <div class="min-w-0 space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold text-slate-900">Действия</span>
        <FieldHint
          title="Действия после срабатывания"
          text="Что именно платформа сделает, когда правило срабатывает: вызвать вебхук, уведомить администратора, передать диалог оператору, пометить диалог тегом. Выполняются по порядку, сверху вниз. «Промолчать» здесь искать не нужно — это вариант в поле «Реакция после выполнения» выше."
        />
        <span v-if="actions.length" class="text-xs font-medium text-slate-500">{{ actions.length }}</span>
      </div>
      <button
        v-if="canEdit"
        type="button"
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors hover:border-primary/40 hover:text-primary"
        @click="$emit('add')"
      >
        + Добавить действие
      </button>
    </div>

    <div v-if="actions.length === 0" class="rounded-xl border border-dashed border-slate-200 bg-white/60 py-6 text-center text-sm text-slate-400">
      Действия не добавлены. Нажмите «+ Добавить действие».
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="(action, idx) in actions"
        :key="action.id"
        class="flex items-center gap-3 rounded-xl bg-white p-3"
      >
        <span
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-[11px] font-bold text-primary"
        ><!-- Позиция в списке, а не order_index: у старых записей он мог быть
             одинаковым, и все действия показывались единицей. Порядок выполнения
             всё равно перенумеровывается по позиции при сохранении функции. -->
          {{ idx + 1 }}</span>

        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <span class="truncate text-sm font-semibold text-slate-900">{{ labelForActionType(action.action_type) }}</span>
            <span
              class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
              :class="action.enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'"
            >
              <span class="h-1.5 w-1.5 rounded-full" :class="action.enabled ? 'bg-emerald-500' : 'bg-slate-400'" />
              {{ action.enabled ? 'Активно' : 'Выключено' }}
            </span>
          </div>
          <div class="mt-0.5 text-xs text-slate-500">
            Когда: <span class="font-medium text-slate-700">{{ labelForOnStatus(action.on_status) }}</span>
          </div>
        </div>

        <div class="flex shrink-0 items-center gap-1">
          <button
            v-if="canEdit"
            type="button"
            class="flex h-8 w-8 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="idx === 0"
            title="Поднять выше"
            @click="$emit('move-up', action.id)"
          >
            <ChevronUp class="h-4 w-4" />
          </button>
          <button
            v-if="canEdit"
            type="button"
            class="flex h-8 w-8 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="idx === actions.length - 1"
            title="Опустить ниже"
            @click="$emit('move-down', action.id)"
          >
            <ChevronDown class="h-4 w-4" />
          </button>
          <button
            v-if="canEdit"
            type="button"
            class="flex h-8 w-8 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-primary/10 hover:text-primary"
            title="Редактировать"
            @click="$emit('edit', action.id)"
          >
            <Pencil class="h-4 w-4" />
          </button>
          <button
            v-if="canEdit"
            type="button"
            class="flex h-8 w-8 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600"
            title="Удалить"
            @click="$emit('remove', action.id)"
          >
            <Trash2 class="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ChevronUp, ChevronDown, Pencil, Trash2 } from 'lucide-vue-next'
import FieldHint from '~/components/agents/settings/FieldHint.vue'
import {
  functionRuleActionLabels,
  functionRuleActionStatusLabels,
  type FunctionRuleAction,
} from '~/types/ruleAction'

defineProps<{
  actions: FunctionRuleAction[]
  canEdit: boolean
}>()

defineEmits<{
  add: []
  edit: [id: string]
  remove: [id: string]
  'move-up': [id: string]
  'move-down': [id: string]
}>()

const labelForActionType = (raw: string) =>
  functionRuleActionLabels[raw as keyof typeof functionRuleActionLabels] || raw
const labelForOnStatus = (raw: string) =>
  functionRuleActionStatusLabels[raw as keyof typeof functionRuleActionStatusLabels] || raw
</script>
