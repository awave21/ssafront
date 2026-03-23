export type AnalysisWindowHours = 24 | 72 | 168

export type AnalysisJobStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'unknown'

export type AnalysisJobStage = string

export type AnalysisScreenState = 'initial' | 'loading' | 'empty' | 'error' | 'ready'

export type AnalysisReviewStatus = 'pending' | 'accepted' | 'rejected'

export type AnalysisStartPayload = {
  window_hours: AnalysisWindowHours
  max_dialogs?: number
  history_limit?: number
  only_with_manager?: boolean
  max_tokens_per_job?: number
  max_llm_requests_per_job?: number
  idempotency_key?: string
  meta_model?: string
}

export type AnalysisJob = {
  id: string
  status: AnalysisJobStatus
  stage?: AnalysisJobStage | null
  progress_pct?: number | null
  period_start?: string | null
  period_end?: string | null
  window_hours?: number | null
  started_at?: string | null
  finished_at?: string | null
  error_message?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export type AnalysisTopic = {
  name: string
  share?: number | null
  dialogs_count?: number | null
  /** API: good | warning | critical (или число в старых отчётах) */
  health?: string | number | null
  /** ID диалогов (сессий), в которых проявляется тема — одна сессия ≈ одно обращение пользователя */
  evidence_dialog_ids?: string[]
}

export type AnalysisReportKpis = {
  intervention_rate?: number | null
  tool_error_rate?: number | null
  tool_argument_mismatch_rate?: number | null
  topic_count?: number | null
  recommendation_count?: number | null
}

export type AnalysisReportMeta = {
  analysis_as_of?: string | null
  analyzer_version?: string | null
  model_name?: string | null
}

export type AnalysisReport = {
  summary?: string | null
  kpis?: AnalysisReportKpis | null
  topics?: AnalysisTopic[]
  top_failure_topics?: string[]
  meta?: AnalysisReportMeta | null
}

export type AnalysisRecommendation = {
  id: string
  title: string
  category?: string | null
  priority?: string | number | null
  confidence?: number | null
  reasoning?: string | null
  suggestion?: string | null
  impact?: string | null
  evidence_dialog_ids?: string[]
  status?: AnalysisReviewStatus | null
  review_comment?: string | null
  reviewed_at?: string | null
}

export type AnalysisRecommendationsResponse = {
  items: AnalysisRecommendation[]
  total: number
  limit: number
  offset: number
}

export type AnalysisRecommendationsFilters = {
  category?: string
  status?: AnalysisReviewStatus | 'all'
  limit?: number
  offset?: number
}

export type AnalysisRecommendationReviewPayload = {
  status: Exclude<AnalysisReviewStatus, 'pending'>
  review_comment?: string
}

export type ApiErrorShape = {
  status?: number
  message?: string
  data?: {
    error?: string
    message?: string
    detail?: string
  }
}
