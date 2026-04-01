<template>
  <div class="space-y-6">
    <h2 class="text-sm font-bold uppercase tracking-widest text-slate-400">Распределение</h2>

    <div v-if="loading && !hasData" class="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <Skeleton
        v-for="i in 3"
        :key="i"
        diagonal-shimmer
        :shimmer-delay-ms="(i - 1) * 180"
        class="h-[520px] rounded-3xl border-none shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
      />
    </div>

    <div v-else class="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <!-- Channel Breakdown -->
      <div
        class="group relative bg-white p-8 rounded-3xl border border-slate-100 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1.5 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)] overflow-hidden motion-safe:animate-analytics-card-enter"
        :style="{ animationDelay: '0ms' }"
      >
        <div 
          class="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-slate-50 transition-transform duration-700 group-hover:scale-150 group-hover:bg-primary/5"
        />
        
        <div class="relative z-10 flex flex-col h-full">
          <div class="flex flex-col gap-1 mb-8">
            <h3 class="text-lg font-bold text-slate-900 tracking-tight group-hover:text-primary transition-colors">Канал связи</h3>
            <p class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Распределение записей</p>
          </div>

          <div v-if="channelItems.length" class="space-y-8 flex-1">
            <div class="h-44">
              <Doughnut
                :data="channelChartData"
                :options="doughnutOptions"
              />
            </div>
            <div class="space-y-4">
              <div v-for="item in channelItems.slice(0, 5)" :key="item.key" class="space-y-2">
                <div class="flex items-center justify-between">
                  <span class="text-[11px] font-bold text-slate-700 truncate max-w-[140px]">{{ item.label }}</span>
                  <span class="text-[11px] font-black text-slate-400">{{ formatShare(item.share) }}</span>
                </div>
                <div class="relative h-1.5 w-full bg-slate-50 rounded-full overflow-hidden">
                  <div
                    class="absolute top-0 left-0 h-full bg-primary rounded-full transition-all duration-1000 ease-out shadow-[0_0_8px_rgba(var(--primary-rgb),0.3)]"
                    :style="{ width: `${item.share * 100}%` }"
                  ></div>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="flex h-44 items-center justify-center text-sm text-slate-300 font-medium italic">
            Нет данных
          </div>
        </div>
      </div>

      <!-- Tag Breakdown -->
      <div
        class="group relative bg-white p-8 rounded-3xl border border-slate-100 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1.5 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)] overflow-hidden motion-safe:animate-analytics-card-enter"
        :style="{ animationDelay: '75ms' }"
      >
        <div 
          class="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-slate-50 transition-transform duration-700 group-hover:scale-150 group-hover:bg-emerald-500/5"
        />

        <div class="relative z-10 flex flex-col h-full">
          <div class="flex flex-col gap-1 mb-8">
            <h3 class="text-lg font-bold text-slate-900 tracking-tight group-hover:text-emerald-600 transition-colors">Теги клиента</h3>
            <p class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Популярные метки</p>
          </div>

          <div v-if="tagItems.length" class="space-y-8 flex-1">
            <div class="h-44">
              <Doughnut
                :data="tagChartData"
                :options="doughnutOptions"
              />
            </div>
            <div class="space-y-4">
              <div v-for="item in tagItems.slice(0, 5)" :key="item.key" class="space-y-2">
                <div class="flex items-center justify-between">
                  <span class="text-[11px] font-bold text-slate-700 truncate max-w-[140px]">{{ item.label }}</span>
                  <span class="text-[11px] font-black text-slate-400">{{ formatShare(item.share) }}</span>
                </div>
                <div class="relative h-1.5 w-full bg-slate-50 rounded-full overflow-hidden">
                  <div
                    class="absolute top-0 left-0 h-full bg-emerald-500 rounded-full transition-all duration-1000 ease-out shadow-[0_0_8px_rgba(16,185,129,0.3)]"
                    :style="{ width: `${item.share * 100}%` }"
                  ></div>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="flex h-44 items-center justify-center text-sm text-slate-300 font-medium italic">
            Нет данных
          </div>
        </div>
      </div>

      <!-- Visit Status -->
      <div
        class="group relative bg-white p-8 rounded-3xl border border-slate-100 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1.5 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)] overflow-hidden motion-safe:animate-analytics-card-enter"
        :style="{ animationDelay: '150ms' }"
      >
        <div 
          class="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-slate-50 transition-transform duration-700 group-hover:scale-150 group-hover:bg-primary/5"
        />

        <div class="relative z-10 flex flex-col h-full">
          <div class="flex flex-col gap-1 mb-8">
            <h3 class="text-lg font-bold text-slate-900 tracking-tight group-hover:text-primary transition-colors">Статус визитов</h3>
            <p class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Дошедшие vs Недошедшие</p>
          </div>

          <div v-if="overview" class="space-y-8 flex-1">
            <div class="h-44">
              <Doughnut
                :data="arrivalChartData"
                :options="doughnutOptions"
              />
            </div>
            <div class="space-y-4">
              <div class="flex items-center justify-between p-4 rounded-2xl bg-emerald-50/50 group-hover:bg-emerald-50 transition-colors">
                <div class="flex items-center gap-3">
                  <div class="h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]"></div>
                  <span class="text-xs font-bold text-emerald-700">Дошли</span>
                </div>
                <span class="text-sm font-black text-emerald-600">{{ formatInt(overview.arrived_total) }}</span>
              </div>
              <div class="flex items-center justify-between p-4 rounded-2xl bg-rose-50/50 group-hover:bg-rose-50 transition-colors">
                <div class="flex items-center gap-3">
                  <div class="h-2.5 w-2.5 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.4)]"></div>
                  <span class="text-xs font-bold text-rose-700">Не дошли</span>
                </div>
                <span class="text-sm font-black text-rose-600">{{ formatInt(overview.visits_total - overview.arrived_total) }}</span>
              </div>
            </div>
          </div>
          <div v-else class="flex h-44 items-center justify-center text-sm text-slate-300 font-medium italic">
            Нет данных
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend
} from 'chart.js'
import Skeleton from '~/components/ui/skeleton/Skeleton.vue'
import type { AnalyticsBreakdown, AnalyticsOverview } from '~/types/analytics'

ChartJS.register(ArcElement, Tooltip, Legend)

const props = defineProps<{
  channelBreakdown: AnalyticsBreakdown | null
  tagBreakdown: AnalyticsBreakdown | null
  overview: AnalyticsOverview | null
  loading: boolean
}>()

const channelItems = computed(() => props.channelBreakdown?.items || [])
const tagItems = computed(() => props.tagBreakdown?.items || [])
const hasData = computed(() => channelItems.value.length > 0 || tagItems.value.length > 0)

const percentFormatter = new Intl.NumberFormat('ru-RU', {
  maximumFractionDigits: 1,
})

const intFormatter = new Intl.NumberFormat('ru-RU', {
  maximumFractionDigits: 0,
})

const formatShare = (share: number) => `${percentFormatter.format((share || 0) * 100)}%`
const formatInt = (value: number) => intFormatter.format(Number.isFinite(value) ? value : 0)

const COLORS = [
  '#6366f1', // Indigo
  '#10b981', // Emerald
  '#f59e0b', // Amber
  '#ec4899', // Pink
  '#8b5cf6', // Violet
  '#06b6d4', // Cyan
  '#f43f5e', // Rose
  '#3b82f6', // Blue
  '#84cc16', // Lime
  '#a855f7', // Purple
]

const channelChartData = computed(() => ({
  labels: channelItems.value.map(i => i.label),
  datasets: [{
    data: channelItems.value.map(i => i.count),
    backgroundColor: COLORS,
    borderWidth: 0,
    hoverOffset: 4
  }]
}))

const tagChartData = computed(() => ({
  labels: tagItems.value.map(i => i.label),
  datasets: [{
    data: tagItems.value.map(i => i.count),
    backgroundColor: COLORS,
    borderWidth: 0,
    hoverOffset: 4
  }]
}))

const arrivalChartData = computed(() => {
  if (!props.overview) return { labels: [], datasets: [] }
  const arrived = props.overview.arrived_total
  const noShows = props.overview.visits_total - arrived
  return {
    labels: ['Дошли', 'Не дошли'],
    datasets: [{
      data: [arrived, noShows],
      backgroundColor: ['#10b981', '#f43f5e'],
      borderWidth: 0,
      hoverOffset: 4
    }]
  }
})

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false
    },
    tooltip: {
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      padding: 12,
      titleFont: { size: 12 },
      bodyFont: { size: 12 }
    }
  },
  cutout: '75%'
}
</script>
