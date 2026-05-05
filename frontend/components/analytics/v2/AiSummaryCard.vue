<template>
  <div
    class="group relative overflow-hidden rounded-3xl border border-slate-100 bg-gradient-to-br from-primary/5 via-white to-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
  >
    <div class="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-primary/10 blur-2xl"></div>

    <!-- Header -->
    <div class="relative flex items-start justify-between gap-4">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <Sparkles class="h-5 w-5" />
        </div>
        <div>
          <div class="text-[11px] font-bold uppercase tracking-[0.2em] text-primary/80">AI-аналитика</div>
          <div class="text-sm font-bold text-slate-900">Рекомендации руководителю</div>
        </div>
      </div>
      <button
        type="button"
        :disabled="loading"
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-600 shadow-sm transition-all hover:bg-slate-50 disabled:opacity-50"
        @click="$emit('refresh')"
      >
        <RefreshCw class="h-3.5 w-3.5" :class="loading && 'animate-spin'" />
        {{ loading ? 'Анализ…' : 'Обновить' }}
      </button>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading && !payload" class="mt-5 space-y-2">
      <div class="h-3 w-3/4 rounded bg-slate-100 motion-safe:animate-pulse"></div>
      <div class="h-3 w-2/3 rounded bg-slate-100 motion-safe:animate-pulse"></div>
      <div class="h-3 w-1/2 rounded bg-slate-100 motion-safe:animate-pulse"></div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!payload" class="relative mt-5 text-sm text-slate-500">
      Нажмите «Обновить», чтобы сгенерировать AI-резюме за выбранный период.
    </div>

    <!-- Content -->
    <div v-else class="relative mt-5 space-y-5">

      <!-- Headline metric + verdict -->
      <div v-if="payload.headline_metric || payload.period_verdict" class="flex flex-wrap items-center gap-3">
        <div v-if="payload.headline_metric" class="text-2xl font-black tabular-nums text-slate-900">
          {{ payload.headline_metric }}
        </div>
        <span
          v-if="payload.period_verdict"
          class="inline-flex items-center gap-1.5 rounded-xl px-3 py-1 text-xs font-black uppercase tracking-wider"
          :class="verdictClass"
        >
          <component :is="verdictIcon" class="h-3.5 w-3.5" />
          {{ verdictLabel }}
        </span>
      </div>

      <!-- Summary -->
      <p class="text-sm leading-relaxed text-slate-700">{{ payload.summary }}</p>

      <!-- Wins & Risks -->
      <div v-if="payload.wins?.length || payload.risks?.length" class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div v-if="payload.wins?.length" class="rounded-2xl bg-emerald-50 p-4">
          <div class="mb-2 text-[10px] font-black uppercase tracking-wider text-emerald-700">Что работает</div>
          <ul class="space-y-1.5">
            <li
              v-for="(win, i) in payload.wins"
              :key="i"
              class="flex items-start gap-2 text-xs text-emerald-800"
            >
              <CheckCircle2 class="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
              {{ win }}
            </li>
          </ul>
        </div>
        <div v-if="payload.risks?.length" class="rounded-2xl bg-rose-50 p-4">
          <div class="mb-2 text-[10px] font-black uppercase tracking-wider text-rose-700">Что горит</div>
          <ul class="space-y-1.5">
            <li
              v-for="(risk, i) in payload.risks"
              :key="i"
              class="flex items-start gap-2 text-xs text-rose-800"
            >
              <AlertTriangle class="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-500" />
              {{ risk }}
            </li>
          </ul>
        </div>
      </div>

      <!-- Recommendations -->
      <div v-if="sortedRecommendations.length" class="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div
          v-for="(rec, idx) in sortedRecommendations"
          :key="idx"
          class="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm transition-all hover:shadow-md"
          :class="rec.target_tab && 'cursor-pointer hover:-translate-y-0.5'"
          @click="rec.target_tab && $emit('go-to-tab', rec.target_tab)"
        >
          <!-- Priority + Impact row -->
          <div class="flex flex-wrap items-center gap-2">
            <span
              class="inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[10px] font-black uppercase tracking-wider"
              :class="priorityClass(rec.priority)"
            >
              <span class="h-1.5 w-1.5 rounded-full" :class="priorityDot(rec.priority)"></span>
              {{ priorityLabel(rec.priority) }}
            </span>
            <span
              v-if="rec.expected_impact_rub"
              class="inline-flex items-center gap-1 rounded-lg bg-emerald-50 px-2 py-0.5 text-[10px] font-black tabular-nums text-emerald-700"
            >
              <TrendingUp class="h-3 w-3" />
              +{{ fmtImpact(rec.expected_impact_rub) }}/год
            </span>
            <span
              v-if="rec.effort"
              class="inline-flex items-center gap-1 rounded-lg bg-slate-50 px-2 py-0.5 text-[10px] font-bold text-slate-600"
              :title="'Трудозатраты: ' + effortLabel(rec.effort)"
            >
              <span v-for="n in effortDots(rec.effort)" :key="n" class="h-1.5 w-1.5 rounded-full bg-slate-400"></span>
              {{ effortLabel(rec.effort) }}
            </span>
            <span
              v-if="rec.confidence"
              class="inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[10px] font-bold"
              :class="confidenceClass(rec.confidence)"
              :title="'Уверенность: ' + confidenceLabel(rec.confidence)"
            >
              <span class="h-1.5 w-1.5 rounded-full" :class="confidenceDot(rec.confidence)"></span>
              {{ confidenceLabel(rec.confidence) }}
            </span>
            <ArrowRight v-if="rec.target_tab" class="ml-auto h-3.5 w-3.5 text-slate-300 transition-colors group-hover:text-primary" />
          </div>

          <!-- Title -->
          <div class="mt-2 text-sm font-bold text-slate-900">{{ rec.title }}</div>

          <!-- Body -->
          <p class="mt-1 text-xs leading-relaxed text-slate-600">{{ rec.body }}</p>

          <!-- Root cause -->
          <p v-if="rec.root_cause" class="mt-2 text-[11px] italic text-slate-400">
            Причина: {{ rec.root_cause }}
          </p>

          <!-- Risk if ignored -->
          <div v-if="rec.risk_if_ignored" class="mt-2 rounded-xl bg-rose-50 px-3 py-2 text-[11px] text-rose-700">
            <span class="font-bold">Если не сделать:</span> {{ rec.risk_if_ignored }}
          </div>

          <!-- Target entity -->
          <div v-if="rec.target_entity" class="mt-2 text-[11px] font-medium text-slate-400">
            → {{ rec.target_entity }}
          </div>
        </div>
      </div>
    </div>

    <!-- Footer: model + cache -->
    <div v-if="model" class="relative mt-4 flex items-center gap-2 text-[10px] font-medium text-slate-400">
      <span class="h-1 w-1 rounded-full bg-slate-300"></span>
      {{ model }}<span v-if="cached" class="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-slate-500">из кэша</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Sparkles, RefreshCw, ArrowRight, CheckCircle2, AlertTriangle, TrendingUp, TrendingDown, Minus } from 'lucide-vue-next'
import type {
  AiRecommendationsPayload,
  AiRecommendationPriority,
  AiEffortLevel,
  AiConfidenceLevel,
  AiPeriodVerdict,
} from '~/types/analytics'

const props = defineProps<{
  payload: AiRecommendationsPayload | null
  loading: boolean
  cached?: boolean
  model?: string | null
}>()

defineEmits<{
  (e: 'refresh'): void
  (e: 'go-to-tab', tab: string): void
}>()

const priorityOrder: Record<AiRecommendationPriority, number> = { high: 0, medium: 1, low: 2 }

const sortedRecommendations = computed(() => {
  if (!props.payload?.recommendations) return []
  return [...props.payload.recommendations].sort((a, b) => {
    const pd = priorityOrder[a.priority] - priorityOrder[b.priority]
    if (pd !== 0) return pd
    return (b.expected_impact_rub ?? 0) - (a.expected_impact_rub ?? 0)
  })
})

// Verdict
const verdictClass = computed((): string => {
  const v = props.payload?.period_verdict
  if (v === 'positive') return 'bg-emerald-50 text-emerald-700'
  if (v === 'negative') return 'bg-rose-50 text-rose-700'
  return 'bg-slate-50 text-slate-600'
})

const verdictIcon = computed(() => {
  const v = props.payload?.period_verdict
  if (v === 'positive') return TrendingUp
  if (v === 'negative') return TrendingDown
  return Minus
})

const verdictLabel = computed((): string => {
  const v = props.payload?.period_verdict
  if (v === 'positive') return 'Хороший период'
  if (v === 'negative') return 'Проблемный период'
  return 'Нейтральный период'
})

// Priority
const priorityClass = (p: AiRecommendationPriority): string => {
  if (p === 'high') return 'bg-rose-50 text-rose-700'
  if (p === 'medium') return 'bg-amber-50 text-amber-700'
  return 'bg-slate-50 text-slate-600'
}

const priorityDot = (p: AiRecommendationPriority): string => {
  if (p === 'high') return 'bg-rose-500'
  if (p === 'medium') return 'bg-amber-500'
  return 'bg-slate-400'
}

const priorityLabel = (p: AiRecommendationPriority): string => {
  if (p === 'high') return 'Высокий'
  if (p === 'medium') return 'Средний'
  return 'Низкий'
}

// Effort
const effortDots = (e: AiEffortLevel): number[] => {
  if (e === 'low') return [1]
  if (e === 'medium') return [1, 2]
  return [1, 2, 3]
}

const effortLabel = (e: AiEffortLevel): string => {
  if (e === 'low') return 'Мало усилий'
  if (e === 'medium') return 'Средние усилия'
  return 'Много усилий'
}

// Confidence
const confidenceClass = (c: AiConfidenceLevel): string => {
  if (c === 'high') return 'bg-emerald-50 text-emerald-700'
  if (c === 'medium') return 'bg-amber-50 text-amber-700'
  return 'bg-slate-50 text-slate-500'
}

const confidenceDot = (c: AiConfidenceLevel): string => {
  if (c === 'high') return 'bg-emerald-500'
  if (c === 'medium') return 'bg-amber-500'
  return 'bg-slate-400'
}

const confidenceLabel = (c: AiConfidenceLevel): string => {
  if (c === 'high') return 'Высокая уверенность'
  if (c === 'medium') return 'Средняя уверенность'
  return 'Низкая уверенность'
}

// Impact formatting
const fmtImpact = (v: number): string => {
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + ' млн ₽'
  if (v >= 1_000) return Math.round(v / 1_000) + ' тыс ₽'
  return v.toLocaleString('ru-RU') + ' ₽'
}
</script>
