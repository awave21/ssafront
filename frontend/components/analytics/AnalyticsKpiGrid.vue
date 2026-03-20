<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-sm font-bold uppercase tracking-widest text-slate-400">Ключевые показатели</h2>
      <div v-if="overview" class="flex items-center gap-2 px-3 py-1 bg-white rounded-full border border-slate-100 shadow-sm">
        <div class="h-1.5 w-1.5 rounded-full bg-emerald-500"></div>
        <span class="text-[11px] font-medium text-slate-600 tracking-tight">
          {{ periodLabel }}
        </span>
      </div>
    </div>

    <div v-if="loading && !overview" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
      <Skeleton
        v-for="index in 10"
        :key="index"
        class="h-40 rounded-3xl bg-white border-none shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
      />
    </div>

    <div
      v-else-if="cards.length"
      class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5"
    >
      <div
        v-for="card in cards"
        :key="card.id"
        class="group relative bg-white p-6 rounded-3xl border border-slate-100 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-300 hover:shadow-[0_12px_24px_-8px_rgba(0,0,0,0.08)] hover:-translate-y-1 overflow-hidden"
      >
        <!-- Decorative Accent -->
        <div 
          class="absolute -right-4 -bottom-4 h-16 w-16 rounded-full bg-slate-50 transition-transform duration-500 group-hover:scale-150 group-hover:bg-primary/5"
        />

        <div class="relative z-10 flex h-full flex-col">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-50 text-slate-400 group-hover:bg-primary/10 group-hover:text-primary transition-colors">
                <component :is="card.icon" class="h-4 w-4" />
              </div>
              <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 group-hover:text-slate-600 transition-colors">
                {{ card.title }}
              </span>
            </div>
            
            <div
              v-if="card.diff !== null"
              class="flex items-center gap-0.5 text-[10px] font-bold px-2 py-0.5 rounded-full transition-transform duration-300 group-hover:scale-110"
              :class="card.diff >= 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-600'"
            >
              <TrendingUp v-if="card.diff > 0" class="h-2.5 w-2.5" />
              <TrendingDown v-else-if="card.diff < 0" class="h-2.5 w-2.5" />
              <span>{{ Math.abs(card.diff) }}%</span>
            </div>
          </div>
          
          <div class="flex items-end justify-between gap-2 mt-auto">
            <div class="text-2xl font-black text-slate-900 tracking-tight group-hover:text-primary transition-colors">
              {{ card.value }}
            </div>
            <div v-if="card.sparklineData.length > 1" class="h-8 w-16 mb-1 opacity-60 group-hover:opacity-100 transition-opacity">
              <Sparkline :data="card.sparklineData" :color="card.diff >= 0 ? '#10b981' : '#f43f5e'" />
            </div>
          </div>

          <p class="mt-4 text-[10px] leading-relaxed text-slate-400 font-medium line-clamp-1 group-hover:text-slate-500 transition-colors">
            {{ card.description }}
          </p>
        </div>
      </div>
    </div>

    <div v-else class="flex flex-col items-center justify-center h-48 bg-white rounded-2xl border border-dashed border-slate-200">
      <div class="h-12 w-12 rounded-full bg-slate-50 flex items-center justify-center mb-3">
        <div class="h-6 w-6 border-2 border-slate-200 rounded-md"></div>
      </div>
      <p class="text-sm font-medium text-slate-400">Нет данных за выбранный период</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { 
  CalendarCheck, 
  UserCheck, 
  UserPlus, 
  RefreshCw, 
  Users, 
  Database, 
  Percent, 
  Coins, 
  Wallet, 
  CreditCard,
  TrendingUp,
  TrendingDown
} from 'lucide-vue-next'
import Skeleton from '~/components/ui/skeleton/Skeleton.vue'
import Sparkline from '~/components/analytics/Sparkline.vue'
import type { AnalyticsOverview, AnalyticsTimeseries } from '~/types/analytics'

const props = defineProps<{
  overview: AnalyticsOverview | null
  previousOverview: AnalyticsOverview | null
  timeseries: AnalyticsTimeseries | null
  loading: boolean
}>()

const moneyFormatter = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
})

const intFormatter = new Intl.NumberFormat('ru-RU', {
  maximumFractionDigits: 0,
})

const percentFormatter = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

const formatInt = (value: number) => intFormatter.format(Number.isFinite(value) ? value : 0)
const formatMoney = (value: number) => `${moneyFormatter.format(Number.isFinite(value) ? value : 0)} ₽`
const formatPercent = (value: number) => `${percentFormatter.format(Number.isFinite(value) ? value : 0)}%`

const calculateDiff = (current: number, previous: number | undefined) => {
  if (previous === undefined || previous === 0) return null
  return Math.round(((current - previous) / previous) * 100)
}

const periodLabel = computed(() => {
  if (!props.overview) return ''
  const from = new Date(props.overview.period_start)
  const to = new Date(props.overview.period_end)
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return ''
  return `${from.toLocaleDateString('ru-RU')} - ${to.toLocaleDateString('ru-RU')}`
})

const sparklinePoints = computed(() => props.timeseries?.points || [])

const cards = computed(() => {
  const value = props.overview
  const prev = props.previousOverview
  if (!value) return []

  return [
    {
      id: 'visits_total',
      title: 'Записи',
      value: formatInt(value.visits_total),
      diff: calculateDiff(value.visits_total, prev?.visits_total),
      sparklineData: sparklinePoints.value.map(p => p.visits_total),
      description: 'Всего записей в периоде',
      icon: CalendarCheck
    },
    {
      id: 'arrived_total',
      title: 'Дошедшие',
      value: formatInt(value.arrived_total),
      diff: calculateDiff(value.arrived_total, prev?.arrived_total),
      sparklineData: sparklinePoints.value.map(p => p.arrived_total),
      description: 'Записались и дошли',
      icon: UserCheck
    },
    {
      id: 'arrived_primary',
      title: 'Первичные',
      value: formatInt(value.arrived_primary),
      diff: calculateDiff(value.arrived_primary, prev?.arrived_primary),
      sparklineData: [],
      description: 'Первичные пациенты, которые пришли',
      icon: UserPlus
    },
    {
      id: 'repeat_total',
      title: 'Повторные',
      value: formatInt(value.repeat_total),
      diff: calculateDiff(value.repeat_total, prev?.repeat_total),
      sparklineData: [],
      description: 'Записи от повторных пациентов',
      icon: RefreshCw
    },
    {
      id: 'bookings_from_primary',
      title: 'От первичных',
      value: formatInt(value.bookings_from_primary),
      diff: calculateDiff(value.bookings_from_primary, prev?.bookings_from_primary),
      sparklineData: [],
      description: 'Все записи от первичных',
      icon: Users
    },
    {
      id: 'bookings_from_existing',
      title: 'Из базы',
      value: formatInt(value.bookings_from_existing_patients),
      diff: calculateDiff(value.bookings_from_existing_patients, prev?.bookings_from_existing_patients),
      sparklineData: [],
      description: 'Пациенты, уже присутствующие в базе',
      icon: Database
    },
    {
      id: 'conversion',
      title: 'Конверсия',
      value: formatPercent(value.conversion_arrived_to_booked_pct),
      diff: calculateDiff(value.conversion_arrived_to_booked_pct, prev?.conversion_arrived_to_booked_pct),
      sparklineData: sparklinePoints.value.map(p => p.visits_total > 0 ? (p.arrived_total / p.visits_total) * 100 : 0),
      description: 'Конверсия из записи в приход',
      icon: Percent
    },
    {
      id: 'avg_check',
      title: 'Средний чек',
      value: formatMoney(value.avg_check),
      diff: calculateDiff(value.avg_check, prev?.avg_check),
      sparklineData: sparklinePoints.value.map(p => p.arrived_total > 0 ? p.revenue_total / p.arrived_total : 0),
      description: 'Средняя сумма платежа',
      icon: Coins
    },
    {
      id: 'revenue_total',
      title: 'Выручка',
      value: formatMoney(value.revenue_total),
      diff: calculateDiff(value.revenue_total, prev?.revenue_total),
      sparklineData: sparklinePoints.value.map(p => p.revenue_total),
      description: 'Сумма платежей за период',
      icon: Wallet
    },
    {
      id: 'payments_total',
      title: 'Платежи',
      value: formatInt(value.payments_total),
      diff: calculateDiff(value.payments_total, prev?.payments_total),
      sparklineData: [],
      description: 'Количество учтенных платежей',
      icon: CreditCard
    },
  ]
})
</script>
