<template>
  <div v-if="items.length" class="space-y-3">
    <div class="flex items-center justify-between">
      <h3 class="text-[11px] font-bold uppercase tracking-[0.2em] text-slate-400">Инсайты</h3>
      <span class="text-[11px] font-medium text-slate-400">{{ items.length }} активных</span>
    </div>

    <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      <div
        v-for="item in items"
        :key="item.code + (item.entity_id || '')"
        class="group relative flex cursor-pointer flex-col gap-2 rounded-2xl border bg-white p-4 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all hover:-translate-y-0.5 hover:shadow-md"
        :class="severityBorder(item.severity)"
        @click="onClick(item)"
      >
        <div class="flex items-start gap-3">
          <div
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl"
            :class="severityIconBg(item.severity)"
          >
            <component :is="severityIcon(item.severity)" class="h-4 w-4" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="text-sm font-bold leading-tight text-slate-900">{{ item.title }}</div>
            <p class="mt-1 text-xs leading-relaxed text-slate-600">{{ item.body }}</p>
          </div>
        </div>

        <div v-if="item.metric_value !== null" class="flex items-center justify-between pt-1">
          <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            {{ item.metric_label || 'Метрика' }}
          </span>
          <span class="text-sm font-black tabular-nums" :class="severityText(item.severity)">
            {{ formatMetric(item.metric_value) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { AlertTriangle, AlertOctagon, Info } from 'lucide-vue-next'
import type { Insight, InsightSeverity } from '~/types/analytics'

const props = defineProps<{ items: Insight[] }>()

const emit = defineEmits<{
  (e: 'go-to-tab', tab: string): void
  (e: 'navigate', url: string): void
}>()

const severityIcon = (s: InsightSeverity) => {
  if (s === 'critical') return AlertOctagon
  if (s === 'warning') return AlertTriangle
  return Info
}

const severityIconBg = (s: InsightSeverity): string => {
  if (s === 'critical') return 'bg-rose-50 text-rose-600'
  if (s === 'warning') return 'bg-amber-50 text-amber-600'
  return 'bg-sky-50 text-sky-600'
}

const severityBorder = (s: InsightSeverity): string => {
  if (s === 'critical') return 'border-rose-100'
  if (s === 'warning') return 'border-amber-100'
  return 'border-slate-100'
}

const severityText = (s: InsightSeverity): string => {
  if (s === 'critical') return 'text-rose-700'
  if (s === 'warning') return 'text-amber-700'
  return 'text-slate-700'
}

const formatMetric = (v: number): string => {
  if (Math.abs(v) >= 1000) return v.toLocaleString('ru-RU', { maximumFractionDigits: 0 })
  return Number.isInteger(v) ? String(v) : v.toFixed(1)
}

const onClick = (item: Insight) => {
  if (item.action_tab) emit('go-to-tab', item.action_tab)
  else if (item.action_url) emit('navigate', item.action_url)
}

void props
</script>
