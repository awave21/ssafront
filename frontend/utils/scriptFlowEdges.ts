import type { ScriptNodeData } from '~/types/scriptFlow'
import { isStandaloneCatalogRule } from '~/utils/scriptFlowNodeRole'

/** Запретить новое ребро диалога, если любой конец — изолированное бизнес-правило каталога. */
export function connectionViolatesCatalogPolicy(
  sourceNode: { data?: ScriptNodeData } | undefined,
  targetNode: { data?: ScriptNodeData } | undefined,
): boolean {
  const sd = sourceNode?.data as ScriptNodeData | undefined
  const td = targetNode?.data as ScriptNodeData | undefined
  if (!sd || !td) return false
  return isStandaloneCatalogRule(sd) || isStandaloneCatalogRule(td)
}
