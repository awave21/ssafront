<template>
  <AgentPageShell title="Покрытие тактик скриптами" :hide-actions="true" :contained="true">
    <div class="max-w-full space-y-6">
      <!-- Header: nav + period selector -->
      <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <ScriptsNav :agent-id="agentId" active="coverage" />
        <div class="flex flex-wrap items-center gap-2 lg:justify-end">
        <div class="inline-flex rounded-xl border border-slate-200 bg-white p-1">
          <button
            v-for="d in [1, 7, 30]"
            :key="d"
            type="button"
            class="h-8 rounded-lg px-3 text-xs font-semibold transition-colors"
            :class="periodDays === d ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'"
            @click="setPeriod(d)"
          >
            {{ d === 1 ? '24 часа' : d + ' дней' }}
          </button>
        </div>
        <button
          type="button"
          class="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          :disabled="loading"
          @click="fetchReport()"
        >
          {{ loading ? 'Обновление…' : 'Обновить' }}
        </button>
        </div>
      </div>

      <div v-if="error" class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {{ error }}
      </div>

      <div v-if="loading && !report" class="py-12 text-center text-slate-500">Загружаем аналитику…</div>

      <template v-else-if="report">
        <!-- Summary cards -->
        <div class="grid grid-cols-2 gap-3 md:grid-cols-5">
          <div class="rounded-xl border border-slate-200 bg-white p-4">
            <div class="text-xs uppercase tracking-wide text-slate-500">Всего запросов</div>
            <div class="mt-1 text-2xl font-bold text-slate-900">{{ report.summary.total_searches }}</div>
          </div>
          <div class="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <div class="text-xs uppercase tracking-wide text-emerald-700">Релевантные</div>
            <div class="mt-1 text-2xl font-bold text-emerald-900">
              {{ report.summary.relevant_count }}
              <span class="ml-1 text-sm font-normal text-emerald-700">{{ pct(report.summary.relevant_count) }}</span>
            </div>
            <div class="text-[11px] text-emerald-700">score ≥ {{ report.thresholds.relevant }}</div>
          </div>
          <div class="rounded-xl border border-amber-200 bg-amber-50 p-4">
            <div class="text-xs uppercase tracking-wide text-amber-700">Слабые</div>
            <div class="mt-1 text-2xl font-bold text-amber-900">
              {{ report.summary.weak_count }}
              <span class="ml-1 text-sm font-normal text-amber-700">{{ pct(report.summary.weak_count) }}</span>
            </div>
            <div class="text-[11px] text-amber-700">{{ report.thresholds.irrelevant }} – {{ report.thresholds.relevant }}</div>
          </div>
          <div class="rounded-xl border border-rose-200 bg-rose-50 p-4">
            <div class="text-xs uppercase tracking-wide text-rose-700">Мимо тактики</div>
            <div class="mt-1 text-2xl font-bold text-rose-900">
              {{ report.summary.irrelevant_count }}
              <span class="ml-1 text-sm font-normal text-rose-700">{{ pct(report.summary.irrelevant_count) }}</span>
            </div>
            <div class="text-[11px] text-rose-700">score ≤ {{ report.thresholds.irrelevant }}</div>
          </div>
          <div class="rounded-xl border border-slate-300 bg-slate-50 p-4">
            <div class="text-xs uppercase tracking-wide text-slate-600">Без матча</div>
            <div class="mt-1 text-2xl font-bold text-slate-900">
              {{ report.summary.no_match_count }}
              <span class="ml-1 text-sm font-normal text-slate-700">{{ pct(report.summary.no_match_count) }}</span>
            </div>
            <div class="text-[11px] text-slate-600">0 хитов</div>
          </div>
        </div>

        <div class="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
          Использовано <strong>{{ report.summary.distinct_tactics_used }}</strong>
          уникальных тактик из всех опубликованных. Чем больше «слабых» и «мимо» —
          тем больше пробелов в библиотеке скриптов.
        </div>

        <!-- Top tactics + gaps -->
        <div class="grid gap-4 lg:grid-cols-2">
          <!-- Top tactics -->
          <section class="rounded-xl border border-slate-200 bg-white">
            <header class="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <h2 class="text-sm font-bold text-slate-900">Самые востребованные тактики</h2>
              <span class="text-xs text-slate-500">релевантные срабатывания</span>
            </header>
            <div v-if="report.top_tactics.length === 0" class="p-6 text-center text-sm text-slate-500">
              За период ни одна тактика не сработала с релевантным score.
            </div>
            <ol v-else class="divide-y divide-slate-100">
              <li v-for="(t, i) in report.top_tactics" :key="t.node_id" class="px-4 py-3">
                <div class="flex items-center gap-3">
                  <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs font-bold text-emerald-700">
                    {{ i + 1 }}
                  </span>
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-sm font-semibold text-slate-900">{{ t.title || t.node_id }}</div>
                    <div class="text-xs text-slate-500">
                      <code class="text-[10px]">{{ t.node_id }}</code>
                    </div>
                  </div>
                  <div class="text-right">
                    <div class="text-sm font-bold text-slate-900">{{ t.hit_count }}×</div>
                    <div class="text-xs text-emerald-600">avg {{ t.avg_score.toFixed(2) }}</div>
                  </div>
                </div>
                <!-- Stage 3 metrics: applied/violation/followup -->
                <div v-if="t.scored_count > 0" class="ml-10 mt-2 flex flex-wrap gap-2 text-[11px]">
                  <span
                    class="rounded-full border px-2 py-0.5"
                    :class="appliedClass(t.applied_rate)"
                    :title="`LLM использовала рекомендуемые фразы в ${t.applied_count} из ${t.scored_count} ответов`"
                  >
                    Применена {{ t.applied_count }}/{{ t.scored_count }}
                    <span v-if="t.applied_rate !== null" class="font-semibold">
                      · {{ Math.round(t.applied_rate * 100) }}%
                    </span>
                  </span>
                  <span
                    v-if="t.violation_count > 0"
                    class="rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-rose-700"
                    :title="`LLM использовала запрещённые фразы в ${t.violation_count} ответах`"
                  >
                    Нарушений {{ t.violation_count }}
                  </span>
                  <span
                    v-if="t.followup_count > 0"
                    class="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-indigo-700"
                    :title="`Обязательный вопрос задан в ${t.followup_count} ответах`"
                  >
                    Followup {{ t.followup_count }}
                  </span>
                </div>
              </li>
            </ol>
          </section>

          <!-- Gap queries -->
          <section class="rounded-xl border border-amber-200 bg-amber-50/40">
            <header class="flex items-center justify-between border-b border-amber-200 px-4 py-3">
              <h2 class="text-sm font-bold text-amber-900">Пробелы — нужны новые тактики</h2>
              <span class="text-xs text-amber-700">слабый/мимо матч</span>
            </header>
            <div v-if="report.gap_queries.length === 0" class="p-6 text-center text-sm text-amber-700">
              Нет запросов со слабым матчем. Скрипты покрывают всё, что спрашивает LLM.
            </div>
            <ol v-else class="divide-y divide-amber-100">
              <li v-for="g in report.gap_queries" :key="g.query" class="px-4 py-3">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0 flex-1 text-sm text-slate-900">{{ g.query }}</div>
                  <div class="text-right text-xs">
                    <div class="font-bold text-amber-900">{{ g.occurrences }}×</div>
                    <div :class="scoreClass(g.top_score)">
                      {{ g.top_score !== null ? g.top_score.toFixed(2) : '—' }}
                    </div>
                  </div>
                </div>
                <div v-if="g.top_title" class="mt-1 text-xs text-slate-500">
                  ближайшая тактика: <em class="text-slate-700">{{ g.top_title }}</em>
                </div>
              </li>
            </ol>
          </section>
        </div>

        <!-- No-match -->
        <section v-if="report.no_match_queries.length > 0" class="rounded-xl border border-slate-300 bg-white">
          <header class="border-b border-slate-100 px-4 py-3">
            <h2 class="text-sm font-bold text-slate-900">Запросы без единого матча</h2>
            <p class="text-xs text-slate-500">LLM искала тактику, но индекс ничего не вернул вообще.</p>
          </header>
          <ol class="divide-y divide-slate-100">
            <li v-for="g in report.no_match_queries" :key="g.query" class="flex items-center gap-3 px-4 py-3">
              <div class="min-w-0 flex-1 text-sm text-slate-700">{{ g.query }}</div>
              <div class="text-xs font-bold text-slate-900">{{ g.occurrences }}×</div>
            </li>
          </ol>
        </section>

        <!-- Stage 4: gap clusters -->
        <section class="rounded-xl border border-amber-200 bg-white">
          <header class="flex items-center justify-between border-b border-amber-200 px-4 py-3">
            <div>
              <h2 class="text-sm font-bold text-slate-900">Кластеры пробелов — темы для новых сценариев</h2>
              <p class="text-xs text-slate-500">
                LLM группирует похожие запросы со слабым/нулевым матчем и предлагает темы.
              </p>
            </div>
            <button
              type="button"
              class="inline-flex items-center gap-2 rounded-xl bg-amber-600 px-4 py-2 text-xs font-bold text-white hover:bg-amber-700 disabled:opacity-50"
              :disabled="clusteringLoading"
              @click="recomputeClusters()"
            >
              {{ clusteringLoading ? 'Кластеризую…' : 'Пересчитать кластеры' }}
            </button>
          </header>
          <div v-if="clusters.length === 0" class="p-6 text-center text-sm text-slate-500">
            Нет кластеров. Нажмите «Пересчитать», чтобы LLM сгруппировала запросы.
          </div>
          <ol v-else class="divide-y divide-amber-100">
            <li v-for="c in clusters" :key="c.id" class="px-4 py-3">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <div class="text-sm font-bold text-slate-900">{{ c.label }}</div>
                  <div v-if="c.suggestion" class="mt-1 text-xs text-slate-600">→ {{ c.suggestion }}</div>
                </div>
                <div class="text-right">
                  <div class="text-sm font-bold text-amber-900">{{ c.query_count }} запр.</div>
                  <div v-if="c.avg_score !== null" class="text-xs text-amber-700">
                    avg {{ c.avg_score.toFixed(2) }}
                  </div>
                </div>
              </div>
              <ul class="mt-2 space-y-1">
                <li v-for="(s, i) in c.sample_queries.slice(0, 4)" :key="i" class="text-xs text-slate-700">
                  • {{ s.query }}
                  <span class="text-slate-400">({{ s.occurrences }}× · {{ s.avg_score.toFixed(2) }})</span>
                </li>
              </ul>
            </li>
          </ol>
        </section>

        <!-- Stage 5: missed tool calls -->
        <section class="rounded-xl border border-rose-200 bg-white">
          <header class="flex items-center justify-between border-b border-rose-200 px-4 py-3">
            <div>
              <h2 class="text-sm font-bold text-slate-900">Упущенные вызовы тула</h2>
              <p class="text-xs text-slate-500">
                Реплики клиентов классифицированы как objection/trigger/closing/concern,
                но <code>search_expert_tactics</code> не вызывался.
              </p>
            </div>
            <button
              type="button"
              class="inline-flex items-center gap-2 rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white hover:bg-rose-700 disabled:opacity-50"
              :disabled="missedLoading"
              @click="detectMissed()"
            >
              {{ missedLoading ? 'Анализирую…' : 'Анализировать за 24ч' }}
            </button>
          </header>
          <div v-if="missed.classes.length === 0" class="p-6 text-center text-sm text-slate-500">
            Нет данных. Нажмите «Анализировать», чтобы LLM классифицировала последние диалоги.
          </div>
          <div v-else class="divide-y divide-rose-100">
            <div v-for="cl in missed.classes" :key="cl.classification" class="px-4 py-3">
              <div class="flex items-center justify-between">
                <div class="text-sm font-bold uppercase tracking-wide text-rose-900">
                  {{ classificationLabel(cl.classification) }}
                </div>
                <div class="text-sm font-bold text-rose-900">{{ cl.count }} случаев</div>
              </div>
              <ul class="mt-2 space-y-1">
                <li v-for="(e, i) in cl.examples" :key="i" class="text-xs text-slate-700">
                  • {{ e.user_message.slice(0, 200) }}{{ e.user_message.length > 200 ? '…' : '' }}
                </li>
              </ul>
            </div>
          </div>
        </section>
      </template>
    </div>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import ScriptsNav from '~/components/agents/scripts/ScriptsNav.vue'
import { useApiFetch } from '~/composables/useApiFetch'
import { useAuth } from '~/composables/useAuth'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})

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
    node_id: string; title: string | null; hit_count: number; avg_score: number;
    scored_count: number; applied_count: number; violation_count: number;
    followup_count: number; applied_rate: number | null;
  }>
  gap_queries: Array<{ query: string; top_title: string | null; top_score: number | null; occurrences: number; last_seen: string | null }>
  no_match_queries: Array<{ query: string; occurrences: number; last_seen: string | null }>
}
interface GapCluster {
  id: string; label: string; suggestion: string | null;
  query_count: number; avg_score: number | null;
  sample_queries: Array<{ query: string; occurrences: number; avg_score: number }>
}
interface MissedSummary {
  period_days: number;
  classes: Array<{
    classification: string; count: number;
    examples: Array<{ user_message: string; confidence: number | null; created_at: string }>
  }>
}

const route = useRoute()
const agentId = computed(() => String(route.params.id))
const apiFetch = useApiFetch()
const { token } = useAuth()

const periodDays = ref(7)
const report = ref<CoverageReport | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const clusters = ref<GapCluster[]>([])
const clusteringLoading = ref(false)
const missed = ref<MissedSummary>({ period_days: 7, classes: [] })
const missedLoading = ref(false)

const setPeriod = (d: number) => {
  periodDays.value = d
  void fetchReport()
}

const fetchReport = async () => {
  loading.value = true
  error.value = null
  try {
    report.value = await apiFetch<CoverageReport>(
      `/agents/${agentId.value}/script-flows/tactic-coverage?period_days=${periodDays.value}`,
      { headers: { Authorization: `Bearer ${token.value}` } }
    )
    await Promise.all([fetchClusters(), fetchMissed()])
  } catch (e: any) {
    error.value = e?.data?.detail?.message || e?.message || 'Не удалось загрузить отчёт'
  } finally {
    loading.value = false
  }
}

const fetchClusters = async () => {
  try {
    const r = await apiFetch<{ clusters: GapCluster[] }>(
      `/agents/${agentId.value}/script-flows/tactic-coverage/gap-clusters`,
      { headers: { Authorization: `Bearer ${token.value}` } }
    )
    clusters.value = r.clusters || []
  } catch { /* ignore */ }
}

const recomputeClusters = async () => {
  clusteringLoading.value = true
  try {
    const r = await apiFetch<{ clusters: GapCluster[] }>(
      `/agents/${agentId.value}/script-flows/tactic-coverage/gap-clusters/recompute?period_days=${periodDays.value}`,
      { method: 'POST', headers: { Authorization: `Bearer ${token.value}` } }
    )
    clusters.value = r.clusters || []
  } catch (e: any) {
    error.value = e?.data?.detail?.message || e?.message || 'Не удалось пересчитать кластеры'
  } finally {
    clusteringLoading.value = false
  }
}

const fetchMissed = async () => {
  try {
    missed.value = await apiFetch<MissedSummary>(
      `/agents/${agentId.value}/script-flows/tactic-coverage/missed-calls?period_days=${periodDays.value}`,
      { headers: { Authorization: `Bearer ${token.value}` } }
    )
  } catch { /* ignore */ }
}

const detectMissed = async () => {
  missedLoading.value = true
  try {
    const r = await apiFetch<{ detected: number; summary: MissedSummary }>(
      `/agents/${agentId.value}/script-flows/tactic-coverage/missed-calls/detect?period_hours=24`,
      { method: 'POST', headers: { Authorization: `Bearer ${token.value}` } }
    )
    missed.value = r.summary
  } catch (e: any) {
    error.value = e?.data?.detail?.message || e?.message || 'Не удалось проанализировать'
  } finally {
    missedLoading.value = false
  }
}

const appliedClass = (rate: number | null) => {
  if (rate === null) return 'border-slate-200 bg-slate-50 text-slate-600'
  if (rate >= 0.7) return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (rate >= 0.4) return 'border-amber-200 bg-amber-50 text-amber-700'
  return 'border-rose-200 bg-rose-50 text-rose-700'
}

const classificationLabel = (c: string) => {
  const map: Record<string, string> = {
    objection: '🛑 Возражения',
    trigger: '🎯 Триггеры',
    concern: '😟 Беспокойство',
    qualification: '🔍 Уточнение',
    closing: '✅ Закрытие',
  }
  return map[c] || c
}

const pct = (n: number) => {
  const total = report.value?.summary.total_searches || 0
  if (!total) return ''
  return `(${Math.round((n / total) * 100)}%)`
}

const scoreClass = (s: number | null) => {
  if (s === null) return 'text-slate-400'
  if (s >= 0.7) return 'text-emerald-600 font-semibold'
  if (s > 0.55) return 'text-amber-600 font-semibold'
  return 'text-rose-600 font-semibold'
}

onMounted(() => {
  void fetchReport()
})
</script>
