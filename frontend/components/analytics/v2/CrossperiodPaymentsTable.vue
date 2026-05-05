<template>
  <div class="rounded-3xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
    <!-- Toolbar: totals pills + direction filter -->
    <div v-if="totals" class="flex flex-wrap items-center gap-2 border-b border-slate-100 px-5 py-4">
      <div
        class="cursor-pointer rounded-2xl px-3 py-2 text-sm transition-colors"
        :class="directionFilter === '' ? 'bg-slate-900 text-white' : 'bg-slate-50 text-slate-600 hover:bg-slate-100'"
        @click="directionFilter = ''"
      >
        <span class="text-[9px] font-black uppercase tracking-wider block leading-none mb-0.5" :class="directionFilter === '' ? 'text-white/60' : 'text-slate-400'">Всего</span>
        <span class="font-black tabular-nums">{{ fmtMoney(totals.amount_total) }}</span>
      </div>
      <div
        v-if="totals.amount_past > 0"
        class="cursor-pointer rounded-2xl px-3 py-2 text-sm transition-colors"
        :class="directionFilter === 'past' ? 'bg-amber-600 text-white' : 'bg-amber-50 text-amber-700 hover:bg-amber-100'"
        @click="directionFilter = directionFilter === 'past' ? '' : 'past'"
      >
        <span class="text-[9px] font-black uppercase tracking-wider block leading-none mb-0.5 opacity-70">Долги (прошлые)</span>
        <span class="font-black tabular-nums">{{ fmtMoney(totals.amount_past) }}</span>
      </div>
      <div
        v-if="totals.amount_future > 0"
        class="cursor-pointer rounded-2xl px-3 py-2 text-sm transition-colors"
        :class="directionFilter === 'future' ? 'bg-emerald-600 text-white' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'"
        @click="directionFilter = directionFilter === 'future' ? '' : 'future'"
      >
        <span class="text-[9px] font-black uppercase tracking-wider block leading-none mb-0.5 opacity-70">Авансы (будущие)</span>
        <span class="font-black tabular-nums">{{ fmtMoney(totals.amount_future) }}</span>
      </div>
      <div
        v-if="totals.amount_unknown > 0"
        class="cursor-pointer rounded-2xl px-3 py-2 text-sm transition-colors"
        :class="directionFilter === 'unknown' ? 'bg-slate-700 text-white' : 'bg-slate-50 text-slate-500 hover:bg-slate-100'"
        @click="directionFilter = directionFilter === 'unknown' ? '' : 'unknown'"
      >
        <span class="text-[9px] font-black uppercase tracking-wider block leading-none mb-0.5 opacity-70">Без визита</span>
        <span class="font-black tabular-nums">{{ fmtMoney(totals.amount_unknown) }}</span>
      </div>
      <div class="ml-auto text-[10px] text-slate-400">
        {{ totals.clients_unique }} клиент{{ plural(totals.clients_unique, 'а', 'ов', '') }}
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex h-32 items-center justify-center">
      <div class="h-7 w-7 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
    </div>

    <!-- Empty -->
    <div v-else-if="items.length === 0" class="px-5 py-10 text-center text-sm text-slate-400">
      Нет платежей за визиты других периодов в выбранном периоде
    </div>

    <!-- Table -->
    <div v-else class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-slate-100 text-left">
            <th
              v-for="col in columns"
              :key="col.key"
              class="cursor-pointer select-none px-4 py-3 text-[9px] font-black uppercase tracking-wider text-slate-400 hover:text-slate-700 whitespace-nowrap"
              :class="col.align === 'right' ? 'text-right' : ''"
              @click="col.sortable ? setSort(col.key as CrossperiodPaymentsSortBy) : undefined"
            >
              {{ col.label }}
              <span v-if="sortBy === col.key" class="ml-0.5">{{ sortOrder === 'desc' ? '↓' : '↑' }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in items"
            :key="item.payment_external_id"
            class="border-b border-slate-50 hover:bg-slate-50/60 transition-colors"
          >
            <!-- Клиент -->
            <td class="px-4 py-3">
              <button
                v-if="item.client_external_id"
                class="text-left group"
                @click="$emit('open-client', item.client_external_id)"
              >
                <div class="font-semibold text-slate-800 group-hover:text-primary transition-colors">
                  {{ item.client_name || 'Клиент #' + item.client_external_id }}
                </div>
                <div class="text-[10px] text-slate-400">ID {{ item.client_external_id }}</div>
              </button>
              <span v-else class="text-slate-400">—</span>
            </td>
            <!-- Сумма -->
            <td class="px-4 py-3 text-right tabular-nums font-semibold text-slate-800 whitespace-nowrap">
              {{ fmtMoney(item.amount) }}
            </td>
            <!-- Дата оплаты -->
            <td class="px-4 py-3 whitespace-nowrap text-slate-600 tabular-nums">
              {{ fmtDate(item.payment_date) }}
            </td>
            <!-- Дата визита + бейдж -->
            <td class="px-4 py-3 whitespace-nowrap">
              <template v-if="item.visit_date">
                <span class="tabular-nums text-slate-600">{{ fmtDate(item.visit_date) }}</span>
                <span
                  class="ml-1.5 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold"
                  :class="directionClass(item.direction)"
                >{{ directionLabel(item.direction) }}</span>
              </template>
              <span v-else class="text-slate-400">—</span>
            </td>
            <!-- Расхождение -->
            <td class="px-4 py-3 whitespace-nowrap tabular-nums text-slate-500 text-xs">
              <template v-if="item.days_gap !== null">
                <span :class="item.days_gap < 0 ? 'text-amber-600' : 'text-emerald-600'">
                  {{ item.days_gap > 0 ? '+' : '' }}{{ item.days_gap }} дн
                </span>
              </template>
              <span v-else class="text-slate-300">—</span>
            </td>
            <!-- Способ оплаты -->
            <td class="px-4 py-3 whitespace-nowrap text-slate-500 text-xs">
              {{ methodLabel(item.payment_method) }}
            </td>
            <!-- Тип платежа -->
            <td class="px-4 py-3 text-slate-500 text-xs max-w-[140px] truncate">
              {{ item.payment_type_name || '—' }}
            </td>
            <!-- Специалист -->
            <td class="px-4 py-3 text-slate-600 text-xs whitespace-nowrap">
              {{ item.resource_name || '—' }}
            </td>
            <!-- Дошёл -->
            <td class="px-4 py-3 text-center">
              <span v-if="item.visit_attendance === 1" class="text-emerald-500 font-bold text-xs">✓</span>
              <span v-else-if="item.visit_attendance === 0" class="text-rose-400 text-xs font-bold">✗</span>
              <span v-else class="text-slate-300 text-xs">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex items-center justify-between border-t border-slate-100 px-5 py-3">
      <span class="text-xs text-slate-400">Страница {{ currentPage + 1 }} из {{ totalPages }}</span>
      <div class="flex gap-2">
        <button
          :disabled="currentPage === 0"
          class="rounded-xl px-3 py-1.5 text-xs font-semibold disabled:opacity-30 bg-slate-100 hover:bg-slate-200 transition-colors"
          @click="setPage(currentPage - 1)"
        >←</button>
        <button
          :disabled="currentPage >= totalPages - 1"
          class="rounded-xl px-3 py-1.5 text-xs font-semibold disabled:opacity-30 bg-slate-100 hover:bg-slate-200 transition-colors"
          @click="setPage(currentPage + 1)"
        >→</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AnalyticsFilters, CrossperiodPaymentsSortBy } from '~/types/analytics'
import { useCrossperiodPaymentsTable } from '~/composables/useCrossperiodPaymentsTable'

const props = defineProps<{
  agentId: string
  filters: AnalyticsFilters
  enabled: boolean
}>()

const emit = defineEmits<{
  (e: 'open-client', clientExternalId: string): void
}>()

const enabledRef = computed(() => props.enabled)

const {
  loading,
  items,
  totals,
  sortBy,
  sortOrder,
  currentPage,
  totalPages,
  directionFilter,
  setSort,
  setPage,
} = useCrossperiodPaymentsTable(props.filters, enabledRef)

const columns = [
  { key: 'client_name', label: 'Клиент', sortable: true, align: 'left' },
  { key: 'amount', label: 'Сумма', sortable: true, align: 'right' },
  { key: 'payment_date', label: 'Дата оплаты', sortable: true, align: 'left' },
  { key: 'visit_date', label: 'Дата визита', sortable: true, align: 'left' },
  { key: 'days_gap', label: 'Расхождение', sortable: true, align: 'left' },
  { key: 'payment_method', label: 'Оплата', sortable: false, align: 'left' },
  { key: 'payment_type', label: 'Тип', sortable: false, align: 'left' },
  { key: 'resource', label: 'Специалист', sortable: false, align: 'left' },
  { key: 'attendance', label: 'Дошёл', sortable: false, align: 'center' },
]

const fmt = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })
const fmtMoney = (v: number) => {
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + ' млн ₽'
  if (v >= 10_000) return Math.round(v / 1000) + ' тыс ₽'
  return fmt.format(Math.round(v)) + ' ₽'
}

const fmtDate = (iso: string | null) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

const methodLabel = (m: string | null) => {
  if (!m) return '—'
  const map: Record<string, string> = { cash: 'Наличные', card: 'Карта', certificate: 'Сертификат' }
  return map[m.toLowerCase()] ?? m
}

const directionLabel = (d: string) => {
  if (d === 'past') return 'прошлый'
  if (d === 'future') return 'будущий'
  return '?'
}

const directionClass = (d: string) => {
  if (d === 'past') return 'bg-amber-100 text-amber-700'
  if (d === 'future') return 'bg-emerald-100 text-emerald-700'
  return 'bg-slate-100 text-slate-500'
}

const plural = (n: number, f2: string, f5: string, f1: string) => {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod100 >= 11 && mod100 <= 19) return f5
  if (mod10 === 1) return f1
  if (mod10 >= 2 && mod10 <= 4) return f2
  return f5
}
</script>
