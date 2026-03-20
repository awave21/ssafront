<template>
  <div class="group relative bg-white rounded-3xl border border-slate-100 p-8 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1.5 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)] overflow-hidden">
    <!-- Background Accent -->
    <div 
      class="absolute -right-12 -top-12 h-40 w-40 rounded-full bg-slate-50 transition-transform duration-700 group-hover:scale-150 group-hover:bg-primary/5"
    />

    <div class="relative z-10 flex flex-col h-full">
      <div class="flex items-start gap-3 mb-8">
        <div v-if="icon" class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-50 text-slate-400 group-hover:bg-primary/10 group-hover:text-primary transition-colors">
          <component :is="icon" class="h-5 w-5" />
        </div>
        <div class="flex flex-col gap-1">
          <h3 class="text-lg font-bold text-slate-900 tracking-tight group-hover:text-primary transition-colors">
            {{ title }}
          </h3>
          <p v-if="subtitle" class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
            {{ subtitle }}
          </p>
        </div>
      </div>

      <div class="h-64 sm:h-80 w-full">
        <Bar
          v-if="chartType === 'bar'"
          :data="chartData"
          :options="mergedOptions"
        />
        <Line
          v-else-if="chartType === 'line'"
          :data="chartData"
          :options="mergedOptions"
        />
        <Doughnut
          v-else-if="chartType === 'doughnut'"
          :data="chartData"
          :options="doughnutOptions"
        />
      </div>
    </div>
  </div>
</template>


<script setup lang="ts">
import { computed } from 'vue'
import { Bar, Doughnut, Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'
import { defu } from 'defu'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

interface Props {
  title: string
  subtitle?: string
  icon?: any
  chartType: 'bar' | 'doughnut' | 'line'
  chartData: any
  chartOptions?: any
}

const props = defineProps<Props>()

const baseChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: {
        padding: 15,
        usePointStyle: true,
        font: {
          size: 12
        }
      }
    },
    tooltip: {
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      padding: 12,
      titleFont: {
        size: 14
      },
      bodyFont: {
        size: 12
      }
    }
  },
  scales: {
    x: {
      grid: {
        display: false
      },
      ticks: {
        font: {
          size: 11
        }
      }
    },
    y: {
      grid: {
        color: 'rgba(0, 0, 0, 0.05)'
      },
      ticks: {
        font: {
          size: 11
        }
      },
      beginAtZero: true
    }
  }
}

const mergedOptions = computed(() => {
  return defu(props.chartOptions || {}, baseChartOptions)
})

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: {
        padding: 15,
        usePointStyle: true,
        font: {
          size: 12
        }
      }
    },
    tooltip: {
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      padding: 12,
      titleFont: {
        size: 14
      },
      bodyFont: {
        size: 12
      },
      callbacks: {
        label: function(context: any) {
          return `${context.label}: ${context.parsed}%`
        }
      }
    }
  },
  cutout: '60%'
}
</script>
