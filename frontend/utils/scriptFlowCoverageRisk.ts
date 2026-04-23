import type { ScriptFlowCoverageResult } from '~/types/scriptFlow'

export type CoverageRiskLevel = 'ok' | 'warn' | 'critical'

export type CoverageRiskSummary = {
  level: CoverageRiskLevel
  criticalCount: number
  warningCount: number
}

/** Агрегирует проваленные проверки по severity (critical блокирует публикацию на фронте). */
export function summarizeCoverageRisk(cov: ScriptFlowCoverageResult): CoverageRiskSummary {
  const failed = cov.checks.filter((c) => !c.passed)
  const criticalCount = failed.filter((c) => c.severity === 'critical').length
  const warningCount = failed.filter((c) => c.severity === 'warning').length
  let level: CoverageRiskLevel
  if (criticalCount > 0) level = 'critical'
  else if (warningCount > 0) level = 'warn'
  else level = 'ok'
  return { level, criticalCount, warningCount }
}

export function coverageRiskBadgeLabel(s: CoverageRiskSummary): string {
  if (s.level === 'ok') return 'Риск: низкий'
  if (s.level === 'warn')
    return s.warningCount === 1 ? 'Есть предупреждение' : `Предупреждений: ${s.warningCount}`
  return s.criticalCount === 1 ? 'Критическая проблема' : `Критично: ${s.criticalCount}`
}
