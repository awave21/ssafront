<template>
  <div class="flex flex-col gap-5">
    <!-- Header -->
    <div class="flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
      <div class="flex items-center gap-2.5">
        <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <DollarSign class="h-4 w-4" />
        </div>
        <h1 class="text-lg font-semibold text-slate-900">Бюджет</h1>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:border-primary/40 hover:text-primary transition-colors"
        @click="helpOpen = !helpOpen"
      >
        <BookOpen class="h-3.5 w-3.5" />
        Помощь по разделу
      </button>
    </div>

    <div
      v-if="helpOpen"
      class="rounded-2xl border border-slate-100 bg-slate-100 p-5 text-sm leading-relaxed text-slate-700"
    >
      <p class="mb-2 font-medium text-slate-900">Как считается расход</p>
      <p>
        Каждый запуск агента фиксирует стоимость по прайсу выбранной модели. Расход агента —
        сумма по всем его запускам с момента создания. Баланс организации пополняется владельцем
        и списывается по мере работы всех агентов. Курс USD → RUB для отображения фиксированный
        <span class="font-mono font-semibold">{{ USD_TO_RUB_RATE }} ₽ / $1</span>.
      </p>
    </div>

    <!-- Верхний ряд: три KPI -->
    <div class="grid gap-3 sm:grid-cols-3">
      <!-- Расход агента (RUB) -->
      <div class="group relative overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <div class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-primary/5" />
        <div class="relative z-10">
          <div class="flex items-center gap-2">
            <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Wallet class="h-4 w-4" />
            </div>
            <span class="text-[9px] font-black uppercase tracking-wider text-slate-500">Расход агента</span>
          </div>
          <div class="mt-3 text-2xl font-bold text-slate-900">
            {{ formatRubAmountFromUsd(agentUsd) }}
          </div>
          <div class="mt-0.5 text-xs text-slate-500">
            <span class="font-mono">{{ formatUsdAmount(agentUsd) }}</span>
            <span class="mx-1.5 text-slate-300">·</span>
            накопительно
          </div>
        </div>
      </div>

      <!-- Остаток тенанта (RUB) -->
      <div class="group relative overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <div class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-emerald-100/40" />
        <div class="relative z-10">
          <div class="flex items-center gap-2">
            <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
              <PiggyBank class="h-4 w-4" />
            </div>
            <span class="text-[9px] font-black uppercase tracking-wider text-slate-500">Остаток организации</span>
          </div>
          <div
            class="mt-3 text-2xl font-bold"
            :class="remainingUsdValue < 0 ? 'text-red-600' : 'text-slate-900'"
          >
            {{ formatRubAmountFromUsd(remainingUsdValue) }}
          </div>
          <div class="mt-0.5 text-xs text-slate-500">
            <span class="font-mono">{{ formatUsdAmount(remainingUsdValue) }}</span>
            <span class="mx-1.5 text-slate-300">·</span>
            из {{ formatRubAmountFromUsd(initialUsdValue) }}
          </div>
        </div>
      </div>

      <!-- Доля агента в общем расходе тенанта -->
      <div class="group relative overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <div class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-amber-100/40" />
        <div class="relative z-10">
          <div class="flex items-center gap-2">
            <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
              <ChartPie class="h-4 w-4" />
            </div>
            <span class="text-[9px] font-black uppercase tracking-wider text-slate-500">Доля в расходе орг.</span>
          </div>
          <div class="mt-3 text-2xl font-bold text-slate-900">
            {{ agentSharePercent }}%
          </div>
          <div class="mt-0.5 text-xs text-slate-500">
            из общего расхода {{ formatRubAmountFromUsd(spentUsdValue) }}
          </div>
        </div>
      </div>
    </div>

    <!-- Использование баланса тенанта — прогресс -->
    <div class="space-y-3 rounded-2xl bg-slate-100 p-5">
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <span class="text-sm font-semibold text-slate-900">Использование баланса организации</span>
          <span class="text-xs text-slate-500">Как расходуется общий кошелёк тенанта</span>
        </div>
        <span class="text-xs font-mono text-slate-600">{{ tenantSpentPercent }}% / 100%</span>
      </div>
      <div class="relative h-2 w-full overflow-hidden rounded-full bg-white">
        <div
          class="h-full rounded-full transition-all duration-500"
          :class="tenantProgressColor"
          :style="{ width: Math.min(100, tenantSpentPercent) + '%' }"
        />
      </div>
      <div class="grid gap-2 sm:grid-cols-3 text-xs">
        <div class="flex items-baseline justify-between rounded-xl bg-white/70 px-3 py-2">
          <span class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Внесено</span>
          <span class="font-mono font-semibold text-slate-900">{{ formatRubAmountFromUsd(initialUsdValue) }}</span>
        </div>
        <div class="flex items-baseline justify-between rounded-xl bg-white/70 px-3 py-2">
          <span class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Потрачено</span>
          <span class="font-mono font-semibold text-slate-900">{{ formatRubAmountFromUsd(spentUsdValue) }}</span>
        </div>
        <div class="flex items-baseline justify-between rounded-xl bg-white/70 px-3 py-2">
          <span class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Осталось</span>
          <span
            class="font-mono font-semibold"
            :class="remainingUsdValue < 0 ? 'text-red-600' : 'text-emerald-600'"
          >{{ formatRubAmountFromUsd(remainingUsdValue) }}</span>
        </div>
      </div>

      <!-- Алерт при низком балансе -->
      <div
        v-if="tenantSpentPercent >= 90"
        class="flex items-start gap-2 rounded-xl border border-red-100 bg-red-50/60 px-4 py-2.5 text-xs text-red-700"
      >
        <AlertTriangle class="h-3.5 w-3.5 mt-0.5 shrink-0 text-red-500" />
        <div>
          <span class="font-semibold">Баланс организации почти исчерпан.</span>
          Пополните счёт, чтобы агенты продолжили работу без прерываний.
        </div>
      </div>
      <div
        v-else-if="tenantSpentPercent >= 70"
        class="flex items-start gap-2 rounded-xl border border-amber-100 bg-amber-50/60 px-4 py-2.5 text-xs text-amber-800"
      >
        <AlertTriangle class="h-3.5 w-3.5 mt-0.5 shrink-0 text-amber-500" />
        <div>
          Потрачено более 70% баланса. Рекомендуем спланировать пополнение.
        </div>
      </div>

      <div v-if="balanceError" class="rounded-xl border border-red-100 bg-red-50/60 px-4 py-2.5 text-xs text-red-700">
        {{ balanceError }}
      </div>
    </div>

    <!-- Лимит на агента — заглушка (нужна миграция БД) -->
    <div class="space-y-3 rounded-2xl border border-dashed border-slate-200 bg-slate-100 p-5">
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <span class="text-sm font-semibold text-slate-700">Лимит расхода агента</span>
          <span class="rounded-full bg-slate-200/70 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-500">Скоро</span>
        </div>
      </div>
      <p class="text-xs leading-relaxed text-slate-500">
        Установка потолка расходов на этого агента (в ₽/USD), пороги алертов и автоматическое
        отключение при превышении. Ждёт колонки <code class="rounded bg-white px-1 py-0.5 text-[11px]">spend_limit_*</code>
        и enforce в оркестраторе.
      </p>
      <div class="grid gap-2 sm:grid-cols-3 opacity-40 pointer-events-none">
        <div class="rounded-xl border border-slate-200 bg-white px-3 py-2">
          <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Дневной</div>
          <div class="mt-1 text-sm font-mono text-slate-400">— ₽</div>
        </div>
        <div class="rounded-xl border border-slate-200 bg-white px-3 py-2">
          <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Месячный</div>
          <div class="mt-1 text-sm font-mono text-slate-400">— ₽</div>
        </div>
        <div class="rounded-xl border border-slate-200 bg-white px-3 py-2">
          <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Общий</div>
          <div class="mt-1 text-sm font-mono text-slate-400">— ₽</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import {
  DollarSign,
  BookOpen,
  Wallet,
  PiggyBank,
  AlertTriangle,
  PieChart as ChartPie,
} from 'lucide-vue-next'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import {
  useTenantBalance,
  formatUsdAmount,
  formatRubAmountFromUsd,
  USD_TO_RUB_RATE,
} from '~/composables/useTenantBalance'

const store = useAgentEditorStore()
const { agent } = storeToRefs(store)
const {
  balance,
  error: balanceError,
  fetchBalance,
  remainingUsdValue,
  spentUsdValue,
  initialUsdValue,
} = useTenantBalance()

const helpOpen = ref(false)

// Расход конкретного агента в USD (Decimal приходит строкой)
const agentUsd = computed(() => {
  const raw = agent.value?.total_cost_usd ?? '0'
  const num = typeof raw === 'string' ? Number.parseFloat(raw.replace(',', '.')) : Number(raw)
  return Number.isFinite(num) ? num : 0
})

// Доля агента в расходе тенанта. Если тенант ничего не потратил — 0.
const agentSharePercent = computed(() => {
  const total = spentUsdValue.value
  if (!total || total <= 0) return 0
  const share = (agentUsd.value / total) * 100
  return Math.min(100, Math.max(0, Math.round(share * 10) / 10))
})

// Процент использования баланса тенанта
const tenantSpentPercent = computed(() => {
  const initial = initialUsdValue.value
  if (!initial || initial <= 0) return 0
  const percent = (spentUsdValue.value / initial) * 100
  return Math.max(0, Math.round(percent * 10) / 10)
})

const tenantProgressColor = computed(() => {
  const p = tenantSpentPercent.value
  if (p >= 90) return 'bg-red-500'
  if (p >= 70) return 'bg-amber-500'
  return 'bg-emerald-500'
})

onMounted(async () => {
  try {
    await fetchBalance()
  } catch {
    // ошибка уже в balanceError
  }
})
</script>
