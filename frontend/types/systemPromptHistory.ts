/** Элемент списка версий (без полного текста промпта) */
export type SystemPromptVersionListItem = {
  id: string
  agent_id: string
  version_number: number
  change_summary: string | null
  triggered_by: 'create' | 'update' | 'publish' | 'manual' | 'ai_training'
  is_active: boolean
  created_by: string | null
  created_at: string
  prompt_length: number
}

/** Полная версия (с текстом промпта) */
export type SystemPromptVersionRead = {
  id: string
  agent_id: string
  tenant_id: string
  version_number: number
  system_prompt: string
  change_summary: string | null
  triggered_by: 'create' | 'update' | 'publish' | 'manual' | 'ai_training'
  is_active: boolean
  created_by: string | null
  created_at: string
  updated_at: string | null
}

/** Обёртка списка с cursor-пагинацией */
export type SystemPromptVersionListResponse = {
  items: SystemPromptVersionListItem[]
  next_cursor: number | null
}

/** Тело POST-запроса для создания версии */
export type SystemPromptVersionCreate = {
  system_prompt: string
  change_summary?: string | null
  activate?: boolean
}

/** Человекочитаемые подписи triggered_by */
export const TRIGGERED_BY_LABELS: Record<string, string> = {
  create: 'Создание агента',
  update: 'Обновление',
  publish: 'Публикация',
  manual: 'Ручное изменение',
  ai_training: 'AI обучение',
}
