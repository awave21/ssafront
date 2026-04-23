import { type Ref, ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import type { ScriptFlow, ScriptFlowCoverageResult } from '~/types/scriptFlow'

/**
 * Дебаунс-обновление coverage для подсветки узлов на канвасе (волна 2.10).
 */
export const useScriptFlowCoverageInline = (
  flowId: () => string,
  flow: Ref<ScriptFlow | null>,
  getFlowCoverage: (id: string) => Promise<ScriptFlowCoverageResult>,
) => {
  const coverageInline = ref<ScriptFlowCoverageResult | null>(null)

  const refreshCoverageInline = useDebounceFn(async () => {
    if (!flow.value) return
    try {
      coverageInline.value = await getFlowCoverage(flowId())
    }
    catch {
      coverageInline.value = null
    }
  }, 900)

  watch(
    () => flow.value?.flow_definition,
    () => void refreshCoverageInline(),
    { deep: true },
  )

  return { coverageInline, refreshCoverageInline }
}
