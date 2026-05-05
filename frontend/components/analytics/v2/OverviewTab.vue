<template>
  <div class="space-y-8">
    <!-- AI Summary -->
    <AiSummaryCard
      :payload="businessAiPayload"
      :loading="aiRecoLoading"
      :cached="aiReco?.cached"
      :model="aiReco?.model"
      @refresh="$emit('refresh-ai')"
      @go-to-tab="(t) => $emit('go-to-tab', t)"
    />

    <!-- Insights strip (без бот/бюджет — это во вкладке Бот) -->
    <InsightsStrip
      :items="businessInsights"
      @go-to-tab="(t) => $emit('go-to-tab', t)"
      @navigate="(u) => $emit('navigate', u)"
    />

    <!-- Executive KPI row — данные из overview (учитывает все фильтры) -->
    <section v-if="kpiData" class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
      <KpiTile
        label="Выручка"
        :value="kpiData.revenue"
        :icon="TrendingUp"
        accent="emerald"
        format="money"
        :sub="kpiData.revenue_crossperiod > 0 ? `в т.ч. ${fmtMoney(kpiData.revenue_crossperiod)} за визиты других периодов` : undefined"
        :sub-href="crossperiodRoute"
      />
      <KpiTile label="Записей" :value="kpiData.visits" :icon="CalendarCheck" accent="primary" />
      <KpiTile label="Конверсия" :value="kpiData.conversion_pct" :icon="Percent" accent="primary" format="pct" />
      <KpiTile label="Средний чек" :value="kpiData.avg_check" :icon="Receipt" accent="slate" format="money" />
      <KpiTile label="Не пришли" :value="kpiData.no_show_pct" :icon="UserX" accent="rose" format="pct" sub="Записались, но не явились на приём" />
    </section>

    <!-- Funnel -->
    <FunnelChart v-if="funnel?.stages?.length" :stages="funnel.stages" />

    <!-- Existing timeseries & breakdown (reused) -->
    <slot />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { TrendingUp, CalendarCheck, Percent, Receipt, UserX } from 'lucide-vue-next'

const fmt = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })
const fmtMoney = (v: number) => {
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + ' млн ₽'
  if (v >= 10_000) return Math.round(v / 1000) + ' тыс ₽'
  return fmt.format(Math.round(v)) + ' ₽'
}
import AiSummaryCard from './AiSummaryCard.vue'
import InsightsStrip from './InsightsStrip.vue'
import FunnelChart from './FunnelChart.vue'
import KpiTile from './KpiTile.vue'
import type {
  AiRecommendationsResponse,
  AnalyticsFilters,
  AnalyticsOverview,
  InsightsResponse,
  FunnelResponse,
  StaffOverviewResponse,
} from '~/types/analytics'

const props = defineProps<{
  aiReco: AiRecommendationsResponse | null
  aiRecoLoading: boolean
  insights: InsightsResponse | null
  funnel: FunnelResponse | null
  staff: StaffOverviewResponse | null
  overview: AnalyticsOverview | null
  agentId?: string
  filters?: AnalyticsFilters
}>()

defineEmits<{
  (e: 'refresh-ai'): void
  (e: 'go-to-tab', tab: string): void
  (e: 'navigate', url: string): void
}>()

const crossperiodRoute = computed(() => {
  if (!props.agentId || !props.filters) return undefined
  const f = props.filters
  const q = new URLSearchParams()
  q.set('agent_id', f.agentId)
  q.set('date_from', f.dateFrom)
  q.set('date_to', f.dateTo)
  q.set('timezone', f.timezone)
  if (f.channel) q.set('channel', f.channel)
  q.set('revenue_basis', f.revenueBasis)
  if (f.paymentMethods?.length) q.set('payment_methods', f.paymentMethods.join(','))
  if (f.revenueCategories?.length) q.set('revenue_categories', f.revenueCategories.join(','))
  if (kpiData.value?.revenue) q.set('revenue_total', String(Math.round(kpiData.value.revenue)))
  if (kpiData.value?.revenue_crossperiod) q.set('revenue_crossperiod', String(Math.round(kpiData.value.revenue_crossperiod)))
  return `/analytics/crossperiod-payments?${q.toString()}`
})

const businessInsights = computed(() =>
  (props.insights?.items ?? []).filter(
    (i) => i.category !== 'bot' && i.category !== 'budget',
  ),
)

const businessAiPayload = computed(() => {
  const p = props.aiReco?.payload
  if (!p) return null
  return {
    ...p,
    recommendations: p.recommendations.filter((r) => r.target_tab !== 'bot'),
  }
})

// KPI считаем из overview (применяет все фильтры: дата, канал, способ оплаты, теги).
// Fallback на staff-агрегат если overview ещё не загружен.
const kpiData = computed(() => {
  if (props.overview) {
    const o = props.overview
    const no_shows = o.visits_total - o.arrived_total
    return {
      revenue: o.revenue_total,
      revenue_crossperiod: o.revenue_crossperiod ?? 0,
      visits: o.visits_total,
      avg_check: o.avg_check,
      conversion_pct: o.visits_total > 0 ? Math.round((o.arrived_total / o.visits_total) * 100) : 0,
      no_show_pct: o.visits_total > 0 ? Math.round((no_shows / o.visits_total) * 100) : 0,
    }
  }
  // fallback: агрегат из staff (только дата-фильтр)
  if (!props.staff) return null
  const items = props.staff.items
  if (!items.length) return null
  const revenue = items.reduce((s, m) => s + m.revenue_total, 0)
  const visits = items.reduce((s, m) => s + m.visits_total, 0)
  const arrived = items.reduce((s, m) => s + m.arrived_total, 0)
  const no_shows = items.reduce((s, m) => s + Math.round(m.visits_total * m.no_show_pct / 100), 0)
  return {
    revenue,
    revenue_crossperiod: 0,
    visits,
    avg_check: arrived > 0 ? Math.round(revenue / arrived) : 0,
    conversion_pct: visits > 0 ? Math.round((arrived / visits) * 100) : 0,
    no_show_pct: visits > 0 ? Math.round((no_shows / visits) * 100) : 0,
  }
})
</script>
