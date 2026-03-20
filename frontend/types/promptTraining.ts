export type TrainingSessionStatus = 'active' | 'completed' | 'cancelled'

export type FeedbackType = 'positive' | 'negative' | 'correction' | 'instruction'

export type TrainingFeedbackRead = {
  id: string
  session_id: string
  feedback_type: FeedbackType
  run_id: string | null
  agent_response: string | null
  correction_text: string
  created_at: string
}

export type TrainingSessionRead = {
  id: string
  agent_id: string
  tenant_id: string
  created_by: string
  status: TrainingSessionStatus
  feedback_count: number
  base_prompt_version: number | null
  generated_prompt: string | null
  generated_prompt_reasoning: string | null
  generated_version_id: string | null
  meta_model: string
  agent_model: string | null
  feedbacks: readonly TrainingFeedbackRead[]
  created_at: string
  updated_at: string | null
}

export type TrainingSessionsListResponse = {
  items: TrainingSessionRead[]
  next_cursor: string | null
}

export type CreateSessionPayload = {
  meta_model?: string | null
}

export type CreateFeedbackPayload = {
  feedback_type: FeedbackType
  run_id?: string | null
  agent_response?: string | null
  correction_text: string
}

export type GeneratePromptRequest = {
  meta_model?: string | null
}

export type GeneratedPromptPreview = {
  current_prompt: string
  generated_prompt: string
  reasoning: string
  change_summary: string
  feedback_used: number
  meta_model: string
  agent_model: string
}

export const SESSION_STATUS_LABELS: Record<TrainingSessionStatus, string> = {
  active: 'Активна',
  completed: 'Завершена',
  cancelled: 'Отменена',
}

export const FEEDBACK_TYPE_LABELS: Record<FeedbackType, string> = {
  positive: 'Одобрение',
  negative: 'Коррекция',
  correction: 'Исправление',
  instruction: 'Правило',
}
