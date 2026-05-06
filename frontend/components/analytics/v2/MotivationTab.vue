<template>
  <div class="space-y-6">
    <!-- Loading skeleton -->
    <div v-if="pending && !overview" class="space-y-4">
      <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div v-for="i in 4" :key="i" class="h-32 animate-pulse rounded-3xl bg-white"></div>
      </div>
      <div class="h-64 animate-pulse rounded-3xl bg-white"></div>
    </div>

    <template v-else-if="overview">
      <!-- KPI tiles -->
      <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiTile
          label="Общая выручка"
          :value="overview.totals.revenue_total"
          :icon="TrendingUp"
          format="money"
          accent="slate"
        />
        <KpiTile
          label="Выручка первички"
          :value="overview.totals.primary_revenue"
          :icon="UserPlus"
          format="money"
          accent="primary"
        />
        <KpiTile
          label="Выручка вторички"
          :value="overview.totals.repeat_revenue"
          :icon="RefreshCw"
          format="money"
          accent="amber"
        />
        <KpiTile
          label="Итого к выплате"
          :value="overview.totals.bonus_total"
          :icon="Award"
          format="money"
          accent="emerald"
          :sub="`${overview.items.length} врачей`"
        />
      </div>

      <!-- Toolbar -->
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2 text-xs text-slate-500">
          <span class="font-bold text-slate-700">{{ overview.items.length }}</span> сотрудников за период
        </div>
        <button
          class="flex items-center gap-1.5 rounded-2xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-600 transition hover:bg-slate-50"
          @click="ruleSheetOpen = true"
        >
          <Settings class="h-3.5 w-3.5" />
          Настройки правила
        </button>
      </div>

      <!-- Table -->
      <div class="rounded-3xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="border-b border-slate-100 text-left">
                <th class="px-4 py-3 text-[10px] font-black uppercase tracking-wider text-slate-400">Сотрудник</th>
                <th class="px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400">Визиты</th>
                <th class="px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400">Первичных</th>
                <th class="px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400">Услуги</th>
                <th
                  class="px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider"
                  :class="overview.rule.include_commodities ? 'text-slate-400' : 'text-slate-300'"
                >
                  Товары
                </th>
                <th class="px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400">Итого выручка</th>
                <th class="px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400">Ср. чек перв.</th>
                <th class="px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400">Ср. чек вторич.</th>
                <th class="px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400">Ср. чек общий</th>
                <th class="px-3 py-3 text-center text-[10px] font-black uppercase tracking-wider text-slate-400">Уровень</th>
                <th class="px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400">% вторич.</th>
                <th class="px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400">Бонус перв.</th>
                <th class="px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-slate-400">Бонус вторич.</th>
                <th class="px-3 py-3 text-right text-[10px] font-black uppercase tracking-wider text-emerald-600">Итого бонус</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="member in sortedItems"
                :key="member.resource_external_id"
                class="border-b border-slate-50 transition-colors last:border-0 hover:bg-slate-50/60"
                :class="{ 'opacity-50': member.is_fired }"
              >
                <td class="px-4 py-3">
                  <div class="font-semibold text-slate-800">{{ member.full_name }}</div>
                  <div v-if="member.position" class="mt-0.5 text-[10px] text-slate-400">{{ member.position }}</div>
                  <div v-if="member.is_fired" class="mt-0.5 text-[10px] text-slate-300">уволен</div>
                </td>
                <td class="px-3 py-3 text-right font-mono text-slate-600">{{ member.arrived_total }}</td>
                <td class="px-3 py-3 text-right font-mono text-slate-600">{{ member.primary_visits }}</td>
                <td class="px-3 py-3 text-right font-mono text-slate-700">{{ formatMoney(member.services_revenue) }}</td>
                <td
                  class="px-3 py-3 text-right font-mono"
                  :class="overview.rule.include_commodities ? 'text-slate-700' : 'text-slate-300'"
                >
                  {{ formatMoney(member.commodities_revenue) }}
                </td>
                <td class="px-3 py-3 text-right font-mono font-semibold text-slate-800">{{ formatMoney(member.revenue_total) }}</td>
                <td class="px-3 py-3 text-right font-mono text-slate-600">{{ formatMoney(member.primary_avg_check) }}</td>
                <td class="px-3 py-3 text-right font-mono text-slate-600">{{ formatMoney(member.repeat_avg_check) }}</td>
                <td class="px-3 py-3 text-right font-mono text-slate-600">{{ formatMoney(member.total_avg_check) }}</td>
                <td class="px-3 py-3 text-center">
                  <span
                    class="inline-block rounded-full px-2 py-0.5 text-[10px] font-black uppercase tracking-wide"
                    :class="tierClass(member.tier)"
                  >{{ tierLabel(member.tier) }}</span>
                </td>
                <td class="px-3 py-3 text-right font-mono text-slate-600">{{ member.applied_repeat_pct }}%</td>
                <td class="px-3 py-3 text-right font-mono text-slate-700">{{ formatMoney(member.bonus_primary) }}</td>
                <td class="px-3 py-3 text-right font-mono text-slate-700">{{ formatMoney(member.bonus_repeat) }}</td>
                <td class="px-3 py-3 text-right font-mono font-black text-emerald-600">{{ formatMoney(member.bonus_total) }}</td>
              </tr>

              <!-- Totals row -->
              <tr class="border-t-2 border-slate-200 bg-slate-50/70">
                <td class="px-4 py-3 text-[10px] font-black uppercase tracking-wider text-slate-500">Итого</td>
                <td class="px-3 py-3 text-right font-mono font-bold text-slate-700">
                  {{ overview.items.reduce((s, m) => s + m.arrived_total, 0) }}
                </td>
                <td class="px-3 py-3 text-right font-mono font-bold text-slate-700">
                  {{ overview.items.reduce((s, m) => s + m.primary_visits, 0) }}
                </td>
                <td class="px-3 py-3 text-right font-mono font-bold text-slate-700">{{ formatMoney(overview.totals.services_revenue) }}</td>
                <td
                  class="px-3 py-3 text-right font-mono font-bold"
                  :class="overview.rule.include_commodities ? 'text-slate-700' : 'text-slate-300'"
                >
                  {{ formatMoney(overview.totals.commodities_revenue) }}
                </td>
                <td class="px-3 py-3 text-right font-mono font-bold text-slate-800">{{ formatMoney(overview.totals.revenue_total) }}</td>
                <td colspan="4"></td>
                <td></td>
                <td class="px-3 py-3 text-right font-mono font-bold text-slate-700">
                  {{ formatMoney(overview.items.reduce((s, m) => s + m.bonus_primary, 0)) }}
                </td>
                <td class="px-3 py-3 text-right font-mono font-bold text-slate-700">
                  {{ formatMoney(overview.items.reduce((s, m) => s + m.bonus_repeat, 0)) }}
                </td>
                <td class="px-3 py-3 text-right font-mono font-black text-emerald-700">{{ formatMoney(overview.totals.bonus_total) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Legend -->
      <div class="flex flex-wrap gap-4 text-xs text-slate-500">
        <div class="flex items-center gap-1.5">
          <span class="inline-block h-2 w-2 rounded-full bg-rose-400"></span>
          Ниже нормы — ср. чек &lt; {{ formatMoney(overview.rule.avg_check_low) }}, % вторички: {{ overview.rule.repeat_pct_low }}%
        </div>
        <div class="flex items-center gap-1.5">
          <span class="inline-block h-2 w-2 rounded-full bg-slate-400"></span>
          Норма — {{ formatMoney(overview.rule.avg_check_low) }}–{{ formatMoney(overview.rule.avg_check_high) }}, % вторички: {{ overview.rule.repeat_pct_norm }}%
        </div>
        <div class="flex items-center gap-1.5">
          <span class="inline-block h-2 w-2 rounded-full bg-emerald-400"></span>
          Выше нормы — ср. чек &gt; {{ formatMoney(overview.rule.avg_check_high) }}, % вторички: {{ overview.rule.repeat_pct_high }}%
        </div>
        <div class="flex items-center gap-1.5">
          <span class="inline-block h-2 w-2 rounded-full bg-sky-400"></span>
          Нет первичных — % вторички: {{ overview.rule.repeat_pct_norm }}%
        </div>
      </div>
    </template>

    <!-- Empty state -->
    <div v-else-if="!pending" class="flex flex-col items-center justify-center py-16 text-slate-400">
      <div class="text-4xl">📋</div>
      <div class="mt-3 text-sm font-semibold">Нет данных за выбранный период</div>
    </div>

    <!-- Rule settings sheet -->
    <MotivationRuleSheet
      v-if="overview"
      :open="ruleSheetOpen"
      :rule="overview.rule"
      @close="ruleSheetOpen = false"
      @saved="onRuleSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Award, RefreshCw, Settings, TrendingUp, UserPlus } from 'lucide-vue-next'
import KpiTile from '~/components/analytics/v2/KpiTile.vue'
import MotivationRuleSheet from '~/components/analytics/v2/MotivationRuleSheet.vue'
import type { MotivationMember, MotivationOverviewResponse, MotivationRule, MotivationTier } from '~/types/analytics'

const props = defineProps<{
  overview: MotivationOverviewResponse | null
  pending: boolean
  saveRule: (payload: Partial<MotivationRule>) => Promise<MotivationRule | undefined>
}>()

const ruleSheetOpen = ref(false)

const sortedItems = computed<MotivationMember[]>(() => {
  if (!props.overview) return []
  return [...props.overview.items].sort((a, b) => b.bonus_total - a.bonus_total)
})

function formatMoney(v: number): string {
  if (v === 0) return '—'
  if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(1) + ' млн ₽'
  if (Math.abs(v) >= 10_000) return Math.round(v / 1000) + ' тыс ₽'
  return Math.round(v).toLocaleString('ru-RU') + ' ₽'
}

function tierLabel(tier: MotivationTier): string {
  const map: Record<MotivationTier, string> = {
    low: 'Ниже нормы',
    norm: 'Норма',
    high: 'Бонус',
    no_primary: 'Нет перв.',
  }
  return map[tier]
}

function tierClass(tier: MotivationTier): string {
  const map: Record<MotivationTier, string> = {
    low: 'bg-rose-100 text-rose-700',
    norm: 'bg-slate-100 text-slate-600',
    high: 'bg-emerald-100 text-emerald-700',
    no_primary: 'bg-sky-100 text-sky-600',
  }
  return map[tier]
}

async function onRuleSaved(rule: MotivationRule) {
  ruleSheetOpen.value = false
  await props.saveRule(rule)
}
</script>
