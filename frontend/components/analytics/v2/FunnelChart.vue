<template>
  <div class="rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
    <div class="mb-5 flex items-center justify-between">
      <div>
        <h3 class="text-sm font-bold uppercase tracking-widest text-slate-400">Воронка пациента</h3>
        <p class="mt-1 text-xs text-slate-500">Сквозная конверсия от первого сообщения до повторной записи</p>
      </div>
    </div>

    <div v-if="!stages.length" class="py-10 text-center text-sm text-slate-400">Нет данных</div>

    <div v-else class="space-y-3">
      <div v-for="(stage, idx) in stages" :key="stage.key" class="space-y-1">
        <div class="flex items-baseline justify-between text-xs">
          <span class="font-bold text-slate-700">{{ stage.label }}</span>
          <div class="flex items-center gap-3 tabular-nums">
            <span class="text-sm font-black text-slate-900">{{ stage.value.toLocaleString('ru-RU') }}</span>
            <span v-if="idx > 0" class="text-[11px] font-medium text-slate-400">
              {{ pctFromPrev(stage.value, stages[idx - 1].value) }}% от пред.
            </span>
          </div>
        </div>
        <div class="relative h-9 overflow-hidden rounded-xl bg-slate-50">
          <div
            class="absolute inset-y-0 left-0 flex items-center rounded-xl bg-gradient-to-r from-primary to-primary/70 transition-all duration-700"
            :style="{ width: pctFromTop(stage.value) + '%' }"
          >
            <span v-if="pctFromTop(stage.value) > 18" class="px-3 text-[11px] font-black text-white">
              {{ pctFromTop(stage.value) }}%
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FunnelStage } from '~/types/analytics'

const props = defineProps<{ stages: FunnelStage[] }>()

const top = computed(() => (props.stages.length ? Math.max(props.stages[0].value, 1) : 1))

const pctFromTop = (value: number) => Math.round((value / top.value) * 100)

const pctFromPrev = (value: number, prev: number) => {
  if (!prev) return '0'
  return Math.round((value / prev) * 100).toString()
}
</script>
