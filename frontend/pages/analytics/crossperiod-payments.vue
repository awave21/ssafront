<template>
  <div class="w-full px-5 py-5 flex flex-col gap-6">
    <!-- Header -->
    <div class="flex items-center gap-4">
      <NuxtLink
        :to="backUrl"
        class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white border border-slate-100 shadow-[0_2px_8px_-2px_rgba(0,0,0,0.06)] hover:shadow-md transition-all"
      >
        <ArrowLeft class="h-4 w-4 text-slate-600" />
      </NuxtLink>
      <div>
        <h1 class="text-xl font-black text-slate-900">Платежи за визиты других периодов</h1>
        <p class="text-sm text-slate-400">
          {{ fmtDate(localDateFrom) }} — {{ fmtDate(localDateTo) }}
          <span v-if="agentName" class="ml-2 text-slate-300">·</span>
          <span v-if="agentName" class="ml-1">{{ agentName }}</span>
        </p>
      </div>
    </div>

    <!-- Revenue context: two KPI tiles side by side -->
    <div v-if="data" class="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <!-- Full revenue tile -->
      <div class="group relative overflow-hidden rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <div class="absolute -right-8 -top-8 h-28 w-28 rounded-full bg-slate-400 opacity-10 transition-transform duration-700 group-hover:scale-150"></div>
        <div class="relative">
          <div class="text-[11px] font-black uppercase tracking-wider text-slate-400">Выручка за период · ИТОГО</div>
          <div class="mt-2 text-2xl font-black leading-tight tabular-nums text-slate-900">
            {{ fmtMoneyExact(revenueTotalAll) }}
          </div>
        </div>
      </div>

      <!-- Services this period -->
      <div class="group relative overflow-hidden rounded-3xl border border-emerald-100 bg-emerald-50 p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <div class="absolute -right-8 -top-8 h-28 w-28 rounded-full bg-emerald-500 opacity-10 transition-transform duration-700 group-hover:scale-150"></div>
        <div class="relative">
          <div class="text-[11px] font-black uppercase tracking-wider text-emerald-600">Услуги (этот период)</div>
          <div class="mt-2 text-2xl font-black leading-tight tabular-nums text-emerald-700">
            {{ fmtMoneyExact(revenueServices) }}
          </div>
        </div>
      </div>

      <!-- Commodity this period -->
      <div class="group relative overflow-hidden rounded-3xl border border-blue-100 bg-blue-50 p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <div class="absolute -right-8 -top-8 h-28 w-28 rounded-full bg-blue-500 opacity-10 transition-transform duration-700 group-hover:scale-150"></div>
        <div class="relative">
          <div class="text-[11px] font-black uppercase tracking-wider text-blue-600">Товары (этот период)</div>
          <div class="mt-2 text-2xl font-black leading-tight tabular-nums text-blue-700">
            {{ fmtMoneyExact(revenueCommodity) }}
          </div>
        </div>
      </div>

      <!-- Crossperiod portion tile -->
      <div class="group relative overflow-hidden rounded-3xl border border-amber-200 bg-amber-50 p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <div class="absolute -right-8 -top-8 h-28 w-28 rounded-full bg-amber-500 opacity-10 transition-transform duration-700 group-hover:scale-150"></div>
        <div class="relative">
          <div class="text-[11px] font-black uppercase tracking-wider text-amber-500">За визиты других периодов</div>
          <div class="mt-2 text-2xl font-black leading-tight tabular-nums text-amber-700">
            {{ fmtMoneyExact(revenueCrossperiodActual) }}
          </div>
        </div>
      </div>
    </div>

    <!-- Payment-type chips: click to exclude/include -->
    <div v-if="data && handleBreakdown.length" class="rounded-2xl border border-slate-100 bg-white px-5 py-3 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-[10px] font-black uppercase tracking-wider text-slate-400 mr-1">Типы платежей · клик чтобы исключить:</span>
        <button
          v-for="h in handleBreakdown"
          :key="h.handle"
          class="rounded-xl px-3 py-1.5 text-xs font-bold transition-all"
          :class="excludedHandles.has(h.handle)
            ? 'bg-slate-100 text-slate-400 line-through opacity-60'
            : 'bg-primary/10 text-primary hover:bg-primary/20'"
          @click="toggleHandle(h.handle)"
          :title="h.handle"
        >
          {{ h.label }} · {{ h.count }} · {{ fmtMoneyExact(h.sum) }}
        </button>
        <button
          v-if="excludedHandles.size > 0"
          class="ml-auto rounded-xl bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-600 hover:bg-slate-200 transition-colors"
          @click="excludedHandles = new Set()"
        >
          Сбросить исключения
        </button>
      </div>
    </div>

    <!-- Toolbar: filters -->
    <div class="flex flex-wrap items-center gap-3 rounded-3xl border border-slate-100 bg-white px-5 py-4 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
      <!-- Direction filter chips -->
      <div class="flex items-center gap-1.5">
        <button
          v-for="opt in directionOptions"
          :key="opt.value"
          class="rounded-xl px-3 py-1.5 text-xs font-bold transition-colors"
          :class="directionFilter === opt.value ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'"
          @click="directionFilter = opt.value"
        >{{ opt.label }}</button>
      </div>

      <div class="h-4 w-px bg-slate-200"></div>

      <!-- Payment method -->
      <div class="flex items-center gap-1.5">
        <button
          v-for="m in paymentMethodOptions"
          :key="m.value"
          class="rounded-xl px-3 py-1.5 text-xs font-bold transition-colors"
          :class="methodFilter === m.value ? 'bg-primary text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'"
          @click="methodFilter = m.value"
        >{{ m.label }}</button>
      </div>

      <div class="h-4 w-px bg-slate-200"></div>

      <!-- Attendance filter -->
      <div class="flex items-center gap-1.5">
        <button
          v-for="a in attendanceOptions"
          :key="a.value"
          class="rounded-xl px-3 py-1.5 text-xs font-bold transition-colors"
          :class="attendanceFilter === a.value ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'"
          @click="attendanceFilter = a.value"
        >{{ a.label }}</button>
      </div>

      <div class="h-4 w-px bg-slate-200"></div>

      <!-- Client search -->
      <div class="relative flex items-center">
        <Search class="absolute left-2.5 h-3.5 w-3.5 text-slate-400" />
        <input
          v-model="clientSearch"
          type="text"
          placeholder="Поиск по ФИО или ID…"
          class="rounded-xl border border-slate-200 bg-slate-50 pl-8 pr-3 py-1.5 text-xs text-slate-700 placeholder-slate-400 focus:border-primary focus:bg-white focus:outline-none w-44"
        />
      </div>

      <!-- Resource filter -->
      <select
        v-model="resourceFilter"
        class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-700 focus:border-primary focus:outline-none"
      >
        <option value="">Все специалисты</option>
        <option v-for="r in resourceOptions" :key="r" :value="r">{{ r }}</option>
      </select>

      <!-- Reset + stats -->
      <div class="ml-auto flex items-center gap-3">
        <span class="text-xs text-slate-400">
          <span v-if="data">
            {{ filteredItems.length === allItems.length ? allItems.length : filteredItems.length + ' из ' + allItems.length }}
            {{ filteredItems.length === allItems.length ? 'записей' : '(выборка)' }}
            <span v-if="data.total > allItems.length" class="ml-1 text-amber-500 font-semibold">· загружено {{ allItems.length }} из {{ data.total }}</span>
          </span>
        </span>
        <button
          v-if="hasActiveFilters"
          class="flex items-center gap-1.5 rounded-xl bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-600 hover:bg-slate-200 transition-colors"
          @click="resetFilters"
        >
          <X class="h-3 w-3" />
          Сбросить
        </button>
        <button
          class="flex items-center gap-1.5 rounded-xl bg-primary/10 px-3 py-1.5 text-xs font-bold text-primary hover:bg-primary/20 transition-colors"
          @click="exportCsv"
        >
          <Download class="h-3 w-3" />
          CSV
        </button>
      </div>
    </div>

    <!-- Table -->
    <div class="rounded-3xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] overflow-hidden">
      <!-- Loading -->
      <div v-if="loading" class="flex h-48 items-center justify-center">
        <div class="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
      </div>

      <!-- Error -->
      <div v-else-if="loadError" class="flex h-48 flex-col items-center justify-center gap-2 px-8 text-center">
        <p class="text-sm font-semibold text-rose-500">{{ loadError }}</p>
      </div>

      <!-- Empty -->
      <div v-else-if="filteredItems.length === 0" class="flex h-48 flex-col items-center justify-center gap-2 text-slate-400">
        <Receipt class="h-8 w-8 opacity-30" />
        <p class="text-sm">Нет платежей за визиты других периодов</p>
      </div>

      <!-- Table -->
      <div v-else class="overflow-x-auto" style="max-height: 70vh; overflow-y: auto;">
        <table class="w-full text-sm border-collapse">
          <colgroup>
            <col style="min-width:180px">
            <col style="min-width:120px">
            <col style="min-width:110px">
            <col style="min-width:140px">
            <col style="min-width:90px">
            <col style="min-width:110px">
            <col style="min-width:180px">
            <col style="min-width:180px">
            <col style="min-width:120px">
            <col style="min-width:70px">
            <col style="min-width:180px">
          </colgroup>
          <thead class="sticky top-0 z-10 bg-slate-50/95 backdrop-blur">
            <tr class="border-b border-slate-100">
              <th
                v-for="col in columns"
                :key="col.key"
                class="cursor-pointer select-none px-4 py-3.5 text-[9px] font-black uppercase tracking-wider text-slate-400 hover:text-slate-700 transition-colors whitespace-nowrap"
                :class="col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'"
                @click="col.sortable ? onSort(col.key) : undefined"
              >
                {{ col.label }}
                <span v-if="sortBy === col.key" class="ml-0.5 text-primary">{{ sortOrder === 'desc' ? '↓' : '↑' }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in pagedItems"
              :key="item.payment_external_id"
              class="border-b border-slate-50 transition-colors"
              :class="item.is_crossperiod ? 'bg-amber-50/60 hover:bg-amber-50' : 'hover:bg-slate-50/60'"
            >
              <!-- Клиент -->
              <td class="px-4 py-3">
                <button
                  v-if="item.client_external_id"
                  class="text-left group w-full"
                  @click="openClientCard(item.client_external_id)"
                >
                  <div class="font-semibold text-slate-800 group-hover:text-primary transition-colors leading-tight text-xs truncate" :title="item.client_name || ('Клиент #' + item.client_external_id)">
                    {{ item.client_name || ('Клиент #' + item.client_external_id) }}
                  </div>
                  <div class="text-[10px] text-slate-400 mt-0.5">ID {{ item.client_external_id }}</div>
                </button>
                <span v-else class="text-slate-400 text-xs">—</span>
              </td>
              <!-- Сумма -->
              <td class="px-4 py-3 text-right tabular-nums font-black text-slate-900 whitespace-nowrap text-xs">
                {{ fmtMoneyExact(item.amount) }}
              </td>
              <!-- Дата оплаты -->
              <td class="px-4 py-3 tabular-nums text-slate-600 whitespace-nowrap text-xs">
                {{ fmtDate(item.payment_date) }}
              </td>
              <!-- Дата визита -->
              <td class="px-4 py-3 whitespace-nowrap">
                <template v-if="item.visit_date">
                  <span class="tabular-nums text-slate-600 text-xs">{{ fmtDate(item.visit_date) }}</span>
                  <span
                    class="ml-1.5 inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold"
                    :class="dirClass(item.direction)"
                  >{{ dirLabel(item.direction) }}</span>
                </template>
                <span v-else class="text-slate-300 text-xs">—</span>
              </td>
              <!-- Разрыв -->
              <td class="px-4 py-3 tabular-nums whitespace-nowrap text-xs">
                <template v-if="item.days_gap !== null && item.days_gap !== undefined">
                  <span :class="item.days_gap < 0 ? 'text-amber-600 font-semibold' : 'text-emerald-600 font-semibold'">
                    {{ item.days_gap > 0 ? '+' : '' }}{{ item.days_gap }} дн
                  </span>
                </template>
                <span v-else class="text-slate-300">—</span>
              </td>
              <!-- Способ оплаты -->
              <td class="px-4 py-3 text-xs whitespace-nowrap">
                <span
                  class="inline-flex items-center rounded-lg px-2 py-1 font-medium"
                  :class="methodClass(item.payment_method)"
                >{{ methodLabel(item.payment_method) }}</span>
              </td>
              <!-- Тип платежа -->
              <td class="px-4 py-3 text-slate-500 text-xs">
                <div class="truncate" :title="item.payment_type_name ?? undefined">{{ item.payment_type_name || '—' }}</div>
              </td>
              <!-- Специалист -->
              <td class="px-4 py-3 text-slate-600 text-xs">
                <div class="truncate" :title="item.resource_name ?? undefined">{{ item.resource_name || '—' }}</div>
              </td>
              <!-- Плановая цена -->
              <td class="px-4 py-3 text-right tabular-nums text-xs text-slate-500 whitespace-nowrap">
                {{ item.visit_total_price != null && item.visit_total_price > 0 ? fmtMoneyExact(item.visit_total_price) : '—' }}
              </td>
              <!-- Дошёл -->
              <td class="px-4 py-3 text-center">
                <span v-if="item.visit_attendance === 1" class="text-emerald-500 font-bold text-sm">✓</span>
                <span v-else-if="item.visit_attendance === 0" class="text-rose-400 font-bold text-sm">✗</span>
                <span v-else class="text-slate-200 text-xs">—</span>
              </td>
              <!-- Комментарий -->
              <td class="px-4 py-3 text-slate-500 text-xs">
                <div v-if="item.comment" class="truncate" :title="item.comment">{{ item.comment }}</div>
                <span v-else class="text-slate-200">—</span>
              </td>
            </tr>
          </tbody>
          <!-- Excel-style totals row -->
          <tfoot v-if="filteredItems.length > 0" class="sticky bottom-0 z-10">
            <tr class="border-t-2 border-slate-300 bg-slate-100 font-black text-xs">
              <!-- Клиент -->
              <td class="px-4 py-3 text-slate-700 whitespace-nowrap">
                Σ {{ tableTotals.clientsUnique }} клиент{{ plClientov(tableTotals.clientsUnique) }}
              </td>
              <!-- Сумма -->
              <td class="px-4 py-3 text-right tabular-nums text-slate-900 whitespace-nowrap">
                {{ fmtMoneyExact(tableTotals.amountSum) }}
              </td>
              <!-- Дата оплаты -->
              <td class="px-4 py-3 tabular-nums text-slate-500 whitespace-nowrap text-[10px] font-semibold">
                <template v-if="tableTotals.payDateMin">
                  {{ fmtDateShort(tableTotals.payDateMin) }}<br/>{{ fmtDateShort(tableTotals.payDateMax) }}
                </template>
                <span v-else>—</span>
              </td>
              <!-- Дата визита -->
              <td class="px-4 py-3 tabular-nums text-slate-500 whitespace-nowrap text-[10px] font-semibold">
                <template v-if="tableTotals.visitDateMin">
                  {{ fmtDateShort(tableTotals.visitDateMin) }}<br/>{{ fmtDateShort(tableTotals.visitDateMax) }}
                </template>
                <span v-else>—</span>
              </td>
              <!-- Разрыв -->
              <td class="px-4 py-3 tabular-nums text-slate-600 whitespace-nowrap">
                <span v-if="tableTotals.gapAvg !== null">
                  avg {{ tableTotals.gapAvg > 0 ? '+' : '' }}{{ tableTotals.gapAvg }} дн
                </span>
                <span v-else class="font-normal text-slate-300">—</span>
              </td>
              <!-- Способ -->
              <td class="px-4 py-3 text-[10px] text-slate-600 whitespace-nowrap">
                <span v-if="tableTotals.methodCash > 0" class="mr-1">Нал {{ tableTotals.methodCash }}</span>
                <span v-if="tableTotals.methodCard > 0" class="mr-1">Карта {{ tableTotals.methodCard }}</span>
                <span v-if="tableTotals.methodCert > 0">Серт {{ tableTotals.methodCert }}</span>
              </td>
              <!-- Тип платежа -->
              <td class="px-4 py-3 text-slate-500">{{ tableTotals.typesUnique }} тип{{ plTipov(tableTotals.typesUnique) }}</td>
              <!-- Специалист -->
              <td class="px-4 py-3 text-slate-500">{{ tableTotals.resourcesUnique }} врач{{ plVrachey(tableTotals.resourcesUnique) }}</td>
              <!-- Цена визита -->
              <td class="px-4 py-3 text-right tabular-nums text-slate-700 whitespace-nowrap">
                {{ tableTotals.priceSum > 0 ? fmtMoneyExact(tableTotals.priceSum) : '—' }}
              </td>
              <!-- Дошёл -->
              <td class="px-4 py-3 text-center text-[10px] text-slate-600 whitespace-nowrap">
                ✓ {{ tableTotals.arrived }} / ✗ {{ tableTotals.noShow }} / — {{ tableTotals.noVisit }}
              </td>
              <!-- Комментарий -->
              <td class="px-4 py-3 text-slate-400 text-[10px]">{{ tableTotals.withComment }} с коммент.</td>
            </tr>
          </tfoot>
        </table>
      </div>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="flex items-center justify-between border-t border-slate-100 px-5 py-3">
        <span class="text-xs text-slate-400">Страница {{ currentPage + 1 }} из {{ totalPages }}</span>
        <div class="flex items-center gap-1">
          <button
            :disabled="currentPage === 0"
            class="rounded-xl px-3 py-1.5 text-xs font-semibold disabled:opacity-30 bg-slate-100 hover:bg-slate-200 transition-colors"
            @click="currentPage--"
          >←</button>
          <button
            v-for="p in visiblePages"
            :key="p"
            class="rounded-xl px-3 py-1.5 text-xs font-bold transition-colors"
            :class="p === currentPage ? 'bg-primary text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
            @click="currentPage = p"
          >{{ p + 1 }}</button>
          <button
            :disabled="currentPage >= totalPages - 1"
            class="rounded-xl px-3 py-1.5 text-xs font-semibold disabled:opacity-30 bg-slate-100 hover:bg-slate-200 transition-colors"
            @click="currentPage++"
          >→</button>
        </div>
      </div>
    </div>

    <!-- Client card sheet -->
    <ClientCardSheet
      :is-open="clientCard.isOpen.value"
      :data="clientCard.data.value"
      :loading="clientCard.loading.value"
      :error="clientCard.error.value"
      @close="clientCard.close()"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ArrowLeft, Receipt, Search, X, Download } from 'lucide-vue-next'
import { useRoute } from 'vue-router'
import { useAnalyticsApi } from '~/composables/analyticsApi'
import { useClientCard } from '~/composables/useClientCard'
import ClientCardSheet from '~/components/analytics/v2/ClientCardSheet.vue'
import type {
  AnalyticsCrossperiodPaymentItem,
  AnalyticsCrossperiodPaymentsResponse,
  CrossperiodPaymentsSortBy,
} from '~/types/analytics'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const api = useAnalyticsApi()

// ─── Query params from the analytics page ────────────────────────────────────
const agentId = computed(() => String(route.query.agent_id ?? ''))
const agentName = computed(() => String(route.query.agent_name ?? ''))
const dateFrom = computed(() => String(route.query.date_from ?? ''))
const dateTo = computed(() => String(route.query.date_to ?? ''))
const timezone = computed(() => String(route.query.timezone ?? 'UTC'))
const channel = computed(() => String(route.query.channel ?? ''))
const revenueBasis = computed(() => String(route.query.revenue_basis ?? 'all'))
const paymentMethodsParam = computed(() => {
  const v = route.query.payment_methods
  if (Array.isArray(v)) return v.map(String)
  if (typeof v === 'string' && v) return v.split(',')
  return []
})
const revenueCategoriesParam = computed(() => {
  const v = route.query.revenue_categories
  if (Array.isArray(v)) return v.map(String)
  if (typeof v === 'string' && v) return v.split(',')
  return []
})

const revenueTotal = computed(() => Number(route.query.revenue_total ?? 0))
const revenueCrossperiod = computed(() => Number(route.query.revenue_crossperiod ?? 0))

const backUrl = computed(() => '/analytics')

// ─── Local date range (overrides URL params, user can change) ─────────────────
const _fmtIsoInit = (d: Date) => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
const _defaultTo = _fmtIsoInit(new Date())
const _defaultFrom = (() => { const d = new Date(); d.setDate(d.getDate() - 29); return _fmtIsoInit(d) })()

const localDateFrom = ref(dateFrom.value || _defaultFrom)
const localDateTo = ref(dateTo.value || _defaultTo)


// ─── Local filter state ───────────────────────────────────────────────────────
const directionFilter = ref<'' | 'past' | 'future' | 'unknown'>('')
const methodFilter = ref<'' | 'cash' | 'card' | 'certificate'>('')
const attendanceFilter = ref<'' | '1' | '0' | 'null'>('')
const clientSearch = ref('')
const resourceFilter = ref('')
const sortBy = ref<CrossperiodPaymentsSortBy>('amount')
const sortOrder = ref<'asc' | 'desc'>('desc')
const currentPage = ref(0)
const pageSize = 500
const directionOptions = [
  { value: '' as const, label: 'Все' },
  { value: 'current' as const, label: 'Этот период' },
  { value: 'past' as const, label: 'Долги (прошлые)' },
  { value: 'future' as const, label: 'Авансы (будущие)' },
  { value: 'unknown' as const, label: 'Без визита' },
]

const paymentMethodOptions = [
  { value: '' as const, label: 'Все способы' },
  { value: 'cash' as const, label: 'Нал' },
  { value: 'card' as const, label: 'Карта' },
  { value: 'certificate' as const, label: 'Сертификат' },
]

// Payment-type filter (handle exclusion). Click chip → исключить из расчёта
const PAYMENT_TYPE_LABELS: Record<string, string> = {
  'service-sell': 'Услуги',
  'commodity-sell': 'Товары',
  'alternative-payment': 'Сертификат (оплата)',
  'certificate-sell': 'Продажа сертификата',
  'other-income': 'Прочие доходы',
  'subscription-sell': 'Абонемент',
  'tariff-sell': 'Тариф',
}
const excludedHandles = ref<Set<string>>(new Set())
const toggleHandle = (h: string) => {
  const next = new Set(excludedHandles.value)
  if (next.has(h)) next.delete(h)
  else next.add(h)
  excludedHandles.value = next
}

const attendanceOptions = [
  { value: '' as const, label: 'Посещения: все' },
  { value: '1' as const, label: 'Дошёл' },
  { value: '0' as const, label: 'Не пришёл' },
  { value: 'null' as const, label: 'Без визита' },
]

const hasActiveFilters = computed(() =>
  directionFilter.value !== '' ||
  methodFilter.value !== '' ||
  attendanceFilter.value !== '' ||
  clientSearch.value !== '' ||
  resourceFilter.value !== ''
)

const resetFilters = () => {
  directionFilter.value = ''
  methodFilter.value = ''
  attendanceFilter.value = ''
  clientSearch.value = ''
  resourceFilter.value = ''
  currentPage.value = 0
}

// ─── Data ─────────────────────────────────────────────────────────────────────
const data = ref<AnalyticsCrossperiodPaymentsResponse | null>(null)
const loading = ref(false)
const loadError = ref<string | null>(null)

const load = async () => {
  if (!agentId.value) {
    loadError.value = 'Не указан агент (agent_id отсутствует в URL). Вернитесь на страницу аналитики и перейдите сюда по ссылке.'
    return
  }
  if (!localDateFrom.value || !localDateTo.value) return
  loading.value = true
  loadError.value = null
  try {
    data.value = await api.getCrossperiodPaymentsTable(agentId.value, {
      dateFrom: localDateFrom.value,
      dateTo: localDateTo.value,
      timezone: timezone.value,
      channel: channel.value,
      revenueBasis: 'clinical' as any,
      paymentMethods: paymentMethodsParam.value as any[],
      revenueCategories: [] as any[],
      resourceExternalId: null,
      clientTags: [],
      sortBy: 'amount',
      sortOrder: 'desc',
      limit: 5000,
      offset: 0,
      crossperiodOnly: false,
    })
  } catch (e: any) {
    loadError.value = e?.data?.detail || e?.message || 'Ошибка загрузки данных'
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ─── Resource options ─────────────────────────────────────────────────────────
const resourceOptions = computed(() => {
  const names = (data.value?.items ?? [])
    .map((i) => i.resource_name)
    .filter((n): n is string => !!n)
  return [...new Set(names)].sort((a, b) => a.localeCompare(b, 'ru'))
})

// ─── Filtering & sorting (client-side on loaded data) ─────────────────────────
const allItems = computed<AnalyticsCrossperiodPaymentItem[]>(() => data.value?.items ?? [])

const filteredItems = computed(() => {
  let items = allItems.value
  if (excludedHandles.value.size > 0) {
    items = items.filter((i) => !excludedHandles.value.has((i.payment_type_handle ?? '').toLowerCase()))
  }
  if (directionFilter.value) items = items.filter((i) => i.direction === directionFilter.value)
  if (methodFilter.value) items = items.filter((i) => (i.payment_method ?? '').toLowerCase() === methodFilter.value)
  if (attendanceFilter.value === '1') items = items.filter((i) => i.visit_attendance === 1)
  else if (attendanceFilter.value === '0') items = items.filter((i) => i.visit_attendance === 0)
  else if (attendanceFilter.value === 'null') items = items.filter((i) => i.visit_attendance == null)
  if (clientSearch.value.trim()) {
    const q = clientSearch.value.trim().toLowerCase()
    items = items.filter((i) =>
      (i.client_name ?? '').toLowerCase().includes(q) ||
      (i.client_external_id ?? '').toLowerCase().includes(q)
    )
  }
  if (resourceFilter.value) items = items.filter((i) => i.resource_name === resourceFilter.value)
  return items
})

watch([directionFilter, methodFilter, attendanceFilter, clientSearch, resourceFilter], () => { currentPage.value = 0 })

const sortedItems = computed(() => {
  const items = [...filteredItems.value]
  const rev = sortOrder.value === 'desc' ? -1 : 1
  items.sort((a, b) => {
    if (sortBy.value === 'amount') return (a.amount - b.amount) * rev
    if (sortBy.value === 'payment_date') return (a.payment_date ?? '').localeCompare(b.payment_date ?? '') * rev
    if (sortBy.value === 'visit_date') return ((a.visit_date ?? '').localeCompare(b.visit_date ?? '')) * rev
    if (sortBy.value === 'client_name') return (a.client_name ?? '').localeCompare(b.client_name ?? '', 'ru') * rev
    if (sortBy.value === 'days_gap') return ((a.days_gap ?? 0) - (b.days_gap ?? 0)) * rev
    return 0
  })
  return items
})

const totalPages = computed(() => Math.ceil(sortedItems.value.length / pageSize))
const pagedItems = computed(() => sortedItems.value.slice(currentPage.value * pageSize, (currentPage.value + 1) * pageSize))

const visiblePages = computed(() => {
  const total = totalPages.value
  const cur = currentPage.value
  const pages: number[] = []
  for (let i = Math.max(0, cur - 2); i < Math.min(total, cur + 3); i++) pages.push(i)
  return pages
})

// ─── Excel-style aggregates ───────────────────────────────────────────────────
const tableTotals = computed(() => {
  const items = filteredItems.value
  const amountSum = items.reduce((s, i) => s + i.amount, 0)
  const priceSum = items.reduce((s, i) => s + (i.visit_total_price ?? 0), 0)
  const clientsUnique = new Set(items.map((i) => i.client_external_id).filter(Boolean)).size
  const typesUnique = new Set(items.map((i) => i.payment_type_name).filter(Boolean)).size
  const resourcesUnique = new Set(items.map((i) => i.resource_name).filter(Boolean)).size
  const withComment = items.filter((i) => !!i.comment).length
  const arrived = items.filter((i) => i.visit_attendance === 1).length
  const noShow = items.filter((i) => i.visit_attendance === 0).length
  const noVisit = items.filter((i) => i.visit_attendance == null).length

  const payDates = items.map((i) => i.payment_date).filter(Boolean).sort()
  const payDateMin = payDates[0] ?? null
  const payDateMax = payDates[payDates.length - 1] ?? null

  const visitDates = items.map((i) => i.visit_date).filter(Boolean).sort() as string[]
  const visitDateMin = visitDates[0] ?? null
  const visitDateMax = visitDates[visitDates.length - 1] ?? null

  const gapItems = items.filter((i) => i.days_gap != null)
  const gapAvg = gapItems.length > 0
    ? Math.round(gapItems.reduce((s, i) => s + (i.days_gap ?? 0), 0) / gapItems.length)
    : null

  const methodCash = items.filter((i) => (i.payment_method ?? '').toLowerCase() === 'cash').length
  const methodCard = items.filter((i) => (i.payment_method ?? '').toLowerCase() === 'card').length
  const methodCert = items.filter((i) => (i.payment_method ?? '').toLowerCase() === 'certificate').length

  return {
    amountSum, priceSum, clientsUnique, typesUnique, resourcesUnique, withComment,
    arrived, noShow, noVisit,
    payDateMin, payDateMax, visitDateMin, visitDateMax,
    gapAvg, methodCash, methodCard, methodCert,
  }
})

// ─── Tile aggregates from loaded data (always from API, always sync with table) ───
const SERVICE_HANDLES = new Set(['service-sell', 'alternative-payment', 'certificate-sell'])
const COMMODITY_HANDLES = new Set(['commodity-sell'])

// "Свой период" = НЕ crossperiod. "Чужой период" = crossperiod.
// Тайлы внизу: Услуги_свой + Товары_свой + Чужой_период = Total
const revenueServices = computed(() =>
  filteredItems.value
    .filter((i) => !i.is_crossperiod && SERVICE_HANDLES.has((i.payment_type_handle ?? '').toLowerCase()))
    .reduce((s, i) => s + i.amount, 0)
)
const revenueCommodity = computed(() =>
  filteredItems.value
    .filter((i) => !i.is_crossperiod && COMMODITY_HANDLES.has((i.payment_type_handle ?? '').toLowerCase()))
    .reduce((s, i) => s + i.amount, 0)
)
const revenueCrossperiodActual = computed(() =>
  filteredItems.value
    .filter((i) => i.is_crossperiod)
    .reduce((s, i) => s + i.amount, 0)
)
const revenueAllOthers = computed(() =>
  filteredItems.value
    .filter((i) => {
      if (i.is_crossperiod) return false
      const h = (i.payment_type_handle ?? '').toLowerCase()
      return !SERVICE_HANDLES.has(h) && !COMMODITY_HANDLES.has(h)
    })
    .reduce((s, i) => s + i.amount, 0)
)
const revenueTotalAll = computed(() =>
  revenueServices.value + revenueCommodity.value + revenueCrossperiodActual.value + revenueAllOthers.value
)

// Breakdown по handle для UI чипов
const handleBreakdown = computed(() => {
  const map = new Map<string, { count: number; sum: number }>()
  for (const i of allItems.value) {
    const h = (i.payment_type_handle ?? '').toLowerCase() || 'unknown'
    const cur = map.get(h) ?? { count: 0, sum: 0 }
    cur.count += 1
    cur.sum += i.amount
    map.set(h, cur)
  }
  return [...map.entries()]
    .map(([handle, v]) => ({ handle, ...v, label: PAYMENT_TYPE_LABELS[handle] ?? handle }))
    .sort((a, b) => b.sum - a.sum)
})

// ─── Live totals for top cards ─────────────────────────────────────────────────
const liveTotalByDirection = computed(() => {
  const items = filteredItems.value
  return {
    '': items.reduce((s, i) => s + i.amount, 0),
    past: items.filter((i) => i.direction === 'past').reduce((s, i) => s + i.amount, 0),
    future: items.filter((i) => i.direction === 'future').reduce((s, i) => s + i.amount, 0),
    unknown: items.filter((i) => i.direction === 'unknown').reduce((s, i) => s + i.amount, 0),
  }
})

// ─── Totals cards ─────────────────────────────────────────────────────────────
const totalCards = computed(() => {
  const t = data.value?.totals
  if (!t) return []
  const live = liveTotalByDirection.value
  const hasFilter = hasActiveFilters.value
  return [
    {
      key: '' as const,
      label: 'Итого кросс-платежей',
      value: t.amount_total,
      sub: `${t.payments_total} платежей · ${t.clients_unique} клиент${plural(t.clients_unique)}`,
      active: directionFilter.value === '',
      activeClass: 'border-slate-700 bg-slate-800 shadow-lg',
      circleClass: 'bg-slate-500',
      valueClass: 'text-slate-900',
      live: hasFilter && directionFilter.value !== '' ? live[''] : null,
    },
    {
      key: 'past' as const,
      label: 'Долги (прошлые визиты)',
      value: t.amount_past,
      sub: 'Оплата после визита',
      active: directionFilter.value === 'past',
      activeClass: 'border-amber-500 bg-amber-600 shadow-lg shadow-amber-200',
      circleClass: 'bg-amber-400',
      valueClass: 'text-amber-600',
      live: hasFilter ? live['past'] : null,
    },
    {
      key: 'future' as const,
      label: 'Авансы (будущие визиты)',
      value: t.amount_future,
      sub: 'Предоплата за визит',
      active: directionFilter.value === 'future',
      activeClass: 'border-emerald-500 bg-emerald-600 shadow-lg shadow-emerald-200',
      circleClass: 'bg-emerald-400',
      valueClass: 'text-emerald-600',
      live: hasFilter ? live['future'] : null,
    },
    {
      key: 'unknown' as const,
      label: 'Без визита',
      value: t.amount_unknown,
      sub: 'Платёж без привязки',
      active: directionFilter.value === 'unknown',
      activeClass: 'border-slate-400 bg-slate-500 shadow-lg',
      circleClass: 'bg-slate-300',
      valueClass: 'text-slate-500',
      live: hasFilter ? live['unknown'] : null,
    },
  ]
})

const toggleDirection = (key: '' | 'past' | 'future' | 'unknown') => {
  directionFilter.value = directionFilter.value === key ? '' : key
}

const onSort = (col: string) => {
  if (sortBy.value === col) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = col as CrossperiodPaymentsSortBy
    sortOrder.value = 'desc'
  }
  currentPage.value = 0
}

// ─── Columns ──────────────────────────────────────────────────────────────────
const columns = [
  { key: 'client_name', label: 'Клиент', sortable: true, align: 'left' },
  { key: 'amount', label: 'Сумма', sortable: true, align: 'right' },
  { key: 'payment_date', label: 'Дата оплаты', sortable: true, align: 'left' },
  { key: 'visit_date', label: 'Дата визита', sortable: true, align: 'left' },
  { key: 'days_gap', label: 'Разрыв', sortable: true, align: 'left' },
  { key: 'payment_method', label: 'Способ', sortable: false, align: 'left' },
  { key: 'payment_type', label: 'Тип платежа', sortable: false, align: 'left' },
  { key: 'resource', label: 'Специалист', sortable: false, align: 'left' },
  { key: 'visit_total_price', label: 'Цена визита', sortable: false, align: 'right' },
  { key: 'attendance', label: 'Дошёл', sortable: false, align: 'center' },
  { key: 'comment', label: 'Комментарий', sortable: false, align: 'left' },
]

// ─── Formatting ───────────────────────────────────────────────────────────────
const fmt = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })
const fmtMoney = (v: number) => {
  if (!v) return '0 ₽'
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + ' млн ₽'
  if (v >= 10_000) return Math.round(v / 1000) + ' тыс ₽'
  return fmt.format(Math.round(v)) + ' ₽'
}
const fmtMoneyExact = (v: number) => {
  if (!v) return '0 ₽'
  return fmt.format(Math.round(v)) + ' ₽'
}
const fmtDate = (iso: string | null | undefined) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
}
const fmtDateShort = (iso: string | null | undefined) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

const methodLabel = (m: string | null) => {
  if (!m) return '—'
  const map: Record<string, string> = { cash: 'Наличные', card: 'Карта', certificate: 'Сертификат' }
  return map[m.toLowerCase()] ?? m
}
const methodClass = (m: string | null) => {
  if (!m) return 'bg-slate-50 text-slate-400'
  const lm = m.toLowerCase()
  if (lm === 'cash') return 'bg-emerald-50 text-emerald-700'
  if (lm === 'card') return 'bg-blue-50 text-blue-700'
  if (lm === 'certificate') return 'bg-purple-50 text-purple-700'
  return 'bg-slate-50 text-slate-500'
}
const dirLabel = (d: string) => d === 'past' ? 'прошлый' : d === 'future' ? 'будущий' : '?'
const dirClass = (d: string) => {
  if (d === 'past') return 'bg-amber-100 text-amber-700'
  if (d === 'future') return 'bg-emerald-100 text-emerald-700'
  return 'bg-slate-100 text-slate-500'
}
const plural = (n: number) => {
  const mod10 = n % 10, mod100 = n % 100
  if (mod100 >= 11 && mod100 <= 19) return 'ов'
  if (mod10 === 1) return ''
  if (mod10 >= 2 && mod10 <= 4) return 'а'
  return 'ов'
}
const plClientov = (n: number) => {
  const mod10 = n % 10, mod100 = n % 100
  if (mod100 >= 11 && mod100 <= 19) return 'ов'
  if (mod10 === 1) return ''
  if (mod10 >= 2 && mod10 <= 4) return 'а'
  return 'ов'
}
const plTipov = (n: number) => {
  const mod10 = n % 10, mod100 = n % 100
  if (mod100 >= 11 && mod100 <= 19) return 'ов'
  if (mod10 === 1) return ''
  if (mod10 >= 2 && mod10 <= 4) return 'а'
  return 'ов'
}
const plVrachey = (n: number) => {
  const mod10 = n % 10, mod100 = n % 100
  if (mod100 >= 11 && mod100 <= 19) return 'ей'
  if (mod10 === 1) return ''
  if (mod10 >= 2 && mod10 <= 4) return 'а'
  return 'ей'
}

// ─── CSV Export ───────────────────────────────────────────────────────────────
const exportCsv = () => {
  const t = tableTotals.value
  const headers = ['Клиент', 'ID клиента', 'Сумма', 'Дата оплаты', 'Дата визита', 'Разрыв (дн)', 'Способ оплаты', 'Тип платежа', 'Специалист', 'Цена визита', 'Дошёл', 'Комментарий']
  const rows = filteredItems.value.map((i) => [
    i.client_name ?? '',
    i.client_external_id ?? '',
    i.amount,
    i.payment_date ? fmtDate(i.payment_date) : '',
    i.visit_date ? fmtDate(i.visit_date) : '',
    i.days_gap ?? '',
    methodLabel(i.payment_method),
    i.payment_type_name ?? '',
    i.resource_name ?? '',
    i.visit_total_price ?? '',
    i.visit_attendance === 1 ? 'Дошёл' : i.visit_attendance === 0 ? 'Не пришёл' : '',
    i.comment ?? '',
  ])
  const totalsRow = [
    `Итого: ${t.clientsUnique} клиентов`,
    '',
    t.amountSum,
    `${fmtDateShort(t.payDateMin)} - ${fmtDateShort(t.payDateMax)}`,
    `${fmtDateShort(t.visitDateMin)} - ${fmtDateShort(t.visitDateMax)}`,
    t.gapAvg != null ? `avg ${t.gapAvg}` : '',
    `Нал ${t.methodCash} / Карта ${t.methodCard} / Серт ${t.methodCert}`,
    `${t.typesUnique} типов`,
    `${t.resourcesUnique} врачей`,
    t.priceSum,
    `✓${t.arrived} / ✗${t.noShow} / —${t.noVisit}`,
    `${t.withComment} с комментарием`,
  ]
  const escape = (v: any) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const csv = [headers, ...rows, totalsRow]
    .map((r) => r.map(escape).join(';'))
    .join('\n')
  const BOM = '﻿'
  const blob = new Blob([BOM + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `crossperiod-payments-${dateFrom.value}-${dateTo.value}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ─── Client card ──────────────────────────────────────────────────────────────
const clientCard = useClientCard(agentId.value)
const openClientCard = (clientExternalId: string) => clientCard.open(clientExternalId)
</script>
