<template>
  <div class="space-y-6">
    <h2 class="text-sm font-bold uppercase tracking-widest text-slate-400">Динамика</h2>

    <div v-if="loading && !timeseries" class="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Skeleton class="h-96 rounded-3xl bg-white border-none shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]" />
      <Skeleton class="h-96 rounded-3xl bg-white border-none shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]" />
      <Skeleton class="h-96 rounded-3xl bg-white border-none shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]" />
      <Skeleton class="h-96 rounded-3xl bg-white border-none shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]" />
    </div>

    <div v-else-if="timeseries && timeseries.points.length" class="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <ChartCard
        title="Записи и дошедшие"
        subtitle="Количество по выбранному периоду"
        :icon="BarChart3"
        chart-type="bar"
        :chart-data="visitsChartData"
      />
      <ChartCard
        title="Выручка по периодам"
        subtitle="Сумма платежей по периодам"
        :icon="TrendingUp"
        chart-type="bar"
        :chart-data="revenueChartData"
      />
      <ChartCard
        title="Потери от недошедших"
        subtitle="Количество неявки и упущенная финансовая выгода"
        :icon="AlertCircle"
        chart-type="bar"
        :chart-data="lossCombinedChartData"
        :chart-options="lossChartOptions"
      />
      <ChartCard
        title="Доходность на 1 запись"
        subtitle="Средняя выручка на каждую созданную запись"
        :icon="Zap"
        chart-type="line"
        :chart-data="revenuePerBookingChartData"
      />
    </div>


    <div v-else class="flex flex-col items-center justify-center h-48 bg-white rounded-2xl border border-dashed border-slate-200">
      <p class="text-sm font-medium text-slate-400">Недостаточно данных для графиков</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { 
  BarChart3, 
  TrendingUp, 
  AlertCircle, 
  Zap 
} from 'lucide-vue-next'
import ChartCard from '~/components/ChartCard.vue'
import Skeleton from '~/components/ui/skeleton/Skeleton.vue'
import type { AnalyticsTimeseries } from '~/types/analytics'

const props = defineProps<{
  timeseries: AnalyticsTimeseries | null
  loading: boolean
}>()

const labels = computed(() => props.timeseries?.points.map(point => point.label) || [])

const visitsChartData = computed(() => {
  const points = props.timeseries?.points || []
  return {
    labels: labels.value,
    datasets: [
      {
        label: 'Записи',
        data: points.map(point => point.visits_total),
        backgroundColor: '#6366f1', // Indigo 500
        borderRadius: 4,
      },
      {
        label: 'Дошедшие',
        data: points.map(point => point.arrived_total),
        backgroundColor: '#10b981', // Emerald 500
        borderRadius: 4,
      },
    ],
  }
})

const revenueChartData = computed(() => {
  const points = props.timeseries?.points || []
  return {
    labels: labels.value,
    datasets: [
      {
        label: 'Выручка, ₽',
        data: points.map(point => point.revenue_total),
        backgroundColor: '#f59e0b', // Amber 500
        borderRadius: 4,
      },
    ],
  }
})

const lossCombinedChartData = computed(() => {
  const points = props.timeseries?.points || []
  return {
    labels: labels.value,
    datasets: [
      {
        label: 'Не пришло (чел.)',
        data: points.map(point => point.visits_total - point.arrived_total),
        backgroundColor: '#fb7185', // Rose 400
        borderRadius: 4,
        yAxisID: 'y',
        order: 2
      },
      {
        label: 'Упущенная выручка (₽)',
        data: points.map(point => {
          if (point.arrived_total === 0) return 0
          const avgCheck = point.revenue_total / point.arrived_total
          const noShows = point.visits_total - point.arrived_total
          return Math.round(noShows * avgCheck)
        }),
        borderColor: '#e11d48', // Rose 600
        backgroundColor: 'rgba(225, 29, 72, 0.1)',
        borderWidth: 2,
        fill: false,
        tension: 0.4,
        type: 'line',
        yAxisID: 'y1',
        order: 1
      },
    ],
  }
})

const lossChartOptions = {
  scales: {
    y: {
      type: 'linear',
      display: true,
      position: 'left',
      title: {
        display: true,
        text: 'Человек',
        font: { size: 10, weight: 'bold' }
      },
      grid: { display: false }
    },
    y1: {
      type: 'linear',
      display: true,
      position: 'right',
      title: {
        display: true,
        text: 'Рубли',
        font: { size: 10, weight: 'bold' }
      },
      grid: {
        drawOnChartArea: false,
      },
    },
  }
}

const revenuePerBookingChartData = computed(() => {
  const points = props.timeseries?.points || []
  return {
    labels: labels.value,
    datasets: [
      {
        label: 'Выручка на запись, ₽',
        data: points.map(point => {
          if (point.visits_total === 0) return 0
          return Math.round(point.revenue_total / point.visits_total)
        }),
        borderColor: '#8b5cf6', // Violet 500
        backgroundColor: 'rgba(139, 92, 246, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointHoverRadius: 6,
      },
    ],
  }
})
</script>
