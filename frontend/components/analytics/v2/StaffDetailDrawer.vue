<template>
  <Sheet :open="!!resourceId" @update:open="(v) => !v && $emit('close')">
    <SheetContent side="right" class="w-full max-w-xl overflow-y-auto p-0">
      <div v-if="loading && !detail" class="flex h-40 items-center justify-center">
        <div class="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
      </div>

      <template v-else-if="detail">
        <!-- Header -->
        <div class="border-b border-slate-100 px-6 py-5">
          <div class="text-[10px] font-black uppercase tracking-wider text-slate-400">Сотрудник</div>
          <div class="mt-1 text-xl font-black text-slate-900">{{ detail.staff.full_name }}</div>
          <div v-if="detail.staff.position" class="text-sm text-slate-400">{{ detail.staff.position }}</div>
        </div>

        <div class="space-y-6 p-6">
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

          <!-- Services table -->
          <div v-if="detail.top_services?.length">
            <div class="mb-3 text-[10px] font-black uppercase tracking-wider text-slate-400">
              Услуги ({{ detail.top_services.length }})
            </div>
            <div class="overflow-x-auto rounded-2xl border border-slate-100">
              <table class="w-full text-xs">
                <thead>
                  <tr class="border-b border-slate-100 bg-slate-50/60">
                    <th class="px-3 py-2 text-left text-[10px] font-black uppercase tracking-wider text-slate-400">Услуга</th>
                    <th class="px-2 py-2 text-right text-[10px] font-black uppercase tracking-wider text-slate-400">Всего</th>
                    <th class="px-2 py-2 text-right text-[10px] font-black uppercase tracking-wider text-primary/70">Перв.</th>
                    <th class="px-2 py-2 text-right text-[10px] font-black uppercase tracking-wider text-slate-400">Вторич.</th>
                    <th class="px-2 py-2 text-right text-[10px] font-black uppercase tracking-wider text-slate-400">Ср. цена</th>
                    <th class="px-3 py-2 text-right text-[10px] font-black uppercase tracking-wider text-slate-400">Выручка</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="svc in detail.top_services"
                    :key="svc.service_name"
                    class="border-b border-slate-50 last:border-0 hover:bg-slate-50/50"
                  >
                    <td class="px-3 py-2 font-medium text-slate-700">{{ svc.service_name }}</td>
                    <td class="px-2 py-2 text-right font-mono text-slate-600">{{ svc.bookings_total }}</td>
                    <td class="px-2 py-2 text-right font-mono font-semibold text-primary">{{ svc.primary_count }}</td>
                    <td class="px-2 py-2 text-right font-mono text-slate-500">{{ svc.repeat_count }}</td>
                    <td class="px-2 py-2 text-right font-mono text-slate-500">{{ formatMoney(svc.avg_price) }}</td>
                    <td class="px-3 py-2 text-right font-mono font-bold text-slate-800">{{ formatMoney(svc.revenue_total) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
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
                <div class="text-[10px] font-bold uppercase tracking-wide text-slate-400">Повторные</div>
                <div class="mt-0.5 text-[10px] font-medium text-slate-400">
                  {{ Math.round((detail.staff.repeat_total / detail.staff.visits_total) * 100) }}% от всех
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <div v-else class="p-10 text-center text-sm text-slate-400">
        Нет данных за выбранный период.
      </div>
    </SheetContent>
  </Sheet>
</template>

<script setup lang="ts">
import { watch, ref } from 'vue'
import { TrendingUp, TrendingDown } from 'lucide-vue-next'
import { Sheet, SheetContent } from '~/components/ui/sheet'
import { useAnalyticsApi } from '~/composables/analyticsApi'
import type { StaffDetailResponse } from '~/types/analytics'

const props = defineProps<{
  resourceId: number | null
  agentId: string | null
  dateFrom: string
  dateTo: string
  timezone: string
}>()

defineEmits<{ (e: 'close'): void }>()

const api = useAnalyticsApi()
const detail = ref<StaffDetailResponse | null>(null)
const loading = ref(false)

watch(() => props.resourceId, async (id) => {
  if (!id || !props.agentId) { detail.value = null; return }
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

const formatMoney = (v: number) => {
  if (!v && v !== 0) return '—'
  if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(1) + ' млн ₽'
  if (Math.abs(v) >= 10_000) return Math.round(v / 1000) + ' тыс ₽'
  return Math.round(v).toLocaleString('ru-RU') + ' ₽'
}

const convClass = (v: number) => v >= 80 ? 'text-emerald-600' : v >= 60 ? 'text-slate-700' : 'text-rose-600'
const noShowClass = (v: number) => v >= 25 ? 'text-rose-600' : v >= 15 ? 'text-amber-600' : 'text-emerald-600'
</script>
