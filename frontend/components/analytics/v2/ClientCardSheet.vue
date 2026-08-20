<template>
  <Sheet :open="isOpen" @update:open="(v) => !v && close()">
    <SheetContent side="right" class="w-[90vw] sm:max-w-[90vw] overflow-y-auto p-0">
      <!-- Loading -->
      <div v-if="loading && !data" class="flex h-40 items-center justify-center">
        <div class="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
      </div>

      <div v-else-if="error" class="flex h-40 items-center justify-center text-sm text-rose-500">
        {{ error }}
      </div>

      <template v-else-if="data">
        <!-- Header -->
        <div class="border-b border-slate-100 px-6 py-5">
          <div class="text-[10px] font-black uppercase tracking-wider text-slate-400">Пациент</div>
          <div class="mt-1 text-xl font-black text-slate-900">
            {{ data.full_name || 'Клиент #' + data.client_external_id }}
          </div>
          <div class="mt-1.5 flex flex-wrap items-center gap-2">
            <a
              v-if="data.phone"
              :href="`tel:${data.phone}`"
              class="text-sm text-primary hover:underline font-medium"
            >{{ data.phone }}</a>
            <span v-if="data.email" class="text-sm text-slate-500">{{ data.email }}</span>
            <span
              v-if="data.client_type"
              class="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold"
              :class="clientTypeClass(data.client_type)"
            >{{ clientTypeLabel(data.client_type) }}</span>
            <span
              v-for="tag in data.tags"
              :key="tag"
              class="inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600"
            >{{ tag }}</span>
          </div>
        </div>

        <!-- KPI row -->
        <div class="grid grid-cols-2 gap-3 p-6 sm:grid-cols-3 lg:grid-cols-5">
          <div class="rounded-2xl bg-slate-50 px-4 py-3">
            <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Визитов</div>
            <div class="mt-1 text-lg font-black tabular-nums text-slate-900">{{ data.visits_count }}</div>
          </div>
          <div class="rounded-2xl bg-slate-50 px-4 py-3">
            <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Дошёл</div>
            <div class="mt-1 text-lg font-black tabular-nums text-emerald-600">{{ data.arrived_count }}</div>
          </div>
          <div class="rounded-2xl bg-slate-50 px-4 py-3">
            <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Не пришли</div>
            <div class="mt-1 text-lg font-black tabular-nums" :class="data.no_show_pct > 30 ? 'text-rose-500' : 'text-slate-700'">
              {{ data.no_show_pct }}%
            </div>
          </div>
          <div class="rounded-2xl bg-emerald-50 px-4 py-3">
            <div class="text-[9px] font-black uppercase tracking-wider text-emerald-500">LTV</div>
            <div class="mt-1 text-lg font-black tabular-nums text-emerald-700">{{ fmtMoney(data.lifetime_revenue) }}</div>
          </div>
          <div class="rounded-2xl bg-slate-50 px-4 py-3">
            <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Средний чек</div>
            <div class="mt-1 text-lg font-black tabular-nums text-slate-800">{{ fmtMoney(data.avg_check) }}</div>
          </div>
        </div>

        <!-- Top services / resources -->
        <div v-if="data.top_services.length || data.top_resources.length" class="border-t border-slate-100 px-6 py-4 space-y-3">
          <div v-if="data.top_services.length">
            <div class="text-[9px] font-black uppercase tracking-wider text-slate-400 mb-2">Топ услуг</div>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="s in data.top_services"
                :key="s.name"
                class="inline-flex items-center gap-1 rounded-full bg-primary/5 px-2.5 py-1 text-xs font-medium text-primary"
              >
                {{ s.name }}
                <span class="rounded-full bg-primary/10 px-1 text-[10px] font-bold">{{ s.count }}</span>
              </span>
            </div>
          </div>
          <div v-if="data.top_resources.length">
            <div class="text-[9px] font-black uppercase tracking-wider text-slate-400 mb-2">Специалисты</div>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="r in data.top_resources"
                :key="r.name"
                class="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600"
              >
                {{ r.name }}
                <span class="rounded-full bg-slate-200 px-1 text-[10px] font-bold">{{ r.count }}</span>
              </span>
            </div>
          </div>
        </div>

        <!-- Tabs: Визиты / Платежи -->
        <div class="border-t border-slate-100">
          <div class="flex border-b border-slate-100">
            <button
              v-for="tab in ['visits', 'payments']"
              :key="tab"
              class="flex-1 py-3 text-sm font-bold transition-colors"
              :class="activeTab === tab ? 'border-b-2 border-primary text-primary' : 'text-slate-400 hover:text-slate-700'"
              @click="activeTab = tab as 'visits' | 'payments'"
            >{{ tab === 'visits' ? `Визиты (${data.visits.length})` : `Платежи (${data.payments.length})` }}</button>
          </div>

          <!-- Визиты -->
          <div v-if="activeTab === 'visits'" class="overflow-x-auto">
            <table class="w-full text-xs">
              <thead>
                <tr class="border-b border-slate-100">
                  <th class="px-4 py-2.5 text-left font-black uppercase tracking-wider text-[9px] text-slate-400">Дата</th>
                  <th class="px-4 py-2.5 text-left font-black uppercase tracking-wider text-[9px] text-slate-400">Статус</th>
                  <th class="px-4 py-2.5 text-left font-black uppercase tracking-wider text-[9px] text-slate-400">Специалист</th>
                  <th class="px-4 py-2.5 text-left font-black uppercase tracking-wider text-[9px] text-slate-400">Услуги</th>
                  <th class="px-4 py-2.5 text-right font-black uppercase tracking-wider text-[9px] text-slate-400">Цена</th>
                  <th class="px-4 py-2.5 text-right font-black uppercase tracking-wider text-[9px] text-slate-400">Оплачено</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="v in data.visits"
                  :key="v.visit_external_id"
                  class="border-b border-slate-50 hover:bg-slate-50/50 transition-colors"
                  :class="v.paid_amount < v.total_price && v.total_price > 0 ? 'bg-amber-50/30' : ''"
                >
                  <td class="px-4 py-2.5 tabular-nums text-slate-700 whitespace-nowrap">{{ fmtDate(v.visit_datetime) }}</td>
                  <td class="px-4 py-2.5">
                    <span class="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold" :class="statusClass(v.status)">
                      {{ statusLabel(v.status) }}
                    </span>
                  </td>
                  <td class="px-4 py-2.5 text-slate-600 whitespace-nowrap">{{ v.resource_name || '—' }}</td>
                  <td class="px-4 py-2.5 text-slate-500 max-w-[160px]">
                    <span v-if="v.services.length">{{ v.services.join(', ') }}</span>
                    <span v-else class="text-slate-300">—</span>
                  </td>
                  <td class="px-4 py-2.5 text-right tabular-nums text-slate-700 whitespace-nowrap">
                    {{ v.total_price > 0 ? fmtMoney(v.total_price) : '—' }}
                  </td>
                  <td class="px-4 py-2.5 text-right tabular-nums whitespace-nowrap" :class="v.paid_amount < v.total_price && v.total_price > 0 ? 'text-amber-600 font-semibold' : 'text-slate-700'">
                    {{ v.paid_amount > 0 ? fmtMoney(v.paid_amount) : '—' }}
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!data.visits.length" class="py-8 text-center text-sm text-slate-400">Визиты не найдены</div>
          </div>

          <!-- Платежи -->
          <div v-if="activeTab === 'payments'" class="overflow-x-auto">
            <table class="w-full text-xs">
              <thead>
                <tr class="border-b border-slate-100">
                  <th class="px-4 py-2.5 text-left font-black uppercase tracking-wider text-[9px] text-slate-400">Дата оплаты</th>
                  <th class="px-4 py-2.5 text-right font-black uppercase tracking-wider text-[9px] text-slate-400">Сумма</th>
                  <th class="px-4 py-2.5 text-left font-black uppercase tracking-wider text-[9px] text-slate-400">Способ</th>
                  <th class="px-4 py-2.5 text-left font-black uppercase tracking-wider text-[9px] text-slate-400">Тип</th>
                  <th class="px-4 py-2.5 text-left font-black uppercase tracking-wider text-[9px] text-slate-400">Дата визита</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="p in data.payments"
                  :key="p.payment_external_id"
                  class="border-b border-slate-50 hover:bg-slate-50/50 transition-colors"
                >
                  <td class="px-4 py-2.5 tabular-nums text-slate-700 whitespace-nowrap">{{ fmtDate(p.payment_date) }}</td>
                  <td class="px-4 py-2.5 text-right tabular-nums font-semibold text-slate-800 whitespace-nowrap">{{ fmtMoney(p.amount) }}</td>
                  <td class="px-4 py-2.5 text-slate-500">{{ methodLabel(p.payment_method) }}</td>
                  <td class="px-4 py-2.5 text-slate-500 max-w-[140px] truncate">{{ p.payment_type_name || '—' }}</td>
                  <td class="px-4 py-2.5 whitespace-nowrap">
                    <template v-if="p.visit_datetime">
                      <span class="tabular-nums text-slate-600">{{ fmtDate(p.visit_datetime) }}</span>
                    </template>
                    <span v-else class="text-slate-300">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!data.payments.length" class="py-8 text-center text-sm text-slate-400">Платежи не найдены</div>
          </div>
        </div>

        <!-- First / last visit info -->
        <div v-if="data.first_visit_at || data.last_visit_at" class="border-t border-slate-100 px-6 py-4 flex gap-4 text-xs text-slate-400">
          <span v-if="data.first_visit_at">Первый визит: <b class="text-slate-600">{{ fmtDate(data.first_visit_at) }}</b></span>
          <span v-if="data.last_visit_at">Последний: <b class="text-slate-600">{{ fmtDate(data.last_visit_at) }}</b></span>
        </div>
      </template>
    </SheetContent>
  </Sheet>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Sheet, SheetContent } from '~/components/ui/sheet'
import type { AnalyticsClientCardResponse } from '~/types/analytics'

const props = defineProps<{
  isOpen: boolean
  data: AnalyticsClientCardResponse | null
  loading: boolean
  error: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const close = () => emit('close')

const activeTab = ref<'visits' | 'payments'>('visits')

const fmt = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })
const fmtMoneyFormatter = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
const fmtMoney = (v: number) => fmtMoneyFormatter.format(Number.isFinite(v) ? v : 0) + ' ₽'
const fmtDate = (iso: string | null) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
}
const methodLabel = (m: string | null) => {
  if (!m) return '—'
  const map: Record<string, string> = { cash: 'Наличные', card: 'Карта', certificate: 'Сертификат' }
  return map[m.toLowerCase()] ?? m
}
const statusLabel = (s: string) => {
  const map: Record<string, string> = { arrived: 'Дошёл', no_show: 'Не пришёл', cancelled: 'Отменён', planned: 'Запись' }
  return map[s] ?? s
}
const statusClass = (s: string) => {
  if (s === 'arrived') return 'bg-emerald-100 text-emerald-700'
  if (s === 'no_show') return 'bg-rose-100 text-rose-600'
  if (s === 'cancelled') return 'bg-slate-100 text-slate-500'
  return 'bg-blue-100 text-blue-600'
}
const clientTypeLabel = (t: string) => {
  const map: Record<string, string> = { primary: 'Первичный', repeat: 'Повторный', loyal: 'Лояльный' }
  return map[t.toLowerCase()] ?? t
}
const clientTypeClass = (t: string) => {
  if (t?.toLowerCase() === 'primary') return 'bg-blue-100 text-blue-700'
  if (t?.toLowerCase() === 'repeat') return 'bg-purple-100 text-purple-700'
  return 'bg-slate-100 text-slate-600'
}
</script>
