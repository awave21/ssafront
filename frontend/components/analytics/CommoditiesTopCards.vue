<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-bold uppercase tracking-widest text-slate-400">Топ товаров по записям</h3>
      <div v-if="topItems.length" class="text-[11px] font-medium text-slate-400">
        Показаны первые {{ topItems.length }} из {{ items.length }}
      </div>
    </div>

    <div v-if="loading && !items.length" class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="index in 3"
        :key="index"
        class="h-[280px] rounded-3xl border border-slate-100 bg-white p-6 shadow-sm animate-pulse"
      />
    </div>

    <div
      v-else-if="topItems.length"
      class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3"
    >
      <div
        v-for="(service, index) in topItems"
        :key="service.commodity_key"
        class="group relative flex flex-col overflow-hidden rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1.5 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
      >
        <!-- Background Accent -->
        <div 
          class="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-primary/5 transition-transform duration-700 group-hover:scale-150"
        />

        <div class="relative flex h-full flex-col">
          <!-- Header -->
          <div class="mb-5 flex items-start justify-between">
            <div class="flex flex-col gap-1">
              <div 
                class="inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold tracking-wider uppercase transition-colors"
                :class="[
                  index === 0 ? 'bg-amber-100 text-amber-700' : 
                  index === 1 ? 'bg-slate-100 text-slate-600' : 
                  index === 2 ? 'bg-orange-100 text-orange-700' : 'bg-slate-50 text-slate-500'
                ]"
              >
                <Trophy v-if="index < 3" class="mr-1 h-3 w-3" />
                Место {{ index + 1 }}
              </div>
              <span class="text-[11px] font-medium text-slate-400">
                {{ service.commodity_category || 'Без категории' }}
              </span>
            </div>
            
            <div class="flex flex-col items-end gap-1">
              <div class="text-lg font-black text-primary">
                {{ formatPercent(service.share_bookings * 100) }}
              </div>
              <div class="text-[9px] font-bold uppercase tracking-tighter text-slate-300">Доля записей</div>
            </div>
          </div>

          <!-- Title -->
          <div class="group/title relative mb-6">
            <h4 class="line-clamp-2 min-h-[3rem] text-lg font-bold leading-tight text-slate-900 group-hover:text-primary transition-colors">
              {{ service.commodity_name }}
            </h4>
          </div>

          <!-- Progress Bar -->
          <div class="mb-6 space-y-2">
            <div class="flex justify-between items-end">
              <div class="flex flex-col">
                <span class="text-[9px] font-black uppercase tracking-widest text-slate-400">Доля в записях</span>
                <span class="text-xs font-bold text-slate-600">{{ formatPercent(service.share_bookings * 100) }}</span>
              </div>
              <TrendingUp v-if="service.share_bookings > 0.1" class="h-4 w-4 text-emerald-500 animate-pulse" />
            </div>
            <div class="h-2.5 w-full overflow-hidden rounded-full bg-slate-100 p-0.5">
              <div 
                class="h-full rounded-full bg-gradient-to-r from-primary to-primary/60 transition-all duration-1000 ease-out shadow-[0_0_8px_rgba(var(--primary-rgb),0.4)]"
                :style="{ width: `${service.share_bookings * 100}%` }"
              />
            </div>
          </div>


          <!-- Metrics Grid -->
          <div class="mt-auto grid grid-cols-2 gap-3">
            <div class="rounded-2xl bg-slate-50/50 p-3 transition-colors group-hover:bg-slate-50">
              <div class="flex items-center gap-2 text-slate-400">
                <CalendarCheck class="h-3.5 w-3.5" />
                <span class="text-[9px] font-bold uppercase tracking-wider">Записи</span>
              </div>
              <p class="mt-1 text-base font-extrabold text-slate-900">{{ formatInt(service.bookings_total) }}</p>
            </div>
            
            <div class="rounded-2xl bg-slate-50/50 p-3 transition-colors group-hover:bg-slate-50">
              <div class="flex items-center gap-2 text-slate-400">
                <UserCheck class="h-3.5 w-3.5" />
                <span class="text-[9px] font-bold uppercase tracking-wider">Визиты</span>
              </div>
              <p class="mt-1 text-base font-extrabold text-slate-900">{{ formatInt(service.arrived_total) }}</p>
            </div>

            <div class="col-span-2 rounded-2xl bg-primary/5 p-3 transition-colors group-hover:bg-primary/10">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-primary/60">
                  <Wallet class="h-3.5 w-3.5" />
                  <span class="text-[9px] font-bold uppercase tracking-wider">Выручка</span>
                </div>
                <p class="text-base font-black text-primary">{{ formatMoney(service.revenue_total) }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div
      v-else
      class="rounded-3xl border-2 border-dashed border-slate-100 bg-white p-12 text-center"
    >
      <div class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-slate-50 text-slate-300">
        <BarChart3 class="h-6 w-6" />
      </div>
      <p class="text-sm font-medium text-slate-500">Нет данных для формирования топа товаров</p>
      <p class="mt-1 text-xs text-slate-400">Попробуйте изменить фильтры или период</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { 
  Trophy, 
  CalendarCheck, 
  UserCheck, 
  Wallet, 
  BarChart3,
  TrendingUp 
} from 'lucide-vue-next'
import type { AnalyticsCommodityTableItem } from '~/types/analytics'

const props = defineProps<{
  items: AnalyticsCommodityTableItem[]
  loading: boolean
}>()

const intFormatter = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })
const moneyFormatter = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
const percentFormatter = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

const formatInt = (value: number) => intFormatter.format(Number.isFinite(value) ? value : 0)
const formatMoney = (value: number) => `${moneyFormatter.format(Number.isFinite(value) ? value : 0)} ₽`
const formatPercent = (value: number) => `${percentFormatter.format(Number.isFinite(value) ? value : 0)}%`

const topItems = computed(() =>
  [...props.items]
    .sort((a, b) => b.bookings_total - a.bookings_total)
    .slice(0, 6),
)
</script>

