import type { ScriptFlowCoverageCheck } from '~/types/scriptFlow'

/**
 * Из ответа GET …/coverage: для проверок по конкретному узлу бэкенд кладёт id в `details`
 * и дублирует суффикс в `key` (например `no_examples:<id>`).
 * Глобальные проверки (`empty_flow`) идут без привязки к узлу.
 */
export function coverageCheckNodeId(check: ScriptFlowCoverageCheck): string | null {
  const raw = check.details
  if (typeof raw === 'string') {
    const t = raw.trim()
    if (t) return t
  }
  const key = check.key || ''
  const colon = key.lastIndexOf(':')
  if (colon !== -1) {
    const tail = key.slice(colon + 1).trim()
    if (tail && tail !== 'empty_flow') return tail
  }
  return null
}

export function flowDefinitionNodeTitle(
  flowDefinition: Record<string, unknown> | null | undefined,
  nodeId: string,
): string | null {
  const nodes = flowDefinition?.nodes
  if (!Array.isArray(nodes)) return null
  for (const n of nodes) {
    if (typeof n !== 'object' || n === null) continue
    const o = n as Record<string, unknown>
    if (String(o.id ?? '') !== nodeId) continue
    const data = o.data as Record<string, unknown> | undefined
    const title = data && typeof data.title === 'string' ? data.title.trim() : ''
    return title || nodeId
  }
  return null
}
