<template>
  <div class="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 shadow-sm">
    <div class="flex items-center justify-between mb-4">
      <p class="text-xs sm:text-sm font-normal text-slate-600">
        {{ title }}
      </p>
      <div
        :class="[
          'flex items-center justify-center w-9 h-9 sm:w-10 sm:h-10 rounded-lg',
          iconBgColor
        ]"
      >
        <component
          :is="iconComponent"
          :class="['h-4 w-4 sm:h-5 sm:w-5', iconColor]"
        />
      </div>
    </div>

    <p class="text-3xl sm:text-4xl font-bold text-slate-900 mb-2">
      {{ value }}
    </p>

    <p class="text-xs sm:text-sm text-slate-500 mb-3">
      {{ description }}
    </p>

    <div class="flex items-center gap-1.5">
      <component
        :is="trendIcon"
        :class="['h-3 w-3', trendColor]"
      />
      <span :class="['text-xs sm:text-sm font-medium', trendColor]">
        {{ trend }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  Calendar,
  XCircle,
  BarChart2,
  Target,
  UserCheck,
  Layers,
  FileText,
  UserX,
  ArrowUp,
  ArrowDown,
  Circle
} from 'lucide-vue-next'

interface Props {
  title: string
  value: string
  description: string
  trend: string
  type: 'positive' | 'negative' | 'info' | 'warning'
  icon: string
}

const props = defineProps<Props>()

const iconComponent = computed(() => {
  const iconMap: Record<string, any> = {
    Calendar,
    XCircle,
    BarChart2,
    Target,
    UserCheck,
    Layers,
    FileText,
    UserX
  }
  return iconMap[props.icon] || Calendar
})

const iconBgColor = computed(() => {
  switch (props.type) {
    case 'positive':
      return 'bg-green-50'
    case 'negative':
      return 'bg-red-50'
    case 'info':
      return 'bg-sky-50'
    case 'warning':
      return 'bg-amber-50'
    default:
      return 'bg-slate-50'
  }
})

const iconColor = computed(() => {
  switch (props.type) {
    case 'positive':
      return 'text-green-600'
    case 'negative':
      return 'text-red-600'
    case 'info':
      return 'text-sky-600'
    case 'warning':
      return 'text-amber-600'
    default:
      return 'text-slate-600'
  }
})

const trendColor = computed(() => {
  switch (props.type) {
    case 'positive':
      return 'text-green-600'
    case 'negative':
      return 'text-slate-500'
    case 'info':
      return 'text-green-600'
    case 'warning':
      return 'text-green-600'
    default:
      return 'text-slate-600'
  }
})

const trendIcon = computed(() => {
  if (props.type === 'negative') {
    return ArrowUp
  }
  if (props.trend.includes('Достигнуто')) {
    return Circle
  }
  return ArrowUp
})
</script>