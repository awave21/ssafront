import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { getReadableErrorMessage } from '~/utils/api-errors'
import { useAnalysisApi } from '~/composables/analysisApi'
import { useToast } from '~/composables/useToast'
import type {
  AnalysisJob,
  AnalysisJobStatus,
  AnalysisRecommendation,
  AnalysisRecommendationsFilters,
  AnalysisReport,
  AnalysisReviewStatus,
  AnalysisScreenState,
  AnalysisStartPayload,
  AnalysisWindowHours
} from '~/types/agent-analysis'

const TERMINAL_STATUSES: AnalysisJobStatus[] = ['succeeded', 'failed', 'cancelled']
const ACTIVE_STATUSES: AnalysisJobStatus[] = ['queued', 'running']

const normalizeJobStatus = (status: unknown): AnalysisJobStatus => {
  if (status === 'queued' || status === 'running' || status === 'succeeded' || status === 'failed' || status === 'cancelled') {
    return status
  }
  return 'unknown'
}

const asRecord = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

const unwrapJobPayload = (payload: unknown): Record<string, unknown> | null => {
  const root = asRecord(payload)
  if (!root) return null

  const directCandidates: Array<Record<string, unknown> | null> = [
    root,
    asRecord(root.job),
    asRecord(root.data),
    asRecord(root.result),
    asRecord(root.payload),
  ]

  const nestedCandidates: Array<Record<string, unknown> | null> = [
    asRecord(asRecord(root.data)?.job),
    asRecord(asRecord(root.result)?.job),
    asRecord(asRecord(root.payload)?.job),
  ]

  const allCandidates = [...directCandidates, ...nestedCandidates]
  return allCandidates.find((candidate) => typeof candidate?.id === 'string' && candidate.id.length > 0) ?? null
}

const unwrapJobsCollectionPayload = (payload: unknown): unknown[] => {
  if (Array.isArray(payload)) return payload

  const root = asRecord(payload)
  if (!root) return []

  const data = asRecord(root.data)
  const result = asRecord(root.result)
  const payloadObj = asRecord(root.payload)

  const candidates: Array<unknown[] | null> = [
    Array.isArray(root.items) ? root.items : null,
    Array.isArray(root.jobs) ? root.jobs : null,
    Array.isArray(data?.items) ? (data.items as unknown[]) : null,
    Array.isArray(data?.jobs) ? (data.jobs as unknown[]) : null,
    Array.isArray(result?.items) ? (result.items as unknown[]) : null,
    Array.isArray(result?.jobs) ? (result.jobs as unknown[]) : null,
    Array.isArray(payloadObj?.items) ? (payloadObj.items as unknown[]) : null,
    Array.isArray(payloadObj?.jobs) ? (payloadObj.jobs as unknown[]) : null,
  ]

  return candidates.find((candidate) => Array.isArray(candidate)) ?? []
}

const normalizeJob = (payload: unknown): AnalysisJob | null => {
  const source = unwrapJobPayload(payload)
  if (!source) return null
  const id = source.id
  if (typeof id !== 'string' || !id) return null

  return {
    id,
    status: normalizeJobStatus(source.status),
    stage: typeof source.stage === 'string' ? source.stage : null,
    progress_pct: typeof source.progress_pct === 'number' ? source.progress_pct : null,
    period_start: typeof source.period_start === 'string' ? source.period_start : null,
    period_end: typeof source.period_end === 'string' ? source.period_end : null,
    window_hours: typeof source.window_hours === 'number' ? source.window_hours : null,
    started_at: typeof source.started_at === 'string' ? source.started_at : null,
    finished_at: typeof source.finished_at === 'string' ? source.finished_at : null,
    error_message: typeof source.error_message === 'string' ? source.error_message : null,
    created_at: typeof source.created_at === 'string' ? source.created_at : null,
    updated_at: typeof source.updated_at === 'string' ? source.updated_at : null
  }
}

const normalizeJobs = (payload: unknown): AnalysisJob[] => {
  const candidates = unwrapJobsCollectionPayload(payload)
  return candidates.map(normalizeJob).filter(Boolean) as AnalysisJob[]
}

const normalizeRecommendations = (payload: unknown) => {
  if (!payload || typeof payload !== 'object') {
    return { items: [] as AnalysisRecommendation[], total: 0, limit: 20, offset: 0 }
  }

  const root = payload as Record<string, unknown>
  const source = asRecord(root.data) ?? root
  const rawItems = Array.isArray(source.items)
    ? source.items
    : Array.isArray(source.recommendations)
      ? source.recommendations
      : []

  const items = rawItems
    .map((item) => {
      if (!item || typeof item !== 'object') return null
      const rec = item as Record<string, unknown>
      const id = rec.id
      const title = rec.title
      if (typeof id !== 'string' || typeof title !== 'string') return null
      return {
        id,
        title,
        category: typeof rec.category === 'string' ? rec.category : null,
        priority: typeof rec.priority === 'string' || typeof rec.priority === 'number' ? rec.priority : null,
        confidence: typeof rec.confidence === 'number' ? rec.confidence : null,
        reasoning: typeof rec.reasoning === 'string' ? rec.reasoning : null,
        suggestion: typeof rec.suggestion === 'string' ? rec.suggestion : null,
        impact: typeof rec.impact === 'string' ? rec.impact : null,
        evidence_dialog_ids: Array.isArray(rec.evidence_dialog_ids) ? rec.evidence_dialog_ids.filter((value) => typeof value === 'string') : [],
        status:
          rec.status === 'accepted' || rec.status === 'rejected'
            ? rec.status
            : rec.status === 'open' || rec.status === 'pending'
              ? 'pending'
              : 'pending',
        review_comment: typeof rec.review_comment === 'string' ? rec.review_comment : null,
        reviewed_at: typeof rec.reviewed_at === 'string' ? rec.reviewed_at : null,
      } satisfies AnalysisRecommendation
    })
    .filter(Boolean) as AnalysisRecommendation[]

  return {
    items,
    total: typeof source.total === 'number' ? source.total : items.length,
    limit: typeof source.limit === 'number' ? source.limit : 20,
    offset: typeof source.offset === 'number' ? source.offset : 0,
  }
}

const normalizeReport = (payload: unknown): AnalysisReport | null => {
  const root = asRecord(payload)
  if (!root) return null
  const source = asRecord(root.data) ?? root

  return {
    summary: typeof source.summary === 'string' ? source.summary : null,
    kpis: asRecord(source.kpis) as AnalysisReport['kpis'],
    topics: Array.isArray(source.topics) ? (source.topics as AnalysisReport['topics']) : [],
    top_failure_topics: Array.isArray(source.top_failure_topics)
      ? source.top_failure_topics.filter((value): value is string => typeof value === 'string')
      : [],
    meta: asRecord(source.meta) as AnalysisReport['meta']
  }
}

const sortJobsByCreatedAtDesc = (jobs: AnalysisJob[]) =>
  [...jobs].sort((left, right) => {
    const leftDate = left.created_at ? new Date(left.created_at).getTime() : 0
    const rightDate = right.created_at ? new Date(right.created_at).getTime() : 0
    return rightDate - leftDate
  })

const resolvePriorityJob = (jobs: AnalysisJob[]) => {
  const active = jobs.find((job) => ACTIVE_STATUSES.includes(job.status))
  if (active) return active
  return sortJobsByCreatedAtDesc(jobs)[0] ?? null
}

const createIdempotencyKey = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `analysis-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export const useAgentAnalysis = (agentIdGetter: () => string) => {
  const api = useAnalysisApi()
  const { success: toastSuccess, error: toastError } = useToast()

  const screenState = ref<AnalysisScreenState>('initial')
  const isBootstrapping = ref(false)
  const isStarting = ref(false)
  const isCancelling = ref(false)
  const isLoadingReport = ref(false)
  const isLoadingRecommendations = ref(false)
  const errorMessage = ref<string | null>(null)

  const jobs = ref<AnalysisJob[]>([])
  const currentJob = ref<AnalysisJob | null>(null)
  const report = ref<AnalysisReport | null>(null)
  const recommendations = ref<AnalysisRecommendation[]>([])
  const recommendationsTotal = ref(0)
  const pollingTimer = ref<number | null>(null)

  const recommendationFilters = reactive<AnalysisRecommendationsFilters>({
    category: '',
    status: 'all',
    limit: 20,
    offset: 0
  })

  const hasActiveJob = computed(() => Boolean(currentJob.value && ACTIVE_STATUSES.includes(currentJob.value.status)))
  const canCancelCurrentJob = computed(() => Boolean(currentJob.value && ACTIVE_STATUSES.includes(currentJob.value.status)))
  const canStartNewJob = computed(() => !hasActiveJob.value)
  const isTerminalJob = computed(() => Boolean(currentJob.value && TERMINAL_STATUSES.includes(currentJob.value.status)))
  const hasReport = computed(() => Boolean(report.value))

  const categories = computed(() => {
    const set = new Set<string>()
    recommendations.value.forEach((item) => {
      if (item.category) set.add(item.category)
    })
    return Array.from(set.values())
  })

  const terminalWithError = computed(() =>
    currentJob.value?.status === 'failed' ? currentJob.value.error_message || 'Задача завершилась с ошибкой' : null
  )

  const stopPolling = () => {
    if (pollingTimer.value === null) return
    window.clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }

  const fetchRecommendations = async (override?: Partial<AnalysisRecommendationsFilters>) => {
    const agentId = agentIdGetter()
    if (!agentId) return
    isLoadingRecommendations.value = true

    if (override?.offset !== undefined) recommendationFilters.offset = override.offset
    if (override?.limit !== undefined) recommendationFilters.limit = override.limit
    if (override?.category !== undefined) recommendationFilters.category = override.category
    if (override?.status !== undefined) recommendationFilters.status = override.status

    try {
      const response = await api.getAnalysisRecommendations(agentId, recommendationFilters)
      const normalized = normalizeRecommendations(response)
      recommendations.value = normalized.items
      recommendationsTotal.value = normalized.total
      if (normalized.items.length === 0 && !hasReport.value && !hasActiveJob.value) {
        screenState.value = 'empty'
      } else if (!errorMessage.value) {
        screenState.value = 'ready'
      }
    } catch (error: any) {
      console.error('[analysis] failed to fetch recommendations', error)
      toastError('Ошибка загрузки рекомендаций', getReadableErrorMessage(error, 'Не удалось загрузить рекомендации'))
    } finally {
      isLoadingRecommendations.value = false
    }
  }

  const debouncedFetchRecommendations = useDebounceFn(() => {
    void fetchRecommendations({ offset: 0 })
  }, 350)

  const fetchReport = async (jobId: string) => {
    const agentId = agentIdGetter()
    if (!agentId || !jobId) return
    isLoadingReport.value = true
    try {
      const response = await api.getAnalysisReport(agentId, jobId)
      report.value = normalizeReport(response)
      screenState.value = 'ready'
    } catch (error: any) {
      console.error('[analysis] failed to fetch report', error)
      toastError('Ошибка загрузки отчёта', getReadableErrorMessage(error, 'Не удалось загрузить отчет анализа'))
    } finally {
      isLoadingReport.value = false
    }
  }

  const fetchCurrentJob = async () => {
    const agentId = agentIdGetter()
    if (!agentId || !currentJob.value) return null
    const response = await api.getAnalysisJob(agentId, currentJob.value.id)
    const normalized = normalizeJob(response)
    if (!normalized) return null
    currentJob.value = normalized

    const index = jobs.value.findIndex((item) => item.id === normalized.id)
    if (index !== -1) {
      jobs.value[index] = normalized
    } else {
      jobs.value.unshift(normalized)
    }

    return normalized
  }

  const ensureReportAndRecommendations = async (job: AnalysisJob | null) => {
    if (!job) return
    if (job.status !== 'succeeded') return
    await fetchReport(job.id)
    await fetchRecommendations()
  }

  const refreshJobState = async () => {
    try {
      const latestJob = await fetchCurrentJob()
      if (!latestJob) return
      if (TERMINAL_STATUSES.includes(latestJob.status)) {
        stopPolling()
        if (latestJob.status === 'succeeded') {
          await ensureReportAndRecommendations(latestJob)
        }
      }
    } catch (error: any) {
      console.error('[analysis] polling error', error)
    }
  }

  const startPolling = () => {
    stopPolling()
    pollingTimer.value = window.setInterval(() => {
      void refreshJobState()
    }, 4000)
  }

  const fetchJobs = async () => {
    const agentId = agentIdGetter()
    if (!agentId) return
    const response = await api.getAnalysisJobs(agentId)
    const normalized = normalizeJobs(response)
    jobs.value = sortJobsByCreatedAtDesc(normalized)
    currentJob.value = resolvePriorityJob(jobs.value)
  }

  const initialize = async () => {
    const agentId = agentIdGetter()
    if (!agentId) return
    screenState.value = 'loading'
    errorMessage.value = null
    isBootstrapping.value = true

    try {
      await fetchJobs()
      if (currentJob.value?.status === 'succeeded') {
        await ensureReportAndRecommendations(currentJob.value)
        return
      }
      if (currentJob.value && ACTIVE_STATUSES.includes(currentJob.value.status)) {
        screenState.value = 'ready'
        startPolling()
        return
      }
      await fetchRecommendations()
      if (recommendations.value.length > 0) {
        screenState.value = 'ready'
      } else {
        screenState.value = 'empty'
      }
    } catch (error: any) {
      console.error('[analysis] initialize error', error)
      errorMessage.value = getReadableErrorMessage(error, 'Не удалось загрузить раздел анализа')
      screenState.value = 'error'
    } finally {
      isBootstrapping.value = false
    }
  }

  const validateWindowHours = (windowHours: number): windowHours is AnalysisWindowHours =>
    windowHours === 24 || windowHours === 72 || windowHours === 168

  const startJob = async (payload: Omit<AnalysisStartPayload, 'idempotency_key'> & { idempotency_key?: string }) => {
    const agentId = agentIdGetter()
    if (!agentId) return null
    if (!validateWindowHours(payload.window_hours)) {
      toastError('Неверный период', 'Анализ можно запускать только на 24, 72 или 168 часов')
      return null
    }
    if (hasActiveJob.value) {
      toastError('Активная задача уже выполняется', 'Дождитесь завершения текущего анализа или отмените его')
      return null
    }

    isStarting.value = true
    errorMessage.value = null

    try {
      const response = await api.startAnalysisJob(agentId, {
        ...payload,
        idempotency_key: payload.idempotency_key || createIdempotencyKey()
      })
      const normalized = normalizeJob(response)
      if (!normalized) {
        throw new Error('Некорректный формат ответа запуска анализа')
      }
      currentJob.value = normalized
      report.value = null
      recommendations.value = []
      recommendationsTotal.value = 0
      jobs.value = [normalized, ...jobs.value.filter((item) => item.id !== normalized.id)]
      screenState.value = 'ready'
      toastSuccess('Анализ запущен', 'Статус задачи обновляется автоматически')
      startPolling()
      return normalized
    } catch (error: any) {
      console.error('[analysis] failed to start job', error)
      errorMessage.value = getReadableErrorMessage(error, 'Не удалось запустить анализ')
      toastError('Ошибка запуска анализа', errorMessage.value)
      return null
    } finally {
      isStarting.value = false
    }
  }

  const cancelCurrentJob = async () => {
    const agentId = agentIdGetter()
    const job = currentJob.value
    if (!agentId || !job || !ACTIVE_STATUSES.includes(job.status)) return

    isCancelling.value = true
    try {
      await api.cancelAnalysisJob(agentId, job.id)
      toastSuccess('Задача отменена', 'Анализ остановлен')
      await refreshJobState()
      stopPolling()
    } catch (error: any) {
      console.error('[analysis] failed to cancel job', error)
      toastError('Ошибка отмены анализа', getReadableErrorMessage(error, 'Не удалось отменить анализ'))
    } finally {
      isCancelling.value = false
    }
  }

  const reviewRecommendation = async (
    recommendationId: string,
    decision: Exclude<AnalysisReviewStatus, 'pending'>,
    comment?: string
  ) => {
    const agentId = agentIdGetter()
    if (!agentId) return false

    try {
      await api.reviewRecommendation(agentId, recommendationId, {
        status: decision,
        review_comment: comment?.trim() || undefined
      })

      const rec = recommendations.value.find((item) => item.id === recommendationId)
      if (rec) {
        rec.status = decision
        rec.review_comment = comment?.trim() || null
        rec.reviewed_at = new Date().toISOString()
      }

      toastSuccess('Рекомендация обновлена', 'Решение сохранено')
      return true
    } catch (error: any) {
      console.error('[analysis] failed to review recommendation', error)
      toastError('Ошибка сохранения review', getReadableErrorMessage(error, 'Не удалось сохранить решение по рекомендации'))
      return false
    }
  }

  watch(
    () => [recommendationFilters.category, recommendationFilters.status],
    () => {
      debouncedFetchRecommendations()
    }
  )

  onBeforeUnmount(() => {
    stopPolling()
  })

  return {
    screenState,
    isBootstrapping,
    isStarting,
    isCancelling,
    isLoadingReport,
    isLoadingRecommendations,
    errorMessage,
    jobs,
    currentJob,
    report,
    recommendations,
    recommendationsTotal,
    recommendationFilters,
    categories,
    hasActiveJob,
    canCancelCurrentJob,
    canStartNewJob,
    isTerminalJob,
    terminalWithError,
    initialize,
    fetchJobs,
    fetchCurrentJob,
    startJob,
    cancelCurrentJob,
    fetchRecommendations,
    reviewRecommendation,
    stopPolling,
  }
}
