<template>
  <div class="h-full w-full">
    <Line
      :data="chartData"
      :options="chartOptions"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler
)

const props = defineProps<{
  data: number[]
  color?: string
}>()

const chartData = computed(() => ({
  labels: props.data.map((_, i) => i),
  datasets: [
    {
      data: props.data,
      borderColor: props.color || '#6366f1',
      borderWidth: 1.5,
      pointRadius: 0,
      pointHoverRadius: 0,
      tension: 0.4,
      fill: true,
      backgroundColor: (context: any) => {
        const ctx = context.chart.ctx
        const gradient = ctx.createLinearGradient(0, 0, 0, 40)
        gradient.addColorStop(0, `${props.color || '#6366f1'}20`)
        gradient.addColorStop(1, `${props.color || '#6366f1'}00`)
        return gradient
      },
    },
  ],
}))

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: { enabled: false },
  },
  scales: {
    x: { display: false },
    y: { display: false, beginAtZero: false },
  },
  interaction: { intersect: false },
}
</script>
