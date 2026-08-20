<template>
  <Sheet :open="!!resourceId" @update:open="(v) => !v && $emit('close')">
    <SheetContent side="right" class-name="w-screen sm:max-w-none flex flex-col">
      <SheetHeader>
        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="text-[10px] font-black uppercase tracking-wider text-slate-400">Сотрудник</div>
            <SheetTitle class="mt-1 text-xl font-black text-slate-900">
              {{ detail?.staff.full_name || '—' }}
            </SheetTitle>
            <div v-if="detail?.staff.position" class="text-sm text-slate-400">{{ detail.staff.position }}</div>
          </div>
          <SheetClose />
        </div>
      </SheetHeader>

      <div v-if="loading && !detail" class="flex h-40 items-center justify-center">
        <div class="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
      </div>

      <template v-else-if="detail">
        <div class="flex-1 overflow-y-auto p-6 space-y-6">
          <!-- Мотивация (показывается только когда передан member) -->
          <div v-if="motivation" class="rounded-3xl border border-emerald-100 bg-gradient-to-br from-emerald-50/60 to-white p-5 space-y-4">
            <div class="flex items-center justify-between">
              <div class="text-[10px] font-black uppercase tracking-wider text-emerald-700">Мотивация и бонусы</div>
              <span
                class="inline-block rounded-full px-2 py-0.5 text-[10px] font-black uppercase tracking-wide"
                :class="tierClass(motivation.tier)"
              >{{ tierLabel(motivation.tier) }}</span>
            </div>

            <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
              <div class="rounded-2xl bg-white px-4 py-3 border border-emerald-50">
                <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Бонус первичка</div>
                <div class="mt-1 text-lg font-black tabular-nums text-slate-800">{{ formatMoney(motivation.bonus_primary) }}</div>
              </div>
              <div class="rounded-2xl bg-white px-4 py-3 border border-emerald-50">
                <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Бонус вторичка</div>
                <div class="mt-1 text-lg font-black tabular-nums text-slate-800">{{ formatMoney(motivation.bonus_repeat) }}</div>
              </div>
              <div class="rounded-2xl bg-emerald-100/60 px-4 py-3 border border-emerald-200">
                <div class="text-[9px] font-black uppercase tracking-wider text-emerald-700">Итого к выплате</div>
                <div class="mt-1 text-lg font-black tabular-nums text-emerald-700">{{ formatMoney(motivation.bonus_total) }}</div>
              </div>
              <div class="rounded-2xl bg-white px-4 py-3 border border-emerald-50">
                <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">% перв. / вторич.</div>
                <div class="mt-1 text-lg font-black tabular-nums text-slate-800">{{ motivation.applied_primary_pct }}% / {{ motivation.applied_repeat_pct }}%</div>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3 md:grid-cols-3">
              <div class="rounded-2xl bg-white px-4 py-3 border border-emerald-50">
                <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Услуги</div>
                <div class="mt-1 text-sm font-bold tabular-nums text-slate-700">{{ formatMoney(motivation.services_revenue) }}</div>
              </div>
              <div class="rounded-2xl bg-white px-4 py-3 border border-emerald-50">
                <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Товары</div>
                <div class="mt-1 text-sm font-bold tabular-nums text-slate-700">{{ formatMoney(motivation.commodities_revenue) }}</div>
              </div>
              <div class="rounded-2xl bg-white px-4 py-3 border border-emerald-50">
                <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Итого выручка</div>
                <div class="mt-1 text-sm font-bold tabular-nums text-slate-800">{{ formatMoney(motivation.revenue_total) }}</div>
              </div>
              <div class="rounded-2xl bg-white px-4 py-3 border border-emerald-50">
                <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Ср. чек первички</div>
                <div class="mt-1 text-sm font-bold tabular-nums text-slate-700">{{ formatMoney(motivation.primary_avg_check) }}</div>
              </div>
              <div class="rounded-2xl bg-white px-4 py-3 border border-emerald-50">
                <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Ср. чек вторички</div>
                <div class="mt-1 text-sm font-bold tabular-nums text-slate-700">{{ formatMoney(motivation.repeat_avg_check) }}</div>
              </div>
              <div class="rounded-2xl bg-white px-4 py-3 border border-emerald-50">
                <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Ср. чек общий</div>
                <div class="mt-1 text-sm font-bold tabular-nums text-slate-700">{{ formatMoney(motivation.total_avg_check) }}</div>
              </div>
            </div>
          </div>


          <!-- KPI row -->
          <div class="grid grid-cols-2 gap-3">
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Записей</div>
              <div class="mt-1 text-xl font-black tabular-nums text-slate-900">{{ detail.staff.visits_total }}</div>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Дошли</div>
              <div class="mt-1 text-xl font-black tabular-nums text-slate-900">{{ detail.staff.arrived_total }}</div>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Конверсия</div>
              <div class="mt-1 text-xl font-black tabular-nums" :class="convClass(detail.staff.conversion_pct)">
                {{ detail.staff.conversion_pct }}%
              </div>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Не пришли</div>
              <div class="mt-1 text-xl font-black tabular-nums" :class="noShowClass(detail.staff.no_show_pct)">
                {{ detail.staff.no_show_pct }}%
              </div>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Выручка</div>
              <div class="mt-1 text-xl font-black tabular-nums text-slate-900">{{ formatMoney(detail.staff.revenue_total) }}</div>
            </div>
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Маржа</div>
              <div class="mt-1 text-xl font-black tabular-nums text-slate-900">{{ formatMoney(detail.staff.margin_total) }}</div>
            </div>
          </div>

          <!-- Delta -->
          <div
            v-if="detail.staff.revenue_delta_pct !== null"
            class="flex items-center gap-2 rounded-2xl px-4 py-3"
            :class="detail.staff.revenue_delta_pct >= 0 ? 'bg-emerald-50' : 'bg-rose-50'"
          >
            <TrendingUp v-if="detail.staff.revenue_delta_pct >= 0" class="h-4 w-4 text-emerald-600" />
            <TrendingDown v-else class="h-4 w-4 text-rose-600" />
            <span class="text-sm font-bold" :class="detail.staff.revenue_delta_pct >= 0 ? 'text-emerald-700' : 'text-rose-700'">
              {{ detail.staff.revenue_delta_pct > 0 ? '+' : '' }}{{ detail.staff.revenue_delta_pct }}% к прошлому периоду
            </span>
          </div>

          <!-- Tabs: Услуги / Пациенты -->
          <div class="flex items-center gap-2 border-b border-slate-100">
            <button
              type="button"
              class="px-4 py-2.5 text-xs font-bold uppercase tracking-wider transition"
              :class="activeTab === 'services'
                ? 'text-primary border-b-2 border-primary'
                : 'text-slate-400 hover:text-slate-600'"
              @click="activeTab = 'services'"
            >
              Услуги ({{ detail.top_services?.length ?? 0 }})
            </button>
            <button
              type="button"
              class="px-4 py-2.5 text-xs font-bold uppercase tracking-wider transition"
              :class="activeTab === 'clients'
                ? 'text-primary border-b-2 border-primary'
                : 'text-slate-400 hover:text-slate-600'"
              @click="activeTab = 'clients'"
            >
              Пациенты ({{ detail.clients?.length ?? 0 }})
            </button>
          </div>

          <!-- Услуги: полный список с атрибутами -->
          <div v-if="activeTab === 'services' && detail.top_services?.length">
            <div class="mb-3 flex items-center justify-end">
              <div class="text-[10px] font-medium text-slate-400">Сортировка: по выручке</div>
            </div>
            <div class="rounded-3xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
              <div class="overflow-auto max-h-[70vh]">
                <table class="min-w-full text-xs services-table">
                  <thead class="sticky top-0 z-10 bg-white shadow-[0_1px_0_0_rgb(241_245_249)]">
                    <tr class="border-b border-slate-100 text-left">
                      <th class="bg-white px-4 py-3 text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[260px]">Услуга</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[80px]">Записи</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[80px]">Дошли</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[100px]">Не пришли</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[100px]">Конверсия</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[110px]">% не пришли</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[90px]">Первичных</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[90px]">Вторичных</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[110px]">Ср. чек</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-emerald-600 whitespace-nowrap min-w-[130px]">Выручка</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="svc in detail.top_services"
                      :key="`${svc.service_external_id}-${svc.service_name}`"
                      class="border-b border-slate-50 transition-colors last:border-0 hover:bg-slate-50/60"
                    >
                      <td class="px-4 py-3">
                        <div class="font-semibold text-slate-800" :title="svc.service_name">{{ svc.service_name }}</div>
                      </td>
                      <td class="px-3 py-3 text-right font-mono text-slate-600">{{ svc.bookings_total }}</td>
                      <td class="px-3 py-3 text-right font-mono text-emerald-700">{{ svc.arrived_total }}</td>
                      <td class="px-3 py-3 text-right font-mono text-rose-600">{{ svc.no_show_total }}</td>
                      <td class="px-3 py-3 text-right font-mono font-semibold" :class="convClass(svc.conversion_pct)">{{ svc.conversion_pct }}%</td>
                      <td class="px-3 py-3 text-right font-mono" :class="noShowClass(svc.no_show_pct)">{{ svc.no_show_pct }}%</td>
                      <td class="px-3 py-3 text-right font-mono text-primary">{{ svc.primary_total }}</td>
                      <td class="px-3 py-3 text-right font-mono text-slate-600">{{ svc.repeat_total }}</td>
                      <td class="px-3 py-3 text-right font-mono text-slate-700">{{ formatMoney(svc.avg_check) }}</td>
                      <td class="px-3 py-3 text-right font-mono font-black text-emerald-600">{{ formatMoney(svc.revenue_total) }}</td>
                    </tr>

                    <!-- Totals row -->
                    <tr class="border-t-2 border-slate-200 bg-slate-50/70">
                      <td class="px-4 py-3 text-[10px] font-black uppercase tracking-wider text-slate-500">Итого</td>
                      <td class="px-3 py-3 text-right font-mono font-bold text-slate-700">{{ servicesTotals.bookings }}</td>
                      <td class="px-3 py-3 text-right font-mono font-bold text-emerald-700">{{ servicesTotals.arrived }}</td>
                      <td class="px-3 py-3 text-right font-mono font-bold text-rose-600">{{ servicesTotals.no_show }}</td>
                      <td class="px-3 py-3 text-right font-mono font-bold" :class="convClass(servicesTotals.conversion_pct)">{{ servicesTotals.conversion_pct }}%</td>
                      <td class="px-3 py-3 text-right font-mono font-bold" :class="noShowClass(servicesTotals.no_show_pct)">{{ servicesTotals.no_show_pct }}%</td>
                      <td class="px-3 py-3 text-right font-mono font-bold text-primary">{{ servicesTotals.primary }}</td>
                      <td class="px-3 py-3 text-right font-mono font-bold text-slate-700">{{ servicesTotals.repeat }}</td>
                      <td class="px-3 py-3 text-right font-mono font-bold text-slate-700">{{ formatMoney(servicesTotals.avg_check) }}</td>
                      <td class="px-3 py-3 text-right font-mono font-black text-emerald-700">{{ formatMoney(servicesTotals.revenue) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- Пациенты -->
          <div v-if="activeTab === 'clients' && detail.clients?.length">
            <div class="mb-3 flex items-center justify-end">
              <div class="text-[10px] font-medium text-slate-400">Сортировка: по выручке</div>
            </div>
            <div class="rounded-3xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
              <div class="overflow-auto max-h-[70vh]">
                <table class="min-w-full text-xs services-table">
                  <thead class="sticky top-0 z-10 bg-white shadow-[0_1px_0_0_rgb(241_245_249)]">
                    <tr class="border-b border-slate-100 text-left">
                      <th class="bg-white px-4 py-3 text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[260px]">Пациент</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[140px]">Телефон</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[80px]">Визиты</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[80px]">Дошли</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[100px]">Не пришли</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[90px]">Первичных</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[90px]">Вторичных</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[110px]">Ср. чек</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-emerald-600 whitespace-nowrap min-w-[130px]">Выручка</th>
                      <th class="bg-white px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400 whitespace-nowrap min-w-[140px]">Последний визит</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="cl in detail.clients"
                      :key="cl.client_external_id"
                      class="border-b border-slate-50 transition-colors last:border-0 hover:bg-slate-50/60"
                    >
                      <td class="px-4 py-3">
                        <div class="font-semibold text-slate-800">{{ cl.full_name }}</div>
                      </td>
                      <td class="px-3 py-3 text-right font-mono text-slate-500">{{ cl.phone || '—' }}</td>
                      <td class="px-3 py-3 text-right font-mono text-slate-600">{{ cl.visits_total }}</td>
                      <td class="px-3 py-3 text-right font-mono text-emerald-700">{{ cl.arrived_total }}</td>
                      <td class="px-3 py-3 text-right font-mono text-rose-600">{{ cl.no_show_total }}</td>
                      <td class="px-3 py-3 text-right font-mono text-primary">{{ cl.primary_total }}</td>
                      <td class="px-3 py-3 text-right font-mono text-slate-600">{{ cl.repeat_total }}</td>
                      <td class="px-3 py-3 text-right font-mono text-slate-700">{{ formatMoney(cl.avg_check) }}</td>
                      <td class="px-3 py-3 text-right font-mono font-black text-emerald-600">{{ formatMoney(cl.revenue_total) }}</td>
                      <td class="px-3 py-3 text-right font-mono text-slate-500">{{ formatDate(cl.last_visit_at) }}</td>
                    </tr>

                    <tr class="border-t-2 border-slate-200 bg-slate-50/70">
                      <td class="px-4 py-3 text-[10px] font-black uppercase tracking-wider text-slate-500">Итого</td>
                      <td></td>
                      <td class="px-3 py-3 text-right font-mono font-bold text-slate-700">{{ clientsTotals.visits }}</td>
                      <td class="px-3 py-3 text-right font-mono font-bold text-emerald-700">{{ clientsTotals.arrived }}</td>
                      <td class="px-3 py-3 text-right font-mono font-bold text-rose-600">{{ clientsTotals.no_show }}</td>
                      <td class="px-3 py-3 text-right font-mono font-bold text-primary">{{ clientsTotals.primary }}</td>
                      <td class="px-3 py-3 text-right font-mono font-bold text-slate-700">{{ clientsTotals.repeat }}</td>
                      <td class="px-3 py-3 text-right font-mono font-bold text-slate-700">{{ formatMoney(clientsTotals.avg_check) }}</td>
                      <td class="px-3 py-3 text-right font-mono font-black text-emerald-700">{{ formatMoney(clientsTotals.revenue) }}</td>
                      <td></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div v-if="activeTab === 'clients' && !detail.clients?.length" class="rounded-2xl bg-slate-50 px-4 py-8 text-center text-sm text-slate-400">
            Нет пациентов за период
          </div>

          <!-- Primary vs repeat split -->
          <div v-if="detail.staff.visits_total > 0">
            <div class="mb-3 text-[10px] font-black uppercase tracking-wider text-slate-400">Новые / повторные</div>
            <div class="grid grid-cols-3 gap-2">
              <div class="rounded-xl bg-primary/10 px-3 py-3 text-center">
                <div class="text-lg font-black text-primary">{{ detail.staff.primary_total }}</div>
                <div class="text-[10px] font-bold uppercase tracking-wide text-primary/70">Первичные</div>
                <div class="mt-0.5 text-[10px] font-medium text-primary/60">
                  {{ Math.round((detail.staff.primary_total / detail.staff.visits_total) * 100) }}% от всех
                </div>
              </div>
              <div class="rounded-xl bg-emerald-50 px-3 py-3 text-center">
                <div class="text-lg font-black text-emerald-700">
                  {{ detail.staff.primary_total > 0
                    ? Math.round((detail.staff.primary_arrived / detail.staff.primary_total) * 100)
                    : 0 }}%
                </div>
                <div class="text-[10px] font-bold uppercase tracking-wide text-emerald-700/70">Конв. перв.</div>
                <div class="mt-0.5 text-[10px] font-medium text-emerald-700/60">
                  {{ detail.staff.primary_arrived }} из {{ detail.staff.primary_total }} дошли
                </div>
              </div>
              <div class="rounded-xl bg-slate-50 px-3 py-3 text-center">
                <div class="text-lg font-black text-slate-700">{{ detail.staff.repeat_total }}</div>
                <div class="text-[10px] font-bold uppercase tracking-wide text-slate-400">Вторичные</div>
                <div class="mt-0.5 text-[10px] font-medium text-slate-400">
                  {{ Math.round((detail.staff.repeat_total / detail.staff.visits_total) * 100) }}% от всех
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <div v-else-if="!loading" class="p-10 text-center text-sm text-slate-400">
        Нет данных за выбранный период.
      </div>
    </SheetContent>
  </Sheet>
</template>

<script setup lang="ts">
import { watch, ref, computed } from 'vue'
import { TrendingUp, TrendingDown } from 'lucide-vue-next'
import { Sheet, SheetClose, SheetContent, SheetHeader, SheetTitle } from '~/components/ui/sheet'
import { useAnalyticsApi } from '~/composables/analyticsApi'
import type { MotivationMember, MotivationTier, StaffDetailResponse } from '~/types/analytics'

const props = defineProps<{
  resourceId: number | null
  agentId: string | null
  dateFrom: string
  dateTo: string
  timezone: string
  motivation?: MotivationMember | null
}>()

defineEmits<{ (e: 'close'): void }>()

const api = useAnalyticsApi()
const detail = ref<StaffDetailResponse | null>(null)
const loading = ref(false)
const activeTab = ref<'services' | 'clients'>('services')

watch(() => props.resourceId, async (id) => {
  if (!id || !props.agentId) { detail.value = null; return }
  activeTab.value = 'services'
  loading.value = true
  try {
    detail.value = await api.getStaffDetail(props.agentId, id, {
      dateFrom: props.dateFrom,
      dateTo: props.dateTo,
      timezone: props.timezone,
    })
  } finally {
    loading.value = false
  }
})

const servicesTotals = computed(() => {
  const list = detail.value?.top_services ?? []
  const sum = list.reduce(
    (acc, s) => {
      acc.bookings += s.bookings_total
      acc.arrived += s.arrived_total
      acc.no_show += s.no_show_total
      acc.primary += s.primary_total
      acc.repeat += s.repeat_total
      acc.revenue += s.revenue_total
      return acc
    },
    { bookings: 0, arrived: 0, no_show: 0, primary: 0, repeat: 0, revenue: 0 },
  )
  return {
    ...sum,
    conversion_pct: sum.bookings ? Math.round((sum.arrived / sum.bookings) * 1000) / 10 : 0,
    no_show_pct: sum.bookings ? Math.round((sum.no_show / sum.bookings) * 1000) / 10 : 0,
    avg_check: sum.arrived ? Math.round((sum.revenue / sum.arrived) * 100) / 100 : 0,
  }
})

const clientsTotals = computed(() => {
  const list = detail.value?.clients ?? []
  const sum = list.reduce(
    (acc, c) => {
      acc.visits += c.visits_total
      acc.arrived += c.arrived_total
      acc.no_show += c.no_show_total
      acc.primary += c.primary_total
      acc.repeat += c.repeat_total
      acc.revenue += c.revenue_total
      return acc
    },
    { visits: 0, arrived: 0, no_show: 0, primary: 0, repeat: 0, revenue: 0 },
  )
  return {
    ...sum,
    avg_check: sum.visits ? Math.round((sum.revenue / sum.visits) * 100) / 100 : 0,
  }
})

const dateFormatter = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})
const formatDate = (s: string | null) => {
  if (!s) return '—'
  const d = new Date(s)
  return Number.isNaN(d.getTime()) ? '—' : dateFormatter.format(d)
}

const moneyFormatter = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})

const formatMoney = (v: number) => {
  if (v === null || v === undefined) return '—'
  return moneyFormatter.format(Number.isFinite(v) ? v : 0) + ' ₽'
}

const convClass = (v: number) => v >= 80 ? 'text-emerald-600' : v >= 60 ? 'text-slate-700' : 'text-rose-600'
const noShowClass = (v: number) => v >= 25 ? 'text-rose-600' : v >= 15 ? 'text-amber-600' : 'text-emerald-600'

const tierLabel = (tier: MotivationTier): string => ({
  low: 'Ниже нормы',
  norm: 'Норма',
  high: 'Бонус',
  no_primary: 'Нет первичных',
} as Record<MotivationTier, string>)[tier]

const tierClass = (tier: MotivationTier): string => ({
  low: 'bg-rose-100 text-rose-700',
  norm: 'bg-slate-100 text-slate-600',
  high: 'bg-emerald-100 text-emerald-700',
  no_primary: 'bg-sky-100 text-sky-600',
} as Record<MotivationTier, string>)[tier]
</script>

<style scoped>
.services-table {
  table-layout: fixed;
  width: max-content;
}
.services-table th {
  position: relative;
  resize: horizontal;
  overflow: auto;
}
.services-table td {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.services-table td:first-child {
  white-space: normal;
}
</style>
