export type DirectQuestionFile = {
  id: string
  name: string
  url: string
  size?: number
  type?: string
}

export type DirectQuestionFollowUp = {
  enabled: boolean
  content: string
  delay_minutes: number
}

export type DirectQuestion = {
  id: string
  agent_id: string
  title: string
  content: string
  order_index?: number
  tags: string[]
  is_enabled: boolean
  interrupt_dialog: boolean
  notify_telegram: boolean
  files: DirectQuestionFile[]
  followup?: DirectQuestionFollowUp
  created_at?: string
  updated_at?: string
}

export type CreateDirectQuestionPayload = Omit<DirectQuestion, 'id' | 'agent_id' | 'created_at' | 'updated_at'>
export type UpdateDirectQuestionPayload = Partial<CreateDirectQuestionPayload>

export type DirectQuestionsImportOptions = {
  hasHeader?: boolean
  replaceAll?: boolean
  strict?: boolean
  sheetName?: string
}

export type DirectQuestionsImportResult = {
  created: number
  updated?: number
  skipped?: number
  errors?: Array<{
    row: number
    field?: string
    error: string
  }>
}

export const knowledgeVectorStatus = {
  notIndexed: 'not_indexed',
  indexing: 'indexing',
  indexed: 'indexed',
  failed: 'failed'
} as const

export type KnowledgeVectorStatus = typeof knowledgeVectorStatus[keyof typeof knowledgeVectorStatus]

export type KnowledgeTreeNode = {
  id: string
  agent_id: string
  parent_id: string | null
  title: string
  order_index: number
  created_at?: string
  updated_at?: string
}

export type KnowledgeEntry = {
  id: string
  agent_id: string
  node_id: string
  admin_title: string
  meta_tags: string[]
  content: string
  is_enabled: boolean
  vector_status: KnowledgeVectorStatus
  created_at?: string
  updated_at?: string
}

export type CreateKnowledgeNodePayload = {
  title: string
  parent_id?: string | null
}

export type UpdateKnowledgeNodePayload = Partial<Pick<KnowledgeTreeNode, 'title' | 'parent_id' | 'order_index'>>

export type CreateKnowledgeEntryPayload = Omit<
  KnowledgeEntry,
  'id' | 'agent_id' | 'vector_status' | 'created_at' | 'updated_at'
> & {
  vector_status?: KnowledgeVectorStatus
}

export type UpdateKnowledgeEntryPayload = Partial<CreateKnowledgeEntryPayload>

export const knowledgeItemType = {
  folder: 'folder',
  file: 'file'
} as const

export type KnowledgeItemType = typeof knowledgeItemType[keyof typeof knowledgeItemType]

export type KnowledgeFileItem = {
  id: string
  agent_id: string
  parent_id: string | null
  type: KnowledgeItemType
  title: string
  meta_tags: string[]
  chunk_size_chars?: number | null
  chunk_overlap_chars?: number | null
  /** Только для файлов: число чанков в векторном индексе (0 до/после переиндексации). */
  chunks_count?: number | null
  content: string
  is_enabled: boolean
  vector_status: KnowledgeVectorStatus
  order_index: number
  /** ISO-8601: когда последний раз успешно построили векторный индекс (файлы). */
  indexed_at?: string | null
  created_at?: string
  updated_at?: string
}

export type CreateKnowledgeFilePayload = {
  title: string
  parent_id?: string | null
}

export type CreateKnowledgeTextPayload = {
  title: string
  parent_id?: string | null
  meta_tags?: string[]
  content?: string
  is_enabled?: boolean
  vector_status?: KnowledgeVectorStatus
}

export const knowledgeIndexJobStatus = {
  queued: 'queued',
  indexing: 'indexing',
  indexed: 'indexed',
  failed: 'failed'
} as const

export type KnowledgeIndexJobStatus = typeof knowledgeIndexJobStatus[keyof typeof knowledgeIndexJobStatus]

export type KnowledgeIndexStartResponse = {
  job_id?: string
  file_id?: string
  status?: KnowledgeIndexJobStatus
  progress?: number
  vector_status?: KnowledgeVectorStatus
}

export type KnowledgeIndexJobStateResponse = {
  job_id: string
  file_id?: string
  status: KnowledgeIndexJobStatus
  progress?: number
  stage?: string
  chunks_total?: number | null
  chunks_done?: number | null
  indexed_at?: string | null
  error?: string | null
  vector_status?: KnowledgeVectorStatus
}

/** GET /knowledge/files/{file_id}/index-status — без поля status, зато есть vector_status файла */
export type KnowledgeFileIndexStatusResponse = {
  file_id: string
  vector_status: KnowledgeVectorStatus
  progress: number
  chunks_count?: number
  indexed_at?: string | null
  job_id?: string | null
  stage?: string | null
  error?: string | null
}
