<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-bold uppercase tracking-widest text-slate-400">Топ категорий товаров</h3>
      <div v-if="topCategories.length" class="text-[11px] font-medium text-slate-400">
        Показаны первые {{ topCategories.length }} категорий
      </div>
    </div>

    <div v-if="loading && !items.length" class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="index in 3"
        :key="index"
        class="h-[240px] rounded-3xl border border-slate-100 bg-white p-6 shadow-sm animate-pulse"
      />
    </div>

    <div
      v-else-if="topCategories.length"
      class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3"
    >
      <div
        v-for="(category, index) in topCategories"
        :key="category.name"
        class="group relative flex flex-col overflow-hidden rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1.5 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
      >
        <!-- Background Accent -->
        <div 
          class="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-emerald-500/5 transition-transform duration-700 group-hover:scale-150"
        />

        <div class="relative flex h-full flex-col">
          <!-- Header -->
          <div class="mb-5 flex items-start justify-between">
            <div class="flex flex-col gap-1">
              <div 
                class="inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold tracking-wider uppercase transition-colors"
                :class="[
                  index === 0 ? 'bg-emerald-100 text-emerald-700' : 
                  index === 1 ? 'bg-slate-100 text-slate-600' : 
                  index === 2 ? 'bg-teal-100 text-teal-700' : 'bg-slate-50 text-slate-500'
                ]"
              >
                <Trophy v-if="index < 3" class="mr-1 h-3 w-3" />
                Место {{ index + 1 }}
              </div>
            </div>
            
            <div class="flex flex-col items-end gap-1">
              <div class="text-lg font-black text-emerald-600">
                {{ formatPercent(category.share * 100) }}
              </div>
              <div class="text-[9px] font-bold uppercase tracking-tighter text-slate-300">Доля</div>
            </div>
          </div>

          <!-- Title -->
          <div class="group/title relative mb-6">
            <h4 class="line-clamp-1 text-lg font-bold leading-tight text-slate-900 group-hover:text-emerald-600 transition-colors">
              {{ category.name }}
            </h4>
            <p class="text-[10px] font-medium text-slate-400 mt-1">
              {{ category.services_count }} товаров в категории
            </p>
          </div>

          <!-- Progress Bar -->
          <div class="mb-6 space-y-2">
            <div class="h-2 w-full overflow-hidden rounded-full bg-slate-100 p-0.5">
              <div 
                class="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all duration-1000 ease-out shadow-[0_0_8px_rgba(16,185,129,0.3)]"
                :style="{ width: `${category.share * 100}%` }"
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
              <p class="mt-1 text-base font-extrabold text-slate-900">{{ formatInt(category.bookings_total) }}</p>
            </div>
            
            <div class="rounded-2xl bg-slate-50/50 p-3 transition-colors group-hover:bg-slate-50">
              <div class="flex items-center gap-2 text-slate-400">
                <Wallet class="h-3.5 w-3.5" />
                <span class="text-[9px] font-bold uppercase tracking-wider">Выручка</span>
              </div>
              <p class="mt-1 text-base font-extrabold text-slate-900">{{ formatMoney(category.revenue_total) }}</p>
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
        <LayoutGrid class="h-6 w-6" />
      </div>
      <p class="text-sm font-medium text-slate-500">Нет данных для формирования топа категорий товаров</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { 
  Trophy, 
  CalendarCheck, 
  Wallet, 
  LayoutGrid
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

const topCategories = computed(() => {
  const categoriesMap = new Map<string, {
    name: string
    bookings_total: number
    revenue_total: number
    services_count: number
  }>()

  let totalBookings = 0

  props.items.forEach(item => {
    const catName = item.commodity_category || 'Без категории'
    const existing = categoriesMap.get(catName) || {
      name: catName,
      bookings_total: 0,
      revenue_total: 0,
      services_count: 0
    }

    existing.bookings_total += item.bookings_total
    existing.revenue_total += item.revenue_total
    existing.services_count += 1
    totalBookings += item.bookings_total

    categoriesMap.set(catName, existing)
  })

  return Array.from(categoriesMap.values())
    .map(cat => ({
      ...cat,
      share: totalBookings > 0 ? cat.bookings_total / totalBookings : 0
    }))
    .sort((a, b) => b.bookings_total - a.bookings_total)
    .slice(0, 6)
})
</script>
