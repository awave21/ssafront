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

    <div v-if="loading && !overview" class="space-y-10">
      <div v-for="section in 3" :key="section" class="space-y-4">
        <div class="h-4 w-32 rounded bg-slate-100 motion-safe:animate-pulse"></div>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Skeleton
            v-for="index in 4"
            :key="index"
            diagonal-shimmer
            :shimmer-delay-ms="((section - 1) * 4 + (index - 1)) * 160"
            class="h-40 rounded-3xl border-none shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
          />
        </div>
      </div>
    </div>

    <div
      v-else-if="sections.length"
      class="space-y-10"
    >
      <div v-for="(section, sIdx) in sections" :key="section.title" class="space-y-4">
        <h3 class="text-[11px] font-bold uppercase tracking-[0.2em] text-slate-400 pl-1">
          {{ section.title }}
        </h3>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2" :class="section.gridClass">
          <div
            v-for="(card, cIdx) in section.cards"
            :key="card.id"
            class="group relative bg-white p-6 rounded-3xl border border-slate-100 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] overflow-hidden transition-all duration-300 motion-safe:animate-analytics-card-enter"
            :class="cardShellExtraClass(card)"
            :style="{ animationDelay: `${(sIdx * 6 + cIdx) * 52}ms` }"
            :role="isDrilldownCard(card) ? 'button' : undefined"
            :tabindex="isDrilldownCard(card) ? 0 : undefined"
            :aria-label="isDrilldownCard(card) ? `${card.label}: открыть список пациентов` : undefined"
            @click="onCardActivate(card)"
            @keydown.enter.prevent="onCardActivate(card)"
            @keydown.space.prevent="onCardActivate(card)"
          >
            <div
              class="absolute -right-4 -bottom-4 h-16 w-16 rounded-full bg-slate-50 transition-transform duration-500"
              :class="accentHoverClass(card)"
            />

            <div class="relative z-10 flex h-full flex-col">
              <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-2">
                  <div
                    class="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-50 text-slate-400 transition-colors"
                    :class="iconHoverClass(card)"
                  >
                    <component :is="card.icon" class="h-4 w-4" />
                  </div>
                  <span
                    class="text-[10px] font-bold uppercase tracking-wider text-slate-400 transition-colors"
                    :class="labelHoverClass(card)"
                  >
                    {{ card.label }}
                  </span>
                </div>

                <div
                  v-if="card.diff !== null"
                  class="flex items-center gap-0.5 text-[10px] font-bold px-2 py-0.5 rounded-full transition-transform duration-300"
                  :class="[
                    card.diff >= 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-600',
                    diffBadgeHoverClass(card),
                  ]"
                >
                  <TrendingUp v-if="card.diff > 0" class="h-2.5 w-2.5" />
                  <TrendingDown v-else-if="card.diff < 0" class="h-2.5 w-2.5" />
                  <span>{{ Math.abs(card.diff) }}%</span>
                </div>
              </div>

              <div class="flex items-end justify-between gap-2 mt-auto">
                <div
                  class="text-2xl font-black text-slate-900 tracking-tight transition-colors"
                  :class="valueHoverClass(card)"
                >
                  {{ card.value }}
                </div>
                <div
                  v-if="card.sparklineData && card.sparklineData.length > 1"
                  class="h-8 w-16 mb-1 opacity-60 transition-opacity"
                  :class="sparklineHoverClass(card)"
                >
                  <Sparkline :data="card.sparklineData" :color="card.diff >= 0 ? '#10b981' : '#f43f5e'" />
                </div>
              </div>

              <p
                class="mt-4 text-[10px] leading-relaxed text-slate-400 font-medium line-clamp-1 transition-colors"
                :class="descHoverClass(card)"
              >
                {{ card.description }}
              </p>
            </div>
          </div>
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
import type { Component } from 'vue'
import {
  CalendarCheck,
  UserCheck,
  UserPlus,
  RefreshCw,
  Users,
  Percent,
  Coins,
  Wallet,
  TrendingUp,
  TrendingDown,
} from 'lucide-vue-next'
import Skeleton from '~/components/ui/skeleton/Skeleton.vue'
import Sparkline from '~/components/analytics/Sparkline.vue'
import type { AnalyticsOverview, AnalyticsTimeseries } from '~/types/analytics'
import type { PatientsVisitCohort } from '~/types/patient-directory'

type KpiCard = {
  id: string
  label: string
  value: string
  diff: number | null
  sparklineData?: number[]
  description: string
  icon: Component
  visitCohort?: PatientsVisitCohort
}

const props = withDefaults(
  defineProps<{
    overview: AnalyticsOverview | null
    previousOverview: AnalyticsOverview | null
    timeseries: AnalyticsTimeseries | null
    loading: boolean
    agentId?: string
    dateFrom?: string
    dateTo?: string
    /** Проброс на /patients: те же границы периода и фильтры, что на дашборде */
    drillTimezone?: string
    drillChannel?: string
    drillClientTags?: string[]
    drillRevenueBasis?: 'all' | 'clinical'
    drillPaymentMethods?: string[]
    drillRevenueCategories?: string[]
    drillResourceExternalId?: number | null
  }>(),
  {
    agentId: '',
    dateFrom: '',
    dateTo: '',
    drillTimezone: '',
    drillChannel: '',
    drillClientTags: () => [],
    drillRevenueBasis: 'clinical',
    drillPaymentMethods: () => [],
    drillRevenueCategories: () => [],
    drillResourceExternalId: null,
  },
)

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

const linkReady = computed(
  () =>
    !!(
      props.agentId?.trim() &&
      props.dateFrom &&
      props.dateTo &&
      /^\d{4}-\d{2}-\d{2}$/.test(props.dateFrom) &&
      /^\d{4}-\d{2}-\d{2}$/.test(props.dateTo)
    ),
)

const isDrilldownCard = (card: KpiCard) => !!(card.visitCohort && linkReady.value)

const cardShellExtraClass = (card: KpiCard) =>
  isDrilldownCard(card)
    ? 'cursor-pointer hover:shadow-[0_12px_24px_-8px_rgba(0,0,0,0.08)] hover:-translate-y-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2'
    : ''

const accentHoverClass = (card: KpiCard) =>
  isDrilldownCard(card) ? 'group-hover:scale-150 group-hover:bg-primary/5' : ''

const iconHoverClass = (card: KpiCard) =>
  isDrilldownCard(card) ? 'group-hover:bg-primary/10 group-hover:text-primary' : ''

const labelHoverClass = (card: KpiCard) =>
  isDrilldownCard(card) ? 'group-hover:text-slate-600' : ''

const valueHoverClass = (card: KpiCard) =>
  isDrilldownCard(card) ? 'group-hover:text-primary' : ''

const descHoverClass = (card: KpiCard) =>
  isDrilldownCard(card) ? 'group-hover:text-slate-500' : ''

const sparklineHoverClass = (card: KpiCard) =>
  isDrilldownCard(card) ? 'group-hover:opacity-100' : ''

const diffBadgeHoverClass = (card: KpiCard) =>
  isDrilldownCard(card) ? 'group-hover:scale-110' : ''

const onCardActivate = (card: KpiCard) => {
  if (!card.visitCohort || !linkReady.value) return
  const query: Record<string, string> = {
    agent: props.agentId.trim(),
    vf: props.dateFrom,
    vt: props.dateTo,
    vc: card.visitCohort,
  }
  const tz = props.drillTimezone?.trim()
  if (tz) query.tz = tz
  const ch = props.drillChannel?.trim()
  if (ch) query.channel = ch
  if (props.drillClientTags?.length) query.tags = props.drillClientTags.join(',')
  if (props.drillRevenueBasis === 'all') query.revenue_basis = 'all'
  if (props.drillPaymentMethods?.length) query.pm = props.drillPaymentMethods.join(',')
  if (props.drillRevenueCategories?.length) query.rc = props.drillRevenueCategories.join(',')
  if (
    props.drillResourceExternalId != null &&
    Number.isFinite(props.drillResourceExternalId)
  ) {
    query.resource = String(Math.trunc(props.drillResourceExternalId))
  }
  void navigateTo({
    path: '/patients',
    query,
  })
}

const sections = computed((): { title: string; gridClass: string; cards: KpiCard[] }[] => {
  const value = props.overview
  const prev = props.previousOverview
  if (!value) return []

  const primaryAvg = Number.isFinite(value.primary_avg_check) ? value.primary_avg_check : 0
  const repeatAvg = Number.isFinite(value.repeat_avg_check) ? value.repeat_avg_check : 0
  const prevPrimaryAvg = prev?.primary_avg_check
  const prevRepeatAvg = prev?.repeat_avg_check

  return [
    {
      title: 'Первичные',
      gridClass: 'lg:grid-cols-5',
      cards: [
        {
          id: 'primary_visits',
          label: 'Записи',
          value: formatInt(value.primary_visits),
          diff: calculateDiff(value.primary_visits, prev?.primary_visits),
          sparklineData: sparklinePoints.value.map((p) => p.primary_visits),
          description: 'Первичные обращения в клинику',
          icon: UserPlus,
          visitCohort: 'primary_bookings' satisfies PatientsVisitCohort,
        },
        {
          id: 'primary_arrived',
          label: 'Дошедшие',
          value: formatInt(value.primary_arrived),
          diff: calculateDiff(value.primary_arrived, prev?.primary_arrived),
          sparklineData: sparklinePoints.value.map((p) => p.primary_arrived),
          description: 'Первичные пациенты, которые дошли',
          icon: Users,
          visitCohort: 'primary_arrived' satisfies PatientsVisitCohort,
        },
        {
          id: 'conversion_primary',
          label: 'Конверсия',
          value: formatPercent(value.conversion_primary_arrived_pct),
          diff: calculateDiff(value.conversion_primary_arrived_pct, prev?.conversion_primary_arrived_pct),
          sparklineData: sparklinePoints.value.map((p) =>
            p.primary_visits > 0 ? (p.primary_arrived / p.primary_visits) * 100 : 0,
          ),
          description: 'Конверсия из первичной записи в факт прихода',
          icon: Percent,
        },
        {
          id: 'primary_revenue',
          label: 'Выручка',
          value: formatMoney(value.primary_revenue),
          diff: calculateDiff(value.primary_revenue, prev?.primary_revenue),
          description: 'Выручка от первичных пациентов',
          icon: Wallet,
        },
        {
          id: 'primary_avg_check',
          label: 'Средний чек',
          value: formatMoney(primaryAvg),
          diff: calculateDiff(primaryAvg, prevPrimaryAvg),
          description: 'Выручка первичных на одного дошедшего',
          icon: Coins,
        },
      ],
    },
    {
      title: 'Повторные',
      gridClass: 'lg:grid-cols-5',
      cards: [
        {
          id: 'repeat_total',
          label: 'Записи',
          value: formatInt(value.repeat_total),
          diff: calculateDiff(value.repeat_total, prev?.repeat_total),
          description: 'Записи от повторных пациентов',
          icon: RefreshCw,
          visitCohort: 'repeat_bookings' satisfies PatientsVisitCohort,
        },
        {
          id: 'repeat_arrived',
          label: 'Дошедшие',
          value: formatInt(value.repeat_arrived),
          diff: calculateDiff(value.repeat_arrived, prev?.repeat_arrived),
          description: 'Повторные пациенты, которые дошли',
          icon: UserCheck,
          visitCohort: 'repeat_arrived' satisfies PatientsVisitCohort,
        },
        {
          id: 'conversion_repeat',
          label: 'Конверсия',
          value: formatPercent(value.conversion_repeat_arrived_pct),
          diff: calculateDiff(value.conversion_repeat_arrived_pct, prev?.conversion_repeat_arrived_pct),
          description: 'Конверсия из повторной записи в факт прихода',
          icon: Percent,
        },
        {
          id: 'repeat_revenue',
          label: 'Выручка',
          value: formatMoney(value.repeat_revenue),
          diff: calculateDiff(value.repeat_revenue, prev?.repeat_revenue),
          description: 'Выручка от повторных пациентов',
          icon: Wallet,
        },
        {
          id: 'repeat_avg_check',
          label: 'Средний чек',
          value: formatMoney(repeatAvg),
          diff: calculateDiff(repeatAvg, prevRepeatAvg),
          description: 'Выручка повторных на одного дошедшего',
          icon: Coins,
        },
      ],
    },
    {
      title: 'Общие',
      gridClass: 'lg:grid-cols-4',
      cards: [
        {
          id: 'visits_total',
          label: 'Записи',
          value: formatInt(value.visits_total),
          diff: calculateDiff(value.visits_total, prev?.visits_total),
          sparklineData: sparklinePoints.value.map((p) => p.visits_total),
          description: 'Всего записей в периоде',
          icon: CalendarCheck,
          visitCohort: 'all_bookings' satisfies PatientsVisitCohort,
        },
        {
          id: 'arrived_total',
          label: 'Дошедшие',
          value: formatInt(value.arrived_total),
          diff: calculateDiff(value.arrived_total, prev?.arrived_total),
          sparklineData: sparklinePoints.value.map((p) => p.arrived_total),
          description: 'Записались и дошли',
          icon: UserCheck,
          visitCohort: 'all_arrived' satisfies PatientsVisitCohort,
        },
        {
          id: 'avg_check',
          label: 'Средний чек',
          value: formatMoney(value.avg_check),
          diff: calculateDiff(value.avg_check, prev?.avg_check),
          sparklineData: sparklinePoints.value.map((p) =>
            p.arrived_total > 0 ? p.revenue_total / p.arrived_total : 0,
          ),
          description: 'Средняя сумма платежа',
          icon: Coins,
        },
        {
          id: 'revenue_total',
          label: 'Выручка',
          value: formatMoney(value.revenue_total),
          diff: calculateDiff(value.revenue_total, prev?.revenue_total),
          sparklineData: sparklinePoints.value.map((p) => p.revenue_total),
          description: 'Платежи с датой оплаты в выбранном периоде',
          icon: Wallet,
        },
      ],
    },
  ]
})
</script>
