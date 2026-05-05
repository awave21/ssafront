<template>
  <div class="space-y-8">
    <div v-if="loading && !data" class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <div v-for="i in 6" :key="i" class="h-28 animate-pulse rounded-3xl bg-white"></div>
    </div>

    <template v-else-if="data">
      <!-- KPI row -->
      <section class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <KpiTile
          label="Запусков"
          :value="data.runs.runs_total"
          :icon="Bot"
          accent="primary"
        />
        <KpiTile
          label="Успешных"
          :value="data.runs.success_pct"
          :icon="CheckCircle2"
          accent="emerald"
          format="pct"
        />
        <KpiTile
          label="Ср. время ответа"
          :value="data.runs.avg_duration_ms"
          :icon="Timer"
          accent="slate"
          format="ms"
        />
        <KpiTile
          label="Токенов"
          :value="data.runs.prompt_tokens_total + data.runs.completion_tokens_total"
          :icon="Cpu"
          accent="primary"
        />
        <KpiTile
          label="Стоимость (USD)"
          :value="data.runs.cost_usd_total.toFixed(2)"
          :icon="DollarSign"
          accent="amber"
          format="raw"
        />
        <KpiTile
          label="Без менеджера"
          :value="data.dialogs.autonomy_pct"
          :icon="ShieldCheck"
          accent="emerald"
          format="pct"
          sub="диалогов решено ботом"
        />
      </section>

      <!-- Budget forecast -->
      <section
        v-if="data.budget"
        class="rounded-3xl border bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
        :class="budgetBorderClass"
      >
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 class="text-[11px] font-bold uppercase tracking-[0.2em] text-slate-400">Бюджет бота</h3>
            <div class="mt-1 text-2xl font-black tabular-nums text-slate-900">
              {{ formatUsd(data.budget.spent_usd) }}
              <span class="text-sm font-medium text-slate-400"> / {{ formatUsd(data.budget.initial_balance_usd) }}</span>
            </div>
          </div>
          <div class="text-right">
            <div class="text-[10px] font-black uppercase tracking-wider text-slate-400">Остаток</div>
            <div class="text-xl font-black tabular-nums" :class="budgetRemainClass">{{ formatUsd(data.budget.remaining_usd) }}</div>
            <div v-if="data.budget.days_to_zero !== null" class="mt-0.5 text-xs text-slate-400">
              {{ data.budget.days_to_zero > 0 ? `≈ ${data.budget.days_to_zero} дн. до нуля` : 'Баланс исчерпан' }}
            </div>
          </div>
        </div>

        <div class="mt-5">
          <div class="mb-1.5 flex items-center justify-between text-[11px]">
            <span class="font-medium text-slate-400">Израсходовано</span>
            <span class="font-black tabular-nums" :class="budgetPctClass">{{ data.budget.spent_pct }}%</span>
          </div>
          <div class="h-3 overflow-hidden rounded-full bg-slate-100">
            <div
              class="h-3 rounded-full transition-all duration-700"
              :class="budgetBarClass"
              :style="{ width: Math.min(data.budget.spent_pct, 100) + '%' }"
            ></div>
          </div>
        </div>
      </section>

      <!-- Tool calls health -->
      <section
        v-if="data.tools.length"
        class="rounded-3xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
      >
        <div class="px-6 py-4">
          <h3 class="text-sm font-bold uppercase tracking-widest text-slate-500">Вызовы инструментов</h3>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-y border-slate-100 bg-slate-50/50 text-[10px] font-black uppercase tracking-wider text-slate-500">
                <th class="px-6 py-3 text-left">Инструмент</th>
                <th class="px-3 py-3 text-right">Вызовов</th>
                <th class="px-3 py-3 text-right">Ошибок</th>
                <th class="px-3 py-3 text-right">p50</th>
                <th class="px-3 py-3 text-right">p95</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="tool in data.tools"
                :key="tool.tool_name"
                class="border-b border-slate-50"
              >
                <td class="px-6 py-3 font-mono text-xs text-slate-700">{{ tool.tool_name }}</td>
                <td class="px-3 py-3 text-right tabular-nums text-slate-700">{{ tool.calls_total }}</td>
                <td class="px-3 py-3 text-right tabular-nums">
                  <span :class="tool.error_pct >= 10 ? 'text-rose-600 font-bold' : tool.error_pct >= 5 ? 'text-amber-600' : 'text-slate-400'">
                    {{ tool.error_pct }}%
                  </span>
                </td>
                <td class="px-3 py-3 text-right tabular-nums text-slate-500 text-xs">{{ fmtMs(tool.p50_ms) }}</td>
                <td class="px-3 py-3 text-right tabular-nums text-slate-500 text-xs">{{ fmtMs(tool.p95_ms) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Dialog quality detail -->
      <section class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div class="rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
          <div class="text-[10px] font-black uppercase tracking-wider text-slate-400">Диалогов всего</div>
          <div class="mt-1.5 text-2xl font-black tabular-nums text-slate-900">{{ data.dialogs.dialogs_total }}</div>
        </div>
        <div class="rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
          <div class="text-[10px] font-black uppercase tracking-wider text-slate-400">С вмешательством</div>
          <div class="mt-1.5 text-2xl font-black tabular-nums text-rose-600">{{ data.dialogs.dialogs_with_manager }}</div>
        </div>
        <div class="rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
          <div class="text-[10px] font-black uppercase tracking-wider text-slate-400">На паузе</div>
          <div class="mt-1.5 text-2xl font-black tabular-nums" :class="data.dialogs.dialogs_paused > 0 ? 'text-amber-600' : 'text-slate-900'">
            {{ data.dialogs.dialogs_paused }}
          </div>
        </div>
      </section>
    </template>

    <div v-else class="rounded-3xl border border-slate-100 bg-white p-10 text-center text-sm text-slate-400">
      Нет данных по боту за выбранный период.
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Bot, CheckCircle2, Timer, Cpu, DollarSign, ShieldCheck } from 'lucide-vue-next'
import KpiTile from './KpiTile.vue'
import type { BotHealthResponse } from '~/types/analytics'

const props = defineProps<{
  data: BotHealthResponse | null
  loading: boolean
}>()

const budgetPct = computed(() => props.data?.budget?.spent_pct ?? 0)

const budgetBorderClass = computed(() => {
  if (budgetPct.value >= 90) return 'border-rose-200'
  if (budgetPct.value >= 75) return 'border-amber-200'
  return 'border-slate-100'
})

const budgetRemainClass = computed(() => {
  if (budgetPct.value >= 90) return 'text-rose-600'
  if (budgetPct.value >= 75) return 'text-amber-600'
  return 'text-emerald-600'
})

const budgetPctClass = computed(() => {
  if (budgetPct.value >= 90) return 'text-rose-600'
  if (budgetPct.value >= 75) return 'text-amber-600'
  return 'text-slate-700'
})

const budgetBarClass = computed(() => {
  if (budgetPct.value >= 90) return 'bg-rose-500'
  if (budgetPct.value >= 75) return 'bg-amber-500'
  return 'bg-emerald-500'
})

const formatUsd = (v: number) => {
  if (v === null || v === undefined) return '—'
  if (Math.abs(v) >= 1000) return '$' + Math.round(v).toLocaleString('en-US')
  return '$' + v.toFixed(2)
}

const fmtMs = (ms: number | null) => {
  if (ms === null) return '—'
  if (ms >= 1000) return (ms / 1000).toFixed(1) + ' с'
  return Math.round(ms) + ' мс'
}
</script>
