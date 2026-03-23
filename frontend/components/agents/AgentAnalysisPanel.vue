<template>
  <div class="flex h-full min-h-0 flex-col gap-4 overflow-y-auto overflow-x-hidden overscroll-y-contain pr-1">

    <AnalysisHeader
      :current-job="currentJob"
      :subtitle="headerSubtitle"
      :can-start-new-job="canStartNewJob"
      :can-cancel-current-job="canCancelCurrentJob"
      :is-cancelling="isCancelling"
      :is-refreshing="isRefreshingJob"
      @open-dialog="isDialogOpen = true"
      @cancel="cancelCurrentJob"
      @refresh="handleRefreshJob"
    />

    <AnalysisJobProgress :current-job="currentJob" :progress="normalizedProgress" />

    <Alert v-if="terminalWithError" variant="destructive" class="py-2">
      <AlertCircle class="h-4 w-4" />
      <AlertDescription class="text-xs">{{ terminalWithError }}</AlertDescription>
    </Alert>

    <Tabs v-model:value="activeTab" class="flex flex-col gap-4">
      <TabsList class="rounded-xl border border-border bg-card p-1 shadow-sm">
        <TabsTrigger value="diagnostics" class="flex-1">
          <BarChart3 class="mr-1.5 h-3.5 w-3.5" />
          Анализ
        </TabsTrigger>
        <TabsTrigger value="prompt" class="flex-1">
          <Sparkles class="mr-1.5 h-3.5 w-3.5" />
          Улучшение промта
        </TabsTrigger>
      </TabsList>

      <TabsContent value="diagnostics">
        <AnalysisTabDiagnostics
          :agent-id="agentId"
          :kpi-cards="kpiCards"
          :tool-type-cards="toolTypeCards"
          :recommendations="recommendations"
          :report="report"
          :selected-topic-name="selectedTopicName"
          @update:selected-topic-name="selectedTopicName = $event"
        />
      </TabsContent>

      <TabsContent value="prompt">
        <AnalysisTabPrompt
          :summary="report?.summary"
          :prompt-sections="promptSections"
          :is-loading="isLoadingRecommendations"
          :pagination-label="paginationLabel"
          :can-prev-page="canPrevPage"
          :can-next-page="canNextPage"
          :review-busy-by-id="reviewBusyById"
          @review="handleReview"
          @prev-page="handlePrevPage"
          @next-page="handleNextPage"
        />
      </TabsContent>
    </Tabs>

    <Alert v-if="screenState === 'error'" variant="destructive">
      <AlertTitle>Не удалось загрузить анализ</AlertTitle>
      <AlertDescription class="flex flex-col gap-2">
        <span>{{ errorMessage || 'Попробуйте повторить позже.' }}</span>
        <Button variant="outline" size="sm" class="w-fit" @click="initialize">Повторить</Button>
      </AlertDescription>
    </Alert>

    <AnalysisStartDialog
      :open="isDialogOpen"
      :is-starting="isStarting"
      @update:open="isDialogOpen = $event"
      @start="handleStartAnalysis"
    />

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { AlertCircle, BarChart3, Sparkles } from 'lucide-vue-next'
import Alert from '~/components/ui/alert/Alert.vue'
import AlertDescription from '~/components/ui/alert/AlertDescription.vue'
import AlertTitle from '~/components/ui/alert/AlertTitle.vue'
import Button from '~/components/ui/button/Button.vue'
import Tabs from '~/components/ui/tabs/Tabs.vue'
import TabsContent from '~/components/ui/tabs/TabsContent.vue'
import TabsList from '~/components/ui/tabs/TabsList.vue'
import TabsTrigger from '~/components/ui/tabs/TabsTrigger.vue'
import { useAgentAnalysis } from '~/composables/useAgentAnalysis'
import type { AnalysisReviewStatus, AnalysisStartPayload } from '~/types/agent-analysis'
import {
  TOOL_TYPE_DEFS,
  PROMPT_SECTION_DEFS,
  formatDateTime,
  formatPercent,
} from './analysis/constants'
import AnalysisHeader from './analysis/AnalysisHeader.vue'
import AnalysisJobProgress from './analysis/AnalysisJobProgress.vue'
import AnalysisStartDialog from './analysis/AnalysisStartDialog.vue'
import AnalysisTabDiagnostics from './analysis/AnalysisTabDiagnostics.vue'
import AnalysisTabPrompt from './analysis/AnalysisTabPrompt.vue'

// ─── Маршрут ─────────────────────────────────────────────────────────────────

const route = useRoute()
const agentId = computed(() => {
  const id = route.params.id
  return Array.isArray(id) ? id[0] || '' : typeof id === 'string' ? id : ''
})

// ─── Данные и действия из composable ─────────────────────────────────────────

const {
  screenState,
  isStarting,
  isCancelling,
  isLoadingRecommendations,
  errorMessage,
  currentJob,
  report,
  recommendations,
  recommendationsTotal,
  recommendationFilters,
  canCancelCurrentJob,
  canStartNewJob,
  terminalWithError,
  initialize,
  startJob,
  cancelCurrentJob,
  fetchCurrentJob,
  fetchRecommendations,
  reviewRecommendation,
} = useAgentAnalysis(() => agentId.value)

// ─── Локальный state ──────────────────────────────────────────────────────────

const activeTab = ref('diagnostics')
const isDialogOpen = ref(false)
const isRefreshingJob = ref(false)
const selectedTopicName = ref('')
const reviewBusyById = reactive<Record<string, boolean>>({})

// ─── Вычисляемые значения ─────────────────────────────────────────────────────

const normalizedProgress = computed(() => {
  const value = currentJob.value?.progress_pct
  if (typeof value !== 'number') return 0
  return Math.min(100, Math.max(0, Math.round(value)))
})

const headerSubtitle = computed(() => {
  if (currentJob.value?.status === 'running') return 'Анализ выполняется'
  if (currentJob.value?.status === 'queued') return 'Анализ в очереди'
  if (report.value) return `Отчёт от ${formatDateTime(report.value.meta?.analysis_as_of)}`
  return 'Анализ качества и обучение агента'
})

const kpiCards = computed(() => [
  {
    label: 'Вмешательства менеджера',
    value: formatPercent(report.value?.kpis?.intervention_rate),
    description: 'Доля диалогов с ручной правкой',
    colorClass:
      (report.value?.kpis?.intervention_rate ?? 0) > 0.2 ? 'text-red-600' : 'text-foreground',
  },
  {
    label: 'Ошибки инструментов',
    value: formatPercent(report.value?.kpis?.tool_error_rate),
    description: 'Неверный выбор инструмента',
    colorClass:
      (report.value?.kpis?.tool_error_rate ?? 0) > 0.1 ? 'text-amber-600' : 'text-foreground',
  },
  {
    label: 'Ошибки аргументов',
    value: formatPercent(report.value?.kpis?.tool_argument_mismatch_rate),
    description: 'Неверные параметры вызова',
    colorClass:
      (report.value?.kpis?.tool_argument_mismatch_rate ?? 0) > 0.1 ? 'text-amber-600' : 'text-foreground',
  },
])

const toolTypeCards = computed(() => {
  const allRecs = recommendations.value
  const totalRecs = allRecs.length || 1
  return TOOL_TYPE_DEFS.map((def) => {
    const count = allRecs.filter((rec) => {
      const cat = (rec.category || '').toLowerCase()
      return def.keywords.some((kw) => cat.includes(kw))
    }).length
    return { ...def, count, share: Math.round((count / totalRecs) * 100) }
  })
})

const promptSections = computed(() => {
  const allRecs = recommendations.value
  const assignedIds = new Set<string>()

  const sections = PROMPT_SECTION_DEFS.filter((s) => s.key !== 'other').map((def) => {
    const items = allRecs.filter((rec) => {
      const cat = (rec.category || '').toLowerCase()
      return def.keywords.some((kw) => cat.includes(kw))
    })
    items.forEach((r) => assignedIds.add(r.id))
    return { ...def, items }
  })

  const otherDef = PROMPT_SECTION_DEFS.find((s) => s.key === 'other')!
  sections.push({ ...otherDef, items: allRecs.filter((r) => !assignedIds.has(r.id)) })

  return sections
})

const canPrevPage = computed(() => (recommendationFilters.offset || 0) > 0)
const canNextPage = computed(() => {
  const offset = recommendationFilters.offset || 0
  const limit = recommendationFilters.limit || 20
  return offset + limit < recommendationsTotal.value
})

const paginationLabel = computed(() => {
  if (!recommendationsTotal.value) return '0 рекомендаций'
  const offset = recommendationFilters.offset || 0
  const limit = recommendationFilters.limit || 20
  const from = offset + 1
  const to = Math.min(offset + limit, recommendationsTotal.value)
  return `${from}–${to} из ${recommendationsTotal.value}`
})

// ─── Обработчики ─────────────────────────────────────────────────────────────

const handleRefreshJob = async () => {
  if (!currentJob.value) return
  isRefreshingJob.value = true
  try {
    await fetchCurrentJob()
  } finally {
    isRefreshingJob.value = false
  }
}

const handleStartAnalysis = async (payload: Omit<AnalysisStartPayload, 'idempotency_key'>) => {
  await startJob(payload)
  isDialogOpen.value = false
}

const handleReview = async (
  recommendationId: string,
  decision: Exclude<AnalysisReviewStatus, 'pending'>
) => {
  reviewBusyById[recommendationId] = true
  try {
    await reviewRecommendation(recommendationId, decision)
  } finally {
    reviewBusyById[recommendationId] = false
  }
}

const handlePrevPage = async () => {
  const limit = recommendationFilters.limit || 20
  await fetchRecommendations({ offset: Math.max(0, (recommendationFilters.offset || 0) - limit) })
}

const handleNextPage = async () => {
  const limit = recommendationFilters.limit || 20
  await fetchRecommendations({ offset: (recommendationFilters.offset || 0) + limit })
}

// ─── Жизненный цикл ──────────────────────────────────────────────────────────

watch(() => route.params.id, async () => { await initialize() })
onMounted(async () => { await initialize() })
onBeforeUnmount(() => {})
</script>
