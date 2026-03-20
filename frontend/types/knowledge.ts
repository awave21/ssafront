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
  search_title: string
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
  content: string
  is_enabled: boolean
  vector_status: KnowledgeVectorStatus
  order_index: number
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
  error?: string | null
  vector_status?: KnowledgeVectorStatus
}
