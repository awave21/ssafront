import { describe, expect, it } from 'vitest'
import { coverageRiskBadgeLabel, summarizeCoverageRisk } from '~/utils/scriptFlowCoverageRisk'
import type { ScriptFlowCoverageResult } from '~/types/scriptFlow'

describe('summarizeCoverageRisk', () => {
  it('returns ok when all checks pass', () => {
    const cov: ScriptFlowCoverageResult = {
      flow_id: 'x',
      score: 100,
      checks: [
        { key: 'a', label: 'L', passed: true, severity: 'warning', details: null },
      ],
      stats: {
        total_nodes: 1,
        searchable_nodes: 1,
        searchable_with_good_question: 0,
        condition_nodes: 0,
        condition_branches: 0,
      },
    }
    expect(summarizeCoverageRisk(cov)).toEqual({
      level: 'ok',
      criticalCount: 0,
      warningCount: 0,
    })
  })

  it('counts critical vs warning failures', () => {
    const cov: ScriptFlowCoverageResult = {
      flow_id: 'x',
      score: 50,
      checks: [
        { key: 'c', label: 'C', passed: false, severity: 'critical', details: null },
        { key: 'w', label: 'W', passed: false, severity: 'warning', details: null },
      ],
      stats: {
        total_nodes: 1,
        searchable_nodes: 0,
        searchable_with_good_question: 0,
        condition_nodes: 0,
        condition_branches: 0,
      },
    }
    expect(summarizeCoverageRisk(cov).level).toBe('critical')
    expect(summarizeCoverageRisk(cov).criticalCount).toBe(1)
    expect(summarizeCoverageRisk(cov).warningCount).toBe(1)
  })
})

describe('coverageRiskBadgeLabel', () => {
  it('labels ok state', () => {
    expect(
      coverageRiskBadgeLabel({ level: 'ok', criticalCount: 0, warningCount: 0 }),
    ).toBe('Риск: низкий')
  })
})
