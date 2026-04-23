/**
 * Maps UI roles (Marika-facing) ↔ persisted node_type + ScriptNodeData flags.
 */
import { nanoid } from 'nanoid'
import type { FlowBranch, NodeRole, NodeType, ScriptNodeData } from '~/types/scriptFlow'

export type FlowLike = {
  nodes?: unknown[]
  edges?: unknown[]
  viewport?: unknown
}

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null && !Array.isArray(x)
}

function strList(raw: unknown): string[] {
  if (!Array.isArray(raw))
    return []
  return raw.map(x => String(x).trim()).filter(Boolean)
}

/** Vue Flow handle id для исходящей ветки условия */
export const branchSourceHandleId = (branchId: string): string =>
  branchId.startsWith('branch:') ? branchId : `branch:${branchId}`

/** Извлекает branch id из sourceHandle (`branch:<id>`) */
export const parseBranchHandleId = (sourceHandle: string | undefined | null): string | null => {
  const s = String(sourceHandle ?? '')
  if (!s.startsWith('branch:'))
    return null
  const id = s.slice('branch:'.length).trim()
  return id.length ? id : null
}

function parseOneConditionItem(c: unknown): FlowBranch {
  if (typeof c === 'string')
    return { id: nanoid(), label: c }
  if (isRecord(c) && typeof c.id === 'string')
    return { id: c.id, label: String(c.label ?? '') }
  return { id: nanoid(), label: String(c ?? '') }
}

/** Нормализует conditions к FlowBranch[] (из строк или объектов) */
export function normalizeConditionsToBranches(raw: unknown): FlowBranch[] {
  if (!Array.isArray(raw))
    return []
  return raw.map(c => parseOneConditionItem(c))
}

/** Wave 7: mirrors backend `script_flow_v2_migrate.migrate_flow_definition_to_v2` */
export function migrateFlowDefinitionToV2(def: Record<string, unknown>): Record<string, unknown> {
  const fd = { ...def }
  const meta = (typeof fd.flow_metadata === 'object' && fd.flow_metadata && !Array.isArray(fd.flow_metadata))
    ? fd.flow_metadata as Record<string, unknown>
    : {}
  const metaHints = strList(meta.keyword_hints)
  const nodesRaw = fd.nodes
  const nodesIn = Array.isArray(nodesRaw) ? nodesRaw : []

  const newNodes = nodesIn.map((raw) => {
    if (!isRecord(raw))
      return raw
    const node = { ...raw }
    const rawData = node.data
    const data = isRecord(rawData) ? { ...rawData } as Record<string, unknown> : {}
    const nt = String(data.node_type ?? 'expertise')

    if (nt === 'trigger') {
      const phrases = strList(data.client_phrase_examples).length ? strList(data.client_phrase_examples) : strList(data.example_phrases)
      const hints = strList(data.keyword_hints).length ? strList(data.keyword_hints) : metaHints
      const whenRel = String(data.when_relevant ?? data.situation ?? '').trim()
      const next: Record<string, unknown> = {
        node_type: 'trigger',
        client_phrase_examples: phrases,
        keyword_hints: hints,
        is_flow_entry: Boolean(data.is_flow_entry ?? data.is_entry_point ?? true),
        is_searchable: Boolean(data.is_searchable ?? data.is_entry_point ?? true),
      }
      if (data.title !== undefined && data.title !== null)
        next.title = data.title
      if (data.label !== undefined && data.label !== null)
        next.label = data.label
      if (whenRel)
        next.when_relevant = whenRel
      node.data = next
      return node
    }

    if (nt === 'question') {
      const ex = strList(data.example_phrases)
      const alt0 = strList(data.alternative_phrasings)
      const gq = String(data.good_question ?? '').trim()
      const alts = [...new Set([...alt0, ...ex.filter(x => x && x !== gq)])]
      const why = String(data.why_we_ask ?? data.situation ?? '').trim()
      const next: Record<string, unknown> = {
        node_type: 'question',
        title: data.title,
        label: data.label,
        good_question: gq,
        alternative_phrasings: alts,
        expected_answer_type: String(data.expected_answer_type ?? 'open'),
        stage: data.stage,
        level: data.level,
        service_ids: Array.isArray(data.service_ids) ? [...(data.service_ids as string[])] : [],
        employee_ids: Array.isArray(data.employee_ids) ? [...(data.employee_ids as string[])] : [],
        is_searchable: Boolean(data.is_searchable ?? data.is_entry_point ?? true),
        kg_links: isRecord(data.kg_links) ? { ...data.kg_links } : {},
      }
      if (why)
        next.why_we_ask = why
      if (data.expertise_axes && isRecord(data.expertise_axes))
        next.expertise_axes = data.expertise_axes
      node.data = next
      return node
    }

    if (nt === 'condition') {
      const rawConds = data.conditions
      const branches: FlowBranch[] = normalizeConditionsToBranches(rawConds).map((b) => {
        const id = b.id.trim() ? b.id : nanoid()
        return { id, label: b.label.trim() }
      })
      const hint = String(data.routing_hint ?? data.situation ?? '').trim()
      node.data = {
        node_type: 'condition',
        title: data.title,
        label: data.label,
        ...(hint ? { routing_hint: hint } : {}),
        conditions: branches,
      }
      return node
    }

    if (nt === 'goto') {
      const ex = strList(data.example_phrases)
      const tp = String(data.transition_phrase ?? ex[0] ?? '').trim() || null
      const ts = String(data.trigger_situation ?? data.situation ?? '').trim() || null
      node.data = {
        node_type: 'goto',
        title: data.title,
        label: data.label,
        target_flow_id: String(data.target_flow_id ?? '').trim(),
        target_node_ref: data.target_node_ref ?? null,
        ...(tp ? { transition_phrase: tp } : {}),
        ...(ts ? { trigger_situation: ts } : {}),
      }
      return node
    }

    node.data = { ...data, node_type: nt } as ScriptNodeData
    return node
  })

  return {
    ...fd,
    schema_version: 2,
    nodes: newNodes as unknown[],
  }
}

/** Persist: canonical node.data for schema_version 2 */
export function sanitizeNodeDataSchemaV2(data: Record<string, unknown>): Record<string, unknown> {
  const nt = String(data.node_type ?? 'expertise')
  const title = data.title
  const label = data.label

  if (nt === 'trigger') {
    return {
      node_type: 'trigger',
      ...(title !== undefined ? { title } : {}),
      ...(label !== undefined ? { label } : {}),
      client_phrase_examples: Array.isArray(data.client_phrase_examples)
        ? strList(data.client_phrase_examples)
        : [],
      ...(data.when_relevant ? { when_relevant: String(data.when_relevant) } : {}),
      keyword_hints: strList(data.keyword_hints),
      is_flow_entry: Boolean(data.is_flow_entry),
      is_searchable: Boolean(data.is_searchable),
      ...(typeof data.is_entry_point === 'boolean' ? { is_entry_point: data.is_entry_point } : {}),
    }
  }

  if (nt === 'question') {
    return {
      node_type: 'question',
      ...(title !== undefined ? { title } : {}),
      ...(label !== undefined ? { label } : {}),
      good_question: String(data.good_question ?? ''),
      alternative_phrasings: strList(data.alternative_phrasings),
      expected_answer_type: String(data.expected_answer_type ?? 'open'),
      ...(data.why_we_ask ? { why_we_ask: String(data.why_we_ask) } : {}),
      stage: data.stage ?? null,
      level: data.level ?? null,
      service_ids: Array.isArray(data.service_ids) ? [...data.service_ids as string[]] : [],
      employee_ids: Array.isArray(data.employee_ids) ? [...data.employee_ids as string[]] : [],
      is_searchable: Boolean(data.is_searchable),
      ...(typeof data.is_entry_point === 'boolean' ? { is_entry_point: data.is_entry_point } : {}),
      kg_links: isRecord(data.kg_links) ? data.kg_links : {},
      conditions: normalizeConditionsToBranches(data.conditions),
      ...(data.expertise_axes ? { expertise_axes: data.expertise_axes } : {}),
    }
  }

  if (nt === 'condition') {
    return {
      node_type: 'condition',
      ...(title !== undefined ? { title } : {}),
      ...(label !== undefined ? { label } : {}),
      ...(data.routing_hint ? { routing_hint: String(data.routing_hint) } : {}),
      conditions: normalizeConditionsToBranches(data.conditions),
    }
  }

  if (nt === 'goto') {
    return {
      node_type: 'goto',
      ...(title !== undefined ? { title } : {}),
      ...(label !== undefined ? { label } : {}),
      target_flow_id: String(data.target_flow_id ?? ''),
      target_node_ref: data.target_node_ref ?? null,
      ...(data.transition_phrase ? { transition_phrase: String(data.transition_phrase) } : {}),
      ...(data.trigger_situation ? { trigger_situation: String(data.trigger_situation) } : {}),
    }
  }

  return { ...data }
}

/** True if edge connects two nodes as a dialogue edge (not constraint dashed). */
function isDialogueEdge(e: Record<string, unknown>): boolean {
  const id = String(e.id ?? '')
  if (id.startsWith('cst-')) return false
  const data = e.data
  if (isRecord(data) && data.isConstraint === true) return false
  return typeof e.source === 'string' && typeof e.target === 'string'
}

/** Whether this business_rule node participates in dialogue connections. */
export function inferIsCatalogRule(
  nodeId: string,
  edges: Record<string, unknown>[] | undefined,
): boolean {
  if (!edges?.length) return true
  for (const e of edges) {
    if (!isRecord(e) || !isDialogueEdge(e)) continue
    const src = String(e.source ?? '')
    const tgt = String(e.target ?? '')
    if (src === nodeId || tgt === nodeId)
      return false
  }
  return true
}

export function inferNodeRole(data: ScriptNodeData): NodeRole {
  const nt = (data.node_type ?? 'expertise') as NodeType
  if (nt === 'question' || nt === 'condition')
    return 'question'

  if (nt === 'business_rule')
    return 'catalog_rule'

  return 'tactic'
}

/** Карточка каталога (изолированная): явно is_catalog_rule === true. */
export function isStandaloneCatalogRule(data: ScriptNodeData): boolean {
  return data.node_type === 'business_rule' && data.is_catalog_rule === true
}

function cloneData(data: unknown): ScriptNodeData {
  if (!isRecord(data)) return {}
  return { ...(data as ScriptNodeData) }
}

/** Разделение «точка входа в поток» vs «участвует в поиске» (волна 3.1). */
export function migrateEntryFlags(data: ScriptNodeData): void {
  const nt = (data.node_type ?? 'expertise') as NodeType
  if (data.is_searchable === undefined) {
    if (nt === 'trigger' || nt === 'expertise' || nt === 'question')
      data.is_searchable = data.is_entry_point !== false
    else
      data.is_searchable = false
  }
  if (data.is_flow_entry === undefined)
    data.is_flow_entry = nt === 'trigger' && data.is_entry_point !== false
}

function migrateConditionsOnNode(out: Record<string, unknown>): void {
  const data = cloneData(out.data)
  const nt = data.node_type
  if (nt !== 'question' && nt !== 'condition') {
    out.data = data
    return
  }

  delete (data as Record<string, unknown>).branches

  const raw = data.conditions
  if (!Array.isArray(raw) || raw.length === 0) {
    out.data = data
    return
  }

  data.conditions = normalizeConditionsToBranches(raw)
  out.data = data
}

/** Переназначает рёбра с `cond-{i}` на `branch:{stableId}` */
function remapConditionEdges(
  nodes: Record<string, unknown>[],
  edges: Record<string, unknown>[],
): void {
  const branchListBySourceId = new Map<string, FlowBranch[]>()

  for (const raw of nodes) {
    if (!isRecord(raw)) continue
    const nid = String(raw.id ?? '')
    const data = cloneData(raw.data)
    if (data.node_type !== 'condition' && data.node_type !== 'question')
      continue
    const conds = data.conditions
    if (!Array.isArray(conds) || !conds.length)
      continue
    const branches = normalizeConditionsToBranches(conds)
    branchListBySourceId.set(nid, branches)
  }

  for (const e of edges) {
    const src = String(e.source ?? '')
    const sh = String(e.sourceHandle ?? e.source_handle ?? '')
    const m = /^cond-(\d+)$/.exec(sh)
    if (!m)
      continue
    const list = branchListBySourceId.get(src)
    if (!list)
      continue
    const idx = Number.parseInt(m[1]!, 10)
    if (idx < 0 || idx >= list.length)
      continue
    const bid = list[idx]!.id
    e.sourceHandle = branchSourceHandleId(bid)
    if ('source_handle' in e)
      delete e.source_handle
  }
}

/**
 * Normalize flow_definition from API: set `is_catalog_rule`, migrate conditions → FlowBranch[], remap edges.
 */
export function migrateFlowDefinition(def: Record<string, unknown>): Record<string, unknown> {
  const nodesRaw = def.nodes
  const edgesRaw = def.edges
  const nodes = Array.isArray(nodesRaw) ? [...nodesRaw] : []
  const edges = Array.isArray(edgesRaw)
    ? edgesRaw.map((e) => (isRecord(e) ? { ...e } : e)).filter((e): e is Record<string, unknown> => isRecord(e))
    : []

  const migratedNodes = nodes.map((raw) => {
    if (!isRecord(raw)) return raw
    const out = { ...raw }
    const data = cloneData(out.data)
    const id = String(out.id ?? '')

    if (data.node_type === 'business_rule') {
      if (data.is_catalog_rule === undefined)
        data.is_catalog_rule = inferIsCatalogRule(id, edges)
    }

    out.data = data
    migrateConditionsOnNode(out as Record<string, unknown>)
    return out
  }) as Record<string, unknown>[]

  remapConditionEdges(migratedNodes, edges)

  for (const raw of migratedNodes) {
    if (!isRecord(raw)) continue
    const data = cloneData(raw.data)
    migrateEntryFlags(data as ScriptNodeData)
    raw.data = data
  }

  const schema_version = typeof def.schema_version === 'number' ? def.schema_version : 1

  let result: Record<string, unknown> = {
    ...def,
    schema_version,
    nodes: migratedNodes,
    edges,
  }
  const sv = typeof result.schema_version === 'number' ? result.schema_version : 1
  if (sv < 2)
    result = migrateFlowDefinitionToV2(result)
  return result
}

/** Persist: не пишем устаревшее поле `branches`; Wave 7 — канонический node.data */
export function serializeFlowDefinition(def: Record<string, unknown>): Record<string, unknown> {
  const nodesRaw = def.nodes
  if (!Array.isArray(nodesRaw))
    return { ...def, schema_version: typeof def.schema_version === 'number' ? def.schema_version : 2 }

  const nodes = nodesRaw.map((raw) => {
    if (!isRecord(raw)) return raw
    const out = { ...raw }
    const data = cloneData(out.data)
    const asRec = data as Record<string, unknown>
    if ('branches' in asRec)
      delete asRec.branches
    out.data = sanitizeNodeDataSchemaV2(asRec)
    return out
  })

  return { ...def, schema_version: 2, nodes }
}

export function migrateNodeData(data: ScriptNodeData): ScriptNodeData {
  const d = { ...data }
  if ((d.node_type === 'question' || d.node_type === 'condition') && Array.isArray(d.conditions)) {
    d.conditions = normalizeConditionsToBranches(d.conditions)
  }
  if ('branches' in d)
    delete (d as Record<string, unknown>).branches
  return d
}
