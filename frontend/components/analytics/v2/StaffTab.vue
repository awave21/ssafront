<template>
  <div class="space-y-8">
    <div v-if="loading && !data" class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <div v-for="i in 3" :key="i" class="h-40 animate-pulse rounded-3xl bg-white"></div>
    </div>

    <template v-else-if="data && data.items.length">
      <!-- Top performers -->
      <section v-if="topPerformers.length" class="space-y-4">
        <h3 class="text-[11px] font-bold uppercase tracking-[0.2em] text-slate-400">Лидеры</h3>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div
            v-for="(member, idx) in topPerformers"
            :key="member.resource_external_id"
            class="group relative overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all hover:-translate-y-1 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)] duration-500"
          >
            <div class="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-emerald-50 transition-transform duration-700 group-hover:scale-150"></div>
            <div class="relative flex items-center gap-2 text-[10px] font-black uppercase tracking-wider text-emerald-600">
              <Trophy class="h-3.5 w-3.5" /> #{{ idx + 1 }} по выручке
            </div>
            <div class="relative mt-3 text-base font-bold text-slate-900">{{ member.full_name }}</div>
            <div class="text-xs text-slate-500">{{ member.position || '—' }}</div>

            <div class="relative mt-4 grid grid-cols-2 gap-2">
              <div class="rounded-xl bg-slate-50 px-3 py-2">
                <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Выручка</div>
                <div class="text-sm font-black tabular-nums text-slate-900">{{ formatMoney(member.revenue_total) }}</div>
              </div>
              <div class="rounded-xl bg-slate-50 px-3 py-2">
                <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Конверсия</div>
                <div class="text-sm font-black tabular-nums text-slate-900">{{ member.conversion_pct }}%</div>
              </div>
              <div class="rounded-xl bg-primary/10 px-3 py-2">
                <div class="text-[9px] font-black uppercase tracking-wider text-primary/70">Первичных</div>
                <div class="text-sm font-black tabular-nums text-primary">{{ member.primary_total }}</div>
              </div>
              <div class="rounded-xl bg-slate-50 px-3 py-2">
                <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Конв. перв.</div>
                <div class="text-sm font-black tabular-nums text-slate-900">
                  {{ member.primary_total > 0 ? Math.round((member.primary_arrived / member.primary_total) * 100) : 0 }}%
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Watch list -->
      <section v-if="watchList.length" class="space-y-4">
        <h3 class="text-[11px] font-bold uppercase tracking-[0.2em] text-rose-500">Под контроль</h3>
        <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div
            v-for="member in watchList"
            :key="'w-' + member.resource_external_id"
            class="rounded-3xl border border-rose-100 bg-rose-50/40 p-5"
          >
            <div class="flex items-center gap-2 text-[10px] font-black uppercase tracking-wider text-rose-600">
              <AlertTriangle class="h-3.5 w-3.5" /> Требует внимания
            </div>
            <div class="mt-3 text-base font-bold text-slate-900">{{ member.full_name }}</div>
            <p class="mt-1 text-xs text-slate-600">{{ watchReason(member) }}</p>
          </div>
        </div>
      </section>

      <!-- Full table -->
      <section class="rounded-3xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <div class="flex flex-col gap-3 px-6 py-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 class="text-sm font-bold uppercase tracking-widest text-slate-500">Все сотрудники</h3>
            <div class="mt-0.5 text-xs text-slate-400">
              <span class="font-bold text-slate-600">{{ counts.filtered }}</span>
              <span> из {{ counts.total }}</span>
              <span v-if="counts.inactive > 0 && onlyActive"> · скрыто {{ counts.inactive }} без записей</span>
            </div>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <input
              v-model="search"
              type="text"
              placeholder="Поиск по имени или должности…"
              class="h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm placeholder:text-slate-400 focus:border-primary focus:outline-none md:w-64"
            />
            <button
              type="button"
              class="h-9 rounded-xl border px-3 text-xs font-bold transition-colors"
              :class="onlyActive
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50'"
              @click="onlyActive = !onlyActive"
            >
              {{ onlyActive ? 'Только активные' : 'Все сотрудники' }}
            </button>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-y border-slate-100 bg-slate-50/50 text-[10px] font-black uppercase tracking-wider text-slate-500">
                <th class="px-6 py-3 text-left">
                  <button class="inline-flex items-center gap-1 hover:text-slate-700" @click="toggleSort('full_name')">
                    Сотрудник <component :is="sortIcon('full_name')" class="h-3 w-3" />
                  </button>
                </th>
                <th class="px-3 py-3 text-right">
                  <button class="inline-flex items-center gap-1 hover:text-slate-700" @click="toggleSort('visits_total')">
                    Записи <component :is="sortIcon('visits_total')" class="h-3 w-3" />
                  </button>
                </th>
                <th class="px-3 py-3 text-right" title="Первичные записи к этому врачу — пациент впервые именно у него">
                  <button class="inline-flex items-center gap-1 hover:text-slate-700" @click="toggleSort('primary_total')">
                    Первичные <component :is="sortIcon('primary_total')" class="h-3 w-3" />
                  </button>
                </th>
                <th class="px-3 py-3 text-right" title="% дошедших из первичных записей">
                  <button class="inline-flex items-center gap-1 hover:text-slate-700" @click="toggleSort('primary_conv')">
                    Конв. перв. <component :is="sortIcon('primary_conv')" class="h-3 w-3" />
                  </button>
                </th>
                <th class="px-3 py-3 text-right">
                  <button class="inline-flex items-center gap-1 hover:text-slate-700" @click="toggleSort('arrived_total')">
                    Дошли <component :is="sortIcon('arrived_total')" class="h-3 w-3" />
                  </button>
                </th>
                <th class="px-3 py-3 text-right">
                  <button class="inline-flex items-center gap-1 hover:text-slate-700" @click="toggleSort('conversion_pct')">
                    Конв. <component :is="sortIcon('conversion_pct')" class="h-3 w-3" />
                  </button>
                </th>
                <th class="px-3 py-3 text-right">
                  <button class="inline-flex items-center gap-1 hover:text-slate-700" @click="toggleSort('no_show_pct')">
                    No-show <component :is="sortIcon('no_show_pct')" class="h-3 w-3" />
                  </button>
                </th>
                <th class="px-3 py-3 text-right">
                  <button class="inline-flex items-center gap-1 hover:text-slate-700" @click="toggleSort('revenue_total')">
                    Выручка <component :is="sortIcon('revenue_total')" class="h-3 w-3" />
                  </button>
                </th>
                <th class="px-3 py-3 text-right">
                  <button class="inline-flex items-center gap-1 hover:text-slate-700" @click="toggleSort('margin_total')">
                    Маржа <component :is="sortIcon('margin_total')" class="h-3 w-3" />
                  </button>
                </th>
                <th class="px-3 py-3 text-right">
                  <button class="inline-flex items-center gap-1 hover:text-slate-700" @click="toggleSort('revenue_delta_pct')">
                    Δ <component :is="sortIcon('revenue_delta_pct')" class="h-3 w-3" />
                  </button>
                </th>
                <th class="px-3 py-3"></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="member in sortedItems"
                :key="member.resource_external_id"
                class="cursor-pointer border-b border-slate-50 transition-colors hover:bg-slate-50/60"
                :class="member.visits_total === 0 && 'bg-slate-50/40 opacity-70'"
                @click="$emit('open-detail', member.resource_external_id)"
              >
                <td class="px-6 py-3">
                  <div class="flex items-center gap-2">
                    <span class="font-bold text-slate-900">{{ member.full_name }}</span>
                    <span
                      v-if="member.is_fired"
                      class="rounded bg-rose-50 px-1.5 py-0.5 text-[9px] font-black uppercase tracking-wider text-rose-600"
                    >Уволен</span>
                    <span
                      v-else-if="member.visits_total === 0"
                      class="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-black uppercase tracking-wider text-slate-500"
                    >Нет записей</span>
                  </div>
                  <div v-if="member.position" class="text-xs text-slate-400">{{ member.position }}</div>
                </td>
                <td class="px-3 py-3 text-right tabular-nums text-slate-700">{{ member.visits_total }}</td>
                <td class="px-3 py-3 text-right tabular-nums">
                  <div class="font-bold text-primary">{{ member.primary_total }}</div>
                  <div v-if="member.visits_total > 0" class="text-[10px] text-slate-400">
                    {{ primaryShare(member) }}% от всех
                  </div>
                </td>
                <td class="px-3 py-3 text-right tabular-nums">
                  <span v-if="member.primary_total === 0" class="text-slate-300">—</span>
                  <span v-else :class="convClass(primaryConv(member))">{{ primaryConv(member) }}%</span>
                </td>
                <td class="px-3 py-3 text-right tabular-nums text-slate-700">{{ member.arrived_total }}</td>
                <td class="px-3 py-3 text-right tabular-nums">
                  <span :class="convClass(member.conversion_pct)">{{ member.conversion_pct }}%</span>
                </td>
                <td class="px-3 py-3 text-right tabular-nums">
                  <span :class="noShowClass(member.no_show_pct)">{{ member.no_show_pct }}%</span>
                </td>
                <td class="px-3 py-3 text-right font-bold tabular-nums text-slate-900">
                  {{ formatMoney(member.revenue_total) }}
                </td>
                <td class="px-3 py-3 text-right tabular-nums text-slate-600">
                  {{ formatMoney(member.margin_total) }}
                </td>
                <td class="px-3 py-3 text-right text-xs tabular-nums">
                  <span v-if="member.revenue_delta_pct === null" class="text-slate-300">—</span>
                  <span v-else :class="deltaClass(member.revenue_delta_pct)">
                    {{ member.revenue_delta_pct > 0 ? '+' : '' }}{{ member.revenue_delta_pct }}%
                  </span>
                </td>
                <td class="px-3 py-3 text-right">
                  <ChevronRight class="ml-auto h-4 w-4 text-slate-300" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <div v-else class="rounded-3xl border border-slate-100 bg-white p-10 text-center text-sm text-slate-400">
      Нет данных по сотрудникам за выбранный период.
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Trophy, AlertTriangle, ChevronRight, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-vue-next'
import type { StaffMember, StaffOverviewResponse } from '~/types/analytics'

const props = defineProps<{
  data: StaffOverviewResponse | null
  loading: boolean
}>()

defineEmits<{ (e: 'open-detail', resourceExternalId: number): void }>()

type SortKey =
  | 'full_name'
  | 'visits_total'
  | 'primary_total'
  | 'primary_conv'
  | 'arrived_total'
  | 'conversion_pct'
  | 'no_show_pct'
  | 'revenue_total'
  | 'margin_total'
  | 'revenue_delta_pct'

const search = ref('')
const onlyActive = ref(true)
const sortKey = ref<SortKey>('revenue_total')
const sortDir = ref<'asc' | 'desc'>('desc')

const toggleSort = (key: SortKey) => {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = key === 'full_name' ? 'asc' : 'desc'
  }
}

const sortIcon = (key: SortKey) =>
  sortKey.value !== key ? ArrowUpDown : sortDir.value === 'asc' ? ArrowUp : ArrowDown

const allItems = computed(() => props.data?.items || [])

const activeItems = computed(() => allItems.value.filter((m) => m.visits_total > 0))

const filteredItems = computed(() => {
  const base = onlyActive.value ? activeItems.value : allItems.value
  const q = search.value.trim().toLowerCase()
  if (!q) return base
  return base.filter(
    (m) =>
      m.full_name.toLowerCase().includes(q) ||
      (m.position || '').toLowerCase().includes(q),
  )
})

const sortValue = (m: StaffMember, key: SortKey): number | string => {
  switch (key) {
    case 'full_name': return m.full_name.toLowerCase()
    case 'primary_conv': return primaryConv(m)
    case 'revenue_delta_pct': return m.revenue_delta_pct ?? -Infinity
    default: return (m as any)[key] as number
  }
}

const sortedItems = computed(() => {
  const dir = sortDir.value === 'asc' ? 1 : -1
  return [...filteredItems.value].sort((a, b) => {
    const av = sortValue(a, sortKey.value)
    const bv = sortValue(b, sortKey.value)
    if (av < bv) return -1 * dir
    if (av > bv) return 1 * dir
    return 0
  })
})

const topPerformers = computed(() =>
  [...activeItems.value].sort((a, b) => b.revenue_total - a.revenue_total).slice(0, 3),
)

const watchList = computed(() =>
  activeItems.value.filter(
    (m) =>
      m.no_show_pct >= 25 ||
      (m.revenue_delta_pct !== null && m.revenue_delta_pct <= -20) ||
      (m.visits_total >= 10 && m.conversion_pct < 50),
  ).slice(0, 3),
)

const counts = computed(() => ({
  total: allItems.value.length,
  active: activeItems.value.length,
  inactive: allItems.value.length - activeItems.value.length,
  filtered: sortedItems.value.length,
}))

const primaryConv = (m: StaffMember) =>
  m.primary_total > 0 ? Math.round((m.primary_arrived / m.primary_total) * 100) : 0

const primaryShare = (m: StaffMember) =>
  m.visits_total > 0 ? Math.round((m.primary_total / m.visits_total) * 100) : 0

const watchReason = (m: StaffMember) => {
  const reasons: string[] = []
  if (m.no_show_pct >= 25) reasons.push(`no-show ${m.no_show_pct}%`)
  if (m.revenue_delta_pct !== null && m.revenue_delta_pct <= -20)
    reasons.push(`выручка ${m.revenue_delta_pct}%`)
  if (m.visits_total >= 10 && m.conversion_pct < 50) reasons.push(`конверсия ${m.conversion_pct}%`)
  return reasons.join(' · ')
}

const formatMoney = (v: number) => {
  if (!v) return '0 ₽'
  if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(1) + ' млн ₽'
  if (Math.abs(v) >= 10_000) return Math.round(v / 1000) + ' тыс ₽'
  return Math.round(v).toLocaleString('ru-RU') + ' ₽'
}

const convClass = (v: number) => {
  if (v >= 80) return 'text-emerald-600 font-bold'
  if (v >= 60) return 'text-slate-700'
  return 'text-rose-600 font-bold'
}

const noShowClass = (v: number) => {
  if (v >= 25) return 'text-rose-600 font-bold'
  if (v >= 15) return 'text-amber-600'
  return 'text-emerald-600'
}

const deltaClass = (v: number) => {
  if (v > 5) return 'text-emerald-600 font-bold'
  if (v < -5) return 'text-rose-600 font-bold'
  return 'text-slate-500'
}
</script>
