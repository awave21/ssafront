<template>
  <AgentPageShell title="Аналитика сценариев" :hide-actions="true" :contained="true">
    <div class="max-w-full space-y-5">

      <!-- ── Header ─────────────────────────────────────── -->
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <ScriptsNav :agent-id="agentId" active="coverage" />
        <div class="flex flex-wrap items-center gap-2 lg:justify-end">
          <div class="inline-flex rounded-xl border border-slate-200 bg-white p-1">
            <button
              v-for="opt in PERIOD_OPTIONS"
              :key="opt.days"
              type="button"
              class="h-8 rounded-lg px-3 text-xs font-semibold transition-colors"
              :class="periodDays === opt.days
                ? 'bg-primary text-primary-foreground'
                : 'text-slate-600 hover:bg-slate-100'"
              @click="setPeriod(opt.days)"
            >{{ opt.label }}</button>
          </div>
          <div ref="missedSettingsRef" class="relative">
            <button
              type="button"
              class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              :disabled="missedLoading"
              @click="missedSettingsOpen = !missedSettingsOpen"
            >
              <Activity class="h-3.5 w-3.5" />
              {{ missedLoading ? 'Анализирую…' : 'Анализировать' }}
              <ChevronDown class="h-3 w-3" :class="missedSettingsOpen ? 'rotate-180' : ''" />
            </button>
            <div
              v-if="missedSettingsOpen"
              class="absolute right-0 top-full z-20 mt-1 w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-lg"
            >
              <p class="mb-2 text-xs font-bold text-slate-700">Параметры анализа</p>
              <div class="mb-2">
                <label class="mb-1 block text-xs text-slate-500">Период</label>
                <div class="flex gap-1">
                  <button
                    v-for="opt in MISSED_PERIOD_OPTIONS"
                    :key="opt.h"
                    type="button"
                    class="flex-1 rounded-lg border px-2 py-1 text-xs font-semibold transition-colors"
                    :class="missedPeriodHours === opt.h
                      ? 'border-primary/40 bg-primary/10 text-primary'
                      : 'border-slate-200 text-slate-600 hover:border-slate-300'"
                    @click="missedPeriodHours = opt.h"
                  >{{ opt.label }}</button>
                </div>
              </div>
              <div class="mb-3">
                <label class="mb-1 block text-xs text-slate-500">Макс. диалогов: <span class="font-bold text-slate-700">{{ missedMaxRuns }}</span></label>
                <input
                  v-model.number="missedMaxRuns"
                  type="range"
                  min="10"
                  max="200"
                  step="10"
                  class="w-full accent-primary"
                />
                <div class="flex justify-between text-[10px] text-slate-400">
                  <span>10</span><span>200</span>
                </div>
              </div>
              <button
                type="button"
                class="w-full rounded-lg bg-primary py-1.5 text-xs font-bold text-primary-foreground hover:bg-primary/90"
                @click="detectMissed()"
              >
                Запустить анализ
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Error ───────────────────────────────────────── -->
      <div v-if="error" class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {{ error }}
      </div>

      <!-- ── Loading skeleton ───────────────────────────── -->
      <div v-if="loading && !report" class="py-14 text-center text-sm text-slate-400">
        <BarChart3 class="mx-auto mb-3 h-8 w-8 animate-pulse text-slate-300" />
        Загружаем аналитику…
      </div>

      <template v-else-if="report">

        <!-- ❶ Здоровье сценариев -->
        <CoverageHealthHero
          :total="report.summary.total_searches"
          :relevant="report.summary.relevant_count"
          :weak="report.summary.weak_count"
          :irrelevant="report.summary.irrelevant_count"
          :no-match="report.summary.no_match_count"
          :distinct-tactics="report.summary.distinct_tactics_used"
          :period-label="currentPeriodLabel"
        />

        <!-- ❷ Что сделать в первую очередь -->
        <section v-if="priorityActions.length > 0" class="rounded-2xl border border-primary/20 bg-primary/5">
          <div class="px-4 py-3">
            <h2 class="flex items-center gap-2 text-sm font-bold text-primary">
              <Lightbulb class="h-4 w-4" />
              Что сделать в первую очередь
            </h2>
            <p class="mt-0.5 text-xs text-primary/80">Приоритетные действия на основе данных</p>
          </div>
          <ol class="divide-y divide-primary/10 border-t border-primary/10">
            <li
              v-for="(action, i) in priorityActions"
              :key="i"
              class="flex items-start gap-3 px-4 py-3"
            >
              <span
                class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-white"
                :class="action.urgent ? 'bg-rose-600' : 'bg-primary'"
              >{{ i + 1 }}</span>
              <div class="min-w-0 flex-1">
                <div class="text-sm font-semibold text-slate-900">{{ action.title }}</div>
                <div class="mt-0.5 text-xs text-slate-600">{{ action.detail }}</div>
              </div>
              <a
                v-if="action.href"
                :href="action.href"
                class="shrink-0 inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground hover:bg-primary/90"
              >{{ action.cta }}</a>
              <button
                v-else-if="action.onClick"
                type="button"
                class="shrink-0 inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                :disabled="action.loading"
                @click="action.onClick()"
              >{{ action.loading ? 'Создаю…' : action.cta }}</button>
            </li>
          </ol>
        </section>

        <!-- ❸ Где ассистент работал без сценария (missed calls) -->
        <CoverageSection
          title="Где ассистент работал без сценария"
          subtitle="Ассистент ответил без скрипта в моменты, когда клиент возражал, сомневался или был готов записаться"
          :icon="AlertCircle"
          tone="rose"
          :default-open="true"
          :count="totalMissed || null"
        >

          <div v-if="missedLoading && missed.classes.length === 0" class="py-8 text-center text-sm text-slate-400">
            Анализируем последние диалоги…
          </div>
          <div v-else-if="missed.classes.length === 0" class="px-4 py-6 text-center text-sm text-slate-500">
            Нет данных. Нажмите «Анализировать» — ассистент проверит последние диалоги.
          </div>
          <div v-else class="divide-y divide-rose-50">
            <div
              v-for="cl in missed.classes"
              :key="cl.classification"
              class="px-4 py-3"
            >
              <!-- Group header -->
              <div class="flex items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <span class="text-base">{{ missedMeta(cl.classification).icon }}</span>
                  <div>
                    <div class="text-sm font-bold text-slate-900">{{ missedMeta(cl.classification).label }}</div>
                    <div class="text-xs text-slate-500">{{ missedMeta(cl.classification).detail }}</div>
                  </div>
                </div>
                <span class="rounded-full bg-rose-100 px-2.5 py-0.5 text-xs font-bold text-rose-800">
                  {{ cl.count }} {{ cl.count === 1 ? 'раз' : 'раза' }}
                </span>
              </div>
              <!-- Examples (collapsible) -->
              <details v-if="cl.examples.length > 0" class="mt-2">
                <summary class="cursor-pointer text-xs font-semibold text-rose-700 hover:text-rose-900">
                  Примеры реплик клиентов ↓
                </summary>
                <ul class="mt-2 space-y-2">
                  <li
                    v-for="(e, ei) in cl.examples"
                    :key="ei"
                    class="flex items-start justify-between gap-3 rounded-lg bg-rose-50 px-3 py-2 text-xs text-slate-700"
                  >
                    <span class="min-w-0 flex-1">{{ e.user_message.slice(0, 220) }}{{ e.user_message.length > 220 ? '…' : '' }}</span>
                    <!-- Сценарий уже есть — ссылка на него -->
                    <NuxtLink
                      v-if="e.best_match"
                      :to="`/agents/${agentId}/scripts/${e.best_match.flow_id}`"
                      class="shrink-0 inline-flex items-center gap-1 rounded-lg border border-emerald-200 bg-emerald-50 px-2 py-1 text-[11px] font-semibold text-emerald-700 hover:bg-emerald-100"
                      :title="`${e.best_match.title} · ${Math.round(e.best_match.score * 100)}% совпадение`"
                    >
                      <ArrowRight class="h-3 w-3" />
                      Открыть сценарий
                    </NuxtLink>
                    <!-- Сценария нет — создать -->
                    <button
                      v-else
                      type="button"
                      class="shrink-0 inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-white px-2 py-1 text-[11px] font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                      :disabled="!!creatingFromGap"
                      @click="createFlowFromGap(e.user_message.slice(0, 60))"
                    >
                      <Plus class="h-3 w-3" />
                      {{ creatingFromGap === e.user_message.slice(0, 60) ? '…' : 'Создать сценарий' }}
                    </button>
                  </li>
                </ul>
              </details>
            </div>
          </div>
        </CoverageSection>

        <!-- ❹ Темы, где сценариев не хватает -->
        <CoverageSection
          title="Темы, где сценариев не хватает"
          subtitle="Ассистент искал сценарий, но ничего подходящего не нашёл — здесь нужны новые сценарии"
          :icon="Sparkles"
          tone="amber"
          :default-open="false"
          :count="(clusters.length + report.gap_queries.length + report.no_match_queries.length) || null"
        >
          <template #actions>
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-amber-700 hover:bg-amber-50 disabled:opacity-50"
              :disabled="clusteringLoading"
              @click="recomputeClusters()"
            >
              <RefreshCw class="h-3.5 w-3.5" :class="clusteringLoading ? 'animate-spin' : ''" />
              {{ clusteringLoading ? 'Кластеризую…' : 'Обновить темы' }}
            </button>
          </template>

          <!-- Clusters -->
          <div v-if="clusters.length > 0" class="divide-y divide-amber-50">
            <div v-for="c in clusters" :key="c.id" class="px-4 py-4">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <div class="text-sm font-bold text-slate-900">{{ c.label }}</div>
                  <div v-if="c.suggestion" class="mt-0.5 text-xs text-slate-600">
                    <span class="font-medium text-amber-700">Что добавить:</span> {{ c.suggestion }}
                  </div>
                </div>
                <div class="flex shrink-0 flex-col items-end gap-1.5">
                  <CoverageMatchBadge
                    :score="c.avg_score"
                    :hits="c.query_count"
                    :relevant-threshold="report.thresholds.relevant"
                    :irrelevant-threshold="report.thresholds.irrelevant"
                  />
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 rounded-lg border border-amber-300 bg-white px-2.5 py-1.5 text-[11px] font-bold text-amber-800 hover:bg-amber-50 disabled:opacity-50"
                    :disabled="!!creatingFromGap"
                    @click="createFlowFromGap(c.label)"
                  >
                    <Plus class="h-3 w-3" />
                    {{ creatingFromGap === c.label ? 'Создаю…' : 'Создать сценарий' }}
                  </button>
                </div>
              </div>
              <!-- Sample queries -->
              <details v-if="c.sample_queries.length > 0" class="mt-2">
                <summary class="cursor-pointer text-xs font-semibold text-amber-700 hover:text-amber-900">
                  Похожие запросы ({{ c.sample_queries.length }}) ↓
                </summary>
                <ul class="mt-2 space-y-1">
                  <li
                    v-for="(s, si) in c.sample_queries.slice(0, 5)"
                    :key="si"
                    class="flex items-start justify-between gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs"
                  >
                    <span class="min-w-0 flex-1 text-slate-700">{{ s.query }}</span>
                    <span class="shrink-0 text-amber-700">{{ s.occurrences }}×</span>
                  </li>
                </ul>
              </details>
            </div>
          </div>

          <!-- Gap queries (no cluster yet) -->
          <div
            v-if="report.gap_queries.length > 0"
            :class="clusters.length > 0 ? 'border-t border-amber-100' : ''"
          >
            <div v-if="clusters.length > 0" class="px-4 pt-3 text-xs font-semibold uppercase tracking-wide text-amber-700">
              Отдельные запросы
            </div>
            <div class="divide-y divide-amber-50">
              <div
                v-for="g in report.gap_queries"
                :key="g.query"
                class="flex items-start gap-3 px-4 py-3"
              >
                <div class="min-w-0 flex-1">
                  <div class="text-sm text-slate-900">{{ g.query }}</div>
                  <div class="mt-1 flex flex-wrap items-center gap-2">
                    <CoverageMatchBadge
                      :score="g.top_score"
                      :hits="1"
                      :relevant-threshold="report.thresholds.relevant"
                      :irrelevant-threshold="report.thresholds.irrelevant"
                    />
                    <span v-if="g.top_title" class="text-xs text-slate-500">
                      Ближайший шаг: <em class="text-slate-700">{{ g.top_title }}</em>
                    </span>
                  </div>
                </div>
                <div class="flex shrink-0 flex-col items-end gap-1">
                  <span class="text-xs font-bold text-slate-700">{{ g.occurrences }}×</span>
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 rounded-lg border border-amber-200 bg-white px-2 py-1 text-[11px] font-semibold text-amber-800 hover:bg-amber-50 disabled:opacity-50"
                    :disabled="!!creatingFromGap"
                    @click="createFlowFromGap(g.query)"
                  >
                    <Plus class="h-3 w-3" />
                    {{ creatingFromGap === g.query ? '…' : 'Создать' }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- No-match queries -->
          <div
            v-if="report.no_match_queries.length > 0"
            class="border-t border-amber-100"
          >
            <div class="px-4 pt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Запросы полностью вне сценариев
            </div>
            <div class="divide-y divide-slate-50">
              <div
                v-for="g in report.no_match_queries"
                :key="g.query"
                class="flex items-center gap-3 px-4 py-2.5"
              >
                <div class="min-w-0 flex-1 text-sm text-slate-700">{{ g.query }}</div>
                <div class="flex shrink-0 items-center gap-2">
                  <span class="text-xs font-bold text-slate-700">{{ g.occurrences }}×</span>
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    :disabled="!!creatingFromGap"
                    @click="createFlowFromGap(g.query)"
                  >
                    <Plus class="h-3 w-3" />
                    {{ creatingFromGap === g.query ? '…' : 'Создать' }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div
            v-if="clusters.length === 0 && report.gap_queries.length === 0 && report.no_match_queries.length === 0"
            class="px-4 py-8 text-center text-sm text-slate-500"
          >
            Нет пробелов. Все запросы ассистента покрыты сценариями.
          </div>
        </CoverageSection>

        <!-- ❺ Какие сценарии работают -->
        <CoverageSection
          title="Какие шаги работают"
          subtitle="Шаги сценариев, которые ассистент находил чаще всего за этот период"
          :icon="Target"
          tone="emerald"
          :default-open="false"
          :count="report.top_tactics.length || null"
        >
          <div v-if="report.top_tactics.length === 0" class="px-4 py-8 text-center text-sm text-slate-500">
            За этот период ни один шаг не сработал с точным совпадением.
          </div>
          <ol v-else class="divide-y divide-emerald-50">
            <li v-for="(t, i) in report.top_tactics" :key="t.node_id" class="px-4 py-4">
              <div class="flex items-start gap-3">
                <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs font-bold text-emerald-700">
                  {{ i + 1 }}
                </span>
                <div class="min-w-0 flex-1">
                  <div class="text-sm font-semibold text-slate-900">{{ t.title || 'Шаг без названия' }}</div>
                  <div class="mt-1 flex flex-wrap items-center gap-2">
                    <span class="text-xs text-slate-500">Найден <strong class="text-slate-800">{{ t.hit_count }}×</strong></span>
                    <CoverageMatchBadge
                      :score="t.avg_score"
                      :hits="t.hit_count"
                      :relevant-threshold="report.thresholds.relevant"
                      :irrelevant-threshold="report.thresholds.irrelevant"
                    />
                  </div>

                  <!-- Application stats -->
                  <div v-if="t.scored_count > 0" class="mt-2 flex flex-wrap gap-2 text-xs">
                    <span
                      class="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5"
                      :class="appliedBadgeClass(t.applied_rate)"
                      :title="`Ассистент использовал рекомендуемые фразы в ${t.applied_count} из ${t.scored_count} ответов`"
                    >
                      {{ formatAppliedRate(t.applied_count, t.scored_count).label }}
                    </span>
                    <span
                      v-if="t.violation_count > 0"
                      class="inline-flex items-center gap-1 rounded-full border border-rose-200 bg-rose-50 px-2.5 py-0.5 text-rose-700"
                      title="Ассистент использовал фразы, которые запрещены в этом шаге"
                    >
                      Использовал запрещённые фразы {{ t.violation_count }}×
                    </span>
                    <span
                      v-if="t.followup_count > 0"
                      class="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/10 px-2.5 py-0.5 text-primary"
                      title="Ассистент задал уточняющий вопрос, предусмотренный этим шагом"
                    >
                      Задал уточняющий вопрос {{ t.followup_count }}×
                    </span>
                  </div>

                  <!-- Low compliance CTA -->
                  <div v-if="t.scored_count > 0 && t.applied_rate !== null && t.applied_rate < 0.4" class="mt-2">
                    <a
                      :href="`/agents/${agentId}/scripts`"
                      class="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 hover:text-amber-900"
                    >
                      Улучшить этот шаг →
                    </a>
                  </div>
                </div>
              </div>
            </li>
          </ol>
        </CoverageSection>

        <!-- Glossary footer -->
        <details class="rounded-xl border border-slate-200 bg-white">
          <summary class="cursor-pointer px-4 py-3 text-xs font-semibold text-slate-500 hover:text-slate-700">
            Что значат эти показатели?
          </summary>
          <div class="border-t border-slate-100 px-4 py-3 text-xs text-slate-600 space-y-1.5">
            <p><strong>Точное попадание (≥{{ Math.round(report.thresholds.relevant * 100) }}% совпадения)</strong> — ассистент нашёл шаг сценария, который точно подходит к ситуации.</p>
            <p><strong>Близкая тема ({{ Math.round(report.thresholds.irrelevant * 100) }}–{{ Math.round(report.thresholds.relevant * 100) }}%)</strong> — шаг похож, но не идеален. Стоит дописать сценарий под эту ситуацию.</p>
            <p><strong>Не подходит (≤{{ Math.round(report.thresholds.irrelevant * 100) }}%)</strong> — ассистент нашёл что-то, но совсем не то. Нужен новый сценарий.</p>
            <p><strong>Сценария нет</strong> — поиск не вернул ничего. В вашей библиотеке нет сценария для этой темы.</p>
            <p><strong>Соблюдение шага</strong> — как часто ассистент использовал рекомендуемые фразы из этого шага при ответе клиенту.</p>
            <p><strong>Ассистент работал без сценария</strong> — диалог содержал возражение или повод, но ассистент ответил, не обратившись к вашим сценариям.</p>
          </div>
        </details>

      </template>
    </div>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { useRoute } from 'vue-router'
import { navigateTo } from '#app'
import {
  AlertCircle,
  Activity,
  ArrowRight,
  BarChart3,
  ChevronDown,
  Lightbulb,
  Plus,
  RefreshCw,
  Sparkles,
  Target,
} from 'lucide-vue-next'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import ScriptsNav from '~/components/agents/scripts/ScriptsNav.vue'
import CoverageHealthHero from '~/components/agents/scripts/coverage/CoverageHealthHero.vue'
import CoverageMatchBadge from '~/components/agents/scripts/coverage/CoverageMatchBadge.vue'
import CoverageSection from '~/components/agents/scripts/coverage/CoverageSection.vue'
import { useApiFetch } from '~/composables/useApiFetch'
import { useAuth } from '~/composables/useAuth'
import { useScriptFlows } from '~/composables/useScriptFlows'
import {
  formatAppliedRate,
  formatMissedClass,
  periodLabel as formatPeriodLabel,
  toneClasses,
} from '~/utils/scriptFlowCoverageFormat'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})

// ── Types ────────────────────────────────────────────────────────────────────

interface CoverageReport {
  period_days: number
  thresholds: { relevant: number; irrelevant: number }
  summary: {
    total_searches: number
    relevant_count: number
    weak_count: number
    irrelevant_count: number
    no_match_count: number
    distinct_tactics_used: number
  }
  top_tactics: Array<{
    node_id: string; title: string | null; hit_count: number; avg_score: number
    scored_count: number; applied_count: number; violation_count: number
    followup_count: number; applied_rate: number | null
  }>
  gap_queries: Array<{
    query: string; top_title: string | null; top_score: number | null
    occurrences: number; last_seen: string | null
  }>
  no_match_queries: Array<{ query: string; occurrences: number; last_seen: string | null }>
}

interface GapCluster {
  id: string; label: string; suggestion: string | null
  query_count: number; avg_score: number | null
  sample_queries: Array<{ query: string; occurrences: number; avg_score: number }>
}

interface MissedSummary {
  period_days: number
  classes: Array<{
    classification: string; count: number
    examples: Array<{
      user_message: string
      confidence: number | null
      created_at: string
      best_match: { flow_id: string; node_id: string; title: string; score: number } | null
    }>
  }>
}

interface PriorityAction {
  title: string
  detail: string
  cta: string
  urgent?: boolean
  href?: string
  onClick?: () => void
  loading?: boolean
}

// ── Constants ─────────────────────────────────────────────────────────────────

const PERIOD_OPTIONS = [
  { days: 1, label: 'Сегодня' },
  { days: 7, label: 'Неделя' },
  { days: 30, label: 'Месяц' },
]

const MISSED_PERIOD_OPTIONS = [
  { h: 24, label: '24ч' },
  { h: 48, label: '48ч' },
  { h: 168, label: 'Неделя' },
]

// ── State ─────────────────────────────────────────────────────────────────────

const route = useRoute()
const agentId = computed(() => String(route.params.id))
const apiFetch = useApiFetch()
const { token } = useAuth()
const { createFlow } = useScriptFlows(agentId.value)

const periodDays = ref(7)
const report = ref<CoverageReport | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const clusters = ref<GapCluster[]>([])
const clusteringLoading = ref(false)
const missed = ref<MissedSummary>({ period_days: 7, classes: [] })
const missedLoading = ref(false)
const missedSettingsOpen = ref(false)
const missedPeriodHours = ref(24)
const missedMaxRuns = ref(60)
const creatingFromGap = ref<string | null>(null)
const missedSettingsRef = ref<HTMLElement | null>(null)
onClickOutside(missedSettingsRef, () => { missedSettingsOpen.value = false })

// ── Computed ──────────────────────────────────────────────────────────────────

const currentPeriodLabel = computed(() => formatPeriodLabel(periodDays.value))

const totalMissed = computed(() =>
  missed.value.classes.reduce((acc, c) => acc + c.count, 0),
)

const priorityActions = computed<PriorityAction[]>(() => {
  if (!report.value) return []
  const s = report.value.summary
  const actions: PriorityAction[] = []

  // Missed calls — самое критичное (ассистент вообще игнорирует сценарии)
  if (totalMissed.value > 0) {
    actions.push({
      title: `Ассистент ${totalMissed.value} раз ответил без сценария`,
      detail: 'Добавьте в инструкцию ассистента явное указание искать сценарий при возражениях и поводах.',
      cta: 'К инструкции',
      urgent: true,
      href: `/agents/${agentId.value}/settings`,
    })
  }

  // Топ кластер пробелов
  if (clusters.value.length > 0) {
    const top = clusters.value[0]
    actions.push({
      title: `Создать сценарий «${top.label}»`,
      detail: `${top.query_count} похожих ситуаций без подходящего сценария. ${top.suggestion ?? ''}`,
      cta: '+ Создать',
      onClick: () => void createFlowFromGap(top.label),
      loading: creatingFromGap.value === top.label,
    })
  }

  // Нет ни одного точного попадания
  if (s.total_searches > 0 && s.relevant_count === 0) {
    actions.push({
      title: 'Ни один сценарий не подошёл точно',
      detail: 'Убедитесь, что сценарии опубликованы и обновлены в памяти ассистента. Добавьте в шаги больше вариантов формулировок.',
      cta: 'К сценариям',
      href: `/agents/${agentId.value}/scripts`,
    })
  }

  // Высокий % несовпадений (>40%)
  const gapRatio = s.total_searches > 0
    ? (s.weak_count + s.irrelevant_count) / s.total_searches
    : 0
  if (gapRatio > 0.4 && report.value.gap_queries.length > 0) {
    const topGap = report.value.gap_queries[0]
    actions.push({
      title: `${Math.round(gapRatio * 100)}% ситуаций без точного сценария`,
      detail: `Чаще всего: «${topGap.query.slice(0, 80)}${topGap.query.length > 80 ? '…' : ''}»`,
      cta: '+ Создать сценарий',
      onClick: () => void createFlowFromGap(topGap.query),
      loading: creatingFromGap.value === topGap.query,
    })
  }

  // Низкое соблюдение у популярного шага
  const badTactic = report.value.top_tactics.find(
    t => t.scored_count > 0 && (t.applied_rate ?? 1) < 0.4,
  )
  if (badTactic) {
    actions.push({
      title: `Шаг «${badTactic.title || 'без названия'}» соблюдается плохо`,
      detail: `Ассистент следует ему лишь в ${Math.round((badTactic.applied_rate ?? 0) * 100)}% ответов. Перепишите рекомендуемые фразы — они должны быть конкретными.`,
      cta: 'К сценариям',
      href: `/agents/${agentId.value}/scripts`,
    })
  }

  return actions
})

// ── Helpers ───────────────────────────────────────────────────────────────────

const missedMeta = (classification: string) => formatMissedClass(classification)

const appliedBadgeClass = (rate: number | null) => {
  const { bg, border, text } = toneClasses(
    rate === null ? 'slate' : rate >= 0.7 ? 'emerald' : rate >= 0.4 ? 'amber' : 'rose',
  )
  return `${bg} ${border} ${text}`
}

// ── API ───────────────────────────────────────────────────────────────────────

const authHeaders = () => ({ Authorization: `Bearer ${token.value}` })

const fetchReport = async () => {
  loading.value = true
  error.value = null
  try {
    report.value = await apiFetch<CoverageReport>(
      `/agents/${agentId.value}/script-flows/tactic-coverage?period_days=${periodDays.value}`,
      { headers: authHeaders() },
    )
    await Promise.all([fetchClusters(), fetchMissed()])
  } catch (e: any) {
    error.value = e?.data?.detail?.message || e?.message || 'Не удалось загрузить аналитику'
  } finally {
    loading.value = false
  }
}

const fetchClusters = async () => {
  try {
    const r = await apiFetch<{ clusters: GapCluster[] }>(
      `/agents/${agentId.value}/script-flows/tactic-coverage/gap-clusters`,
      { headers: authHeaders() },
    )
    clusters.value = r.clusters || []
  } catch { /* ignore */ }
}

const recomputeClusters = async () => {
  clusteringLoading.value = true
  try {
    const r = await apiFetch<{ clusters: GapCluster[] }>(
      `/agents/${agentId.value}/script-flows/tactic-coverage/gap-clusters/recompute?period_days=${periodDays.value}`,
      { method: 'POST', headers: authHeaders() },
    )
    clusters.value = r.clusters || []
  } catch (e: any) {
    error.value = e?.data?.detail?.message || e?.message || 'Не удалось пересчитать темы'
  } finally {
    clusteringLoading.value = false
  }
}

const fetchMissed = async () => {
  try {
    missed.value = await apiFetch<MissedSummary>(
      `/agents/${agentId.value}/script-flows/tactic-coverage/missed-calls?period_days=${periodDays.value}`,
      { headers: authHeaders() },
    )
  } catch { /* ignore */ }
}

const detectMissed = async () => {
  missedLoading.value = true
  missedSettingsOpen.value = false
  try {
    const r = await apiFetch<{ detected: number; summary: MissedSummary }>(
      `/agents/${agentId.value}/script-flows/tactic-coverage/missed-calls/detect?period_hours=${missedPeriodHours.value}&max_runs=${missedMaxRuns.value}`,
      { method: 'POST', headers: authHeaders() },
    )
    missed.value = r.summary
  } catch (e: any) {
    error.value = e?.data?.detail?.message || e?.message || 'Не удалось проанализировать диалоги'
  } finally {
    missedLoading.value = false
  }
}

const createFlowFromGap = async (label: string) => {
  if (creatingFromGap.value) return
  creatingFromGap.value = label
  try {
    const name = label.length > 60 ? label.slice(0, 57) + '…' : label
    const created = await createFlow({
      name,
      flow_metadata: { when_relevant: label },
      flow_definition: {},
    })
    await navigateTo(`/agents/${agentId.value}/scripts/${created.id}?view=schema`)
  } catch {
    error.value = 'Не удалось создать сценарий'
  } finally {
    creatingFromGap.value = null
  }
}

const setPeriod = (d: number) => {
  periodDays.value = d
  void fetchReport()
}

onMounted(() => {
  void fetchReport()
})
</script>
