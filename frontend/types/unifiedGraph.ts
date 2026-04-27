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
}

export type UnifiedGraphPreview = {
  nodes: UnifiedGraphNodeDto[]
  relations: UnifiedGraphRelationDto[]
}

/** Ответ POST …/unified-graph/ask (если эндпоинт включён на бэкенде). */
export type UnifiedGraphAskResponse = {
  answer: string
  used_nodes?: number
  used_relations?: number
}
