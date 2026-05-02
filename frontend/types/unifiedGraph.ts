/** Узел единого графа (D3-превью, панель деталей). */

export type UnifiedGraphNodeDto = {
  graph_node_id: string
  /** Кластер на канвасе: sqns | knowledge | directory | script_bridge */
  origin_slice: string
  entity_type: string
  title: string
  description: string | null
  domain_entity_id?: string | null
  properties?: Record<string, unknown>
  provenance_tier?: string | null
}

export type UnifiedGraphRelationDto = {
  source_graph_node_id: string
  target_graph_node_id: string
  relation_type: string
  weight?: number | null
  origin_slice?: string | null
  properties?: Record<string, unknown>
  provenance_tier?: string | null
}

export type UnifiedGraphPreview = {
  nodes: UnifiedGraphNodeDto[]
  relations: UnifiedGraphRelationDto[]
}

export type GraphSearchMethod = 'naive' | 'basic' | 'local' | 'global' | 'drift'

export type GraphPromptTemplate = {
  name: string
  content: string
}

/** Ответ POST …/unified-graph/ask. */
export type UnifiedGraphAskResponse = {
  answer: string
  method: GraphSearchMethod
  used_nodes?: number
  used_relations?: number
  total_nodes?: number
  total_relations?: number
  system_prompt?: string | null
  user_prompt?: string | null
  command?: string | null
  latency_ms?: number | null
  stderr_tail?: string | null
  prompt_templates?: GraphPromptTemplate[]
  supported_methods?: GraphSearchMethod[]
}

export type UnifiedGraphRebuildJob = {
  id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  stage: string
  progress_pct: number
  active_sqns_only: boolean
  message: string | null
  error_message: string | null
  created_at: string | null
  updated_at: string | null
  started_at: string | null
  finished_at: string | null
}

export type UnifiedGraphRebuildStartResponse = {
  status: 'accepted'
  created_new: boolean
  message: string
  job: UnifiedGraphRebuildJob
}

export type UnifiedGraphRebuildStatusResponse = {
  status: 'active' | 'idle'
  job: UnifiedGraphRebuildJob | null
}
