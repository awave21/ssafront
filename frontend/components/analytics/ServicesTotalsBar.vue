<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-bold uppercase tracking-widest text-slate-400">Итоги по услугам</h3>
    </div>
    
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
      <div
        v-for="card in summaryCards"
        :key="card.id"
        class="group relative bg-white p-6 rounded-3xl border border-slate-100 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-300 hover:shadow-[0_12px_24px_-8px_rgba(0,0,0,0.08)] hover:-translate-y-1 overflow-hidden"
      >
        <!-- Decorative Accent -->
        <div 
          class="absolute -right-4 -bottom-4 h-16 w-16 rounded-full bg-slate-50 transition-transform duration-500 group-hover:scale-150 group-hover:bg-primary/5"
        />

        <div class="relative z-10 flex flex-col h-full">
          <div class="flex items-center gap-2 mb-3">
            <component 
              :is="card.icon" 
              class="h-4 w-4 text-slate-300 group-hover:text-primary transition-colors"
            />
            <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 group-hover:text-slate-600 transition-colors">
              {{ card.title }}
            </span>
          </div>
          
          <div class="text-2xl font-black text-slate-900 tracking-tight group-hover:text-primary transition-colors">
            {{ card.value }}
          </div>
          
          <p class="mt-2 text-[10px] leading-relaxed text-slate-400 font-medium line-clamp-1 group-hover:text-slate-500 transition-colors">
            {{ card.description }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { 
  LayoutGrid, 
  CalendarCheck, 
  UserCheck, 
  Wallet, 
  Coins 
} from 'lucide-vue-next'
import type { AnalyticsServicesTableTotals } from '~/types/analytics'

const props = defineProps<{
  totals: AnalyticsServicesTableTotals
}>()

const intFormatter = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })
const moneyFormatter = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })

const formatInt = (value: number) => intFormatter.format(Number.isFinite(value) ? value : 0)
const formatMoney = (value: number) => `${moneyFormatter.format(Number.isFinite(value) ? value : 0)} ₽`

const summaryCards = computed(() => [
  {
    id: 'services_total',
    title: 'Услуг',
    value: formatInt(props.totals.services_total),
    description: 'Количество уникальных услуг',
    icon: LayoutGrid
  },
  {
    id: 'bookings_total',
    title: 'Записи',
    value: formatInt(props.totals.bookings_total),
    description: 'Всего записей по услугам',
    icon: CalendarCheck
  },
  {
    id: 'arrived_total',
    title: 'Дошедшие',
    value: formatInt(props.totals.arrived_total),
    description: 'Клиенты, которые пришли',
    icon: UserCheck
  },
  {
    id: 'revenue_total',
    title: 'Выручка',
    value: formatMoney(props.totals.revenue_total),
    description: 'Суммарная выручка по услугам',
    icon: Wallet
  },
  {
    id: 'avg_check',
    title: 'Средний чек',
    value: formatMoney(props.totals.avg_check),
    description: 'Средняя сумма оплаты',
    icon: Coins
  },
])
</script>

