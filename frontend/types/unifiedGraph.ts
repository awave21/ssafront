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

/** @deprecated Оставлен для backwards-compat. Виджет всегда использует neo4j_hybrid. */
export type GraphSearchMethod = 'naive' | 'basic' | 'local' | 'global' | 'drift'

export type GraphPromptTemplate = {
  name: string
  content: string
}

export type SqnsCandidate = {
  name: string
  score: number
  entity_type: string
  graph_node_id: string
  external_id: string | null
  additional_info: string | null
  information?: string | null
}

export type RetrievedNode = {
  title: string
  node_label: 'FlowNode' | 'GraphNode' | 'Service' | 'Specialist' | string
  score: number
  situation?: string | null
  approach?: string | null
  phrases?: string | null
  service_name?: string | null
  service_external_id?: number | null
  specialists: Array<{ name: string; external_id: number }>
  objections: string[]
  tactics: string[]
}

/** Ответ POST …/unified-graph/ask (режим neo4j_hybrid = как в проде). */
export type UnifiedGraphAskResponse = {
  answer: string
  retrieval_path: string
  retrieved_nodes: RetrievedNode[]
  service_candidates?: SqnsCandidate[]
  specialist_candidates?: SqnsCandidate[]
  category_candidates?: SqnsCandidate[]
  system_prompt?: string | null
  user_prompt?: string | null
  latency_ms?: number | null
  tokens?: { in: number; out: number }
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
