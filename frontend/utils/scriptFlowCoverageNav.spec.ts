import { describe, expect, it } from 'vitest'
import { coverageCheckNodeId, flowDefinitionNodeTitle } from './scriptFlowCoverageNav'
import type { ScriptFlowCoverageCheck } from '~/types/scriptFlow'

describe('coverageCheckNodeId', () => {
  it('uses details when set', () => {
    const c: ScriptFlowCoverageCheck = {
      key: 'x',
      label: 'L',
      passed: false,
      severity: 'warning',
      details: ' node-1 ',
    }
    expect(coverageCheckNodeId(c)).toBe('node-1')
  })

  it('falls back to key suffix', () => {
    const c: ScriptFlowCoverageCheck = {
      key: 'no_kg_links:abc123',
      label: 'L',
      passed: false,
      severity: 'warning',
      details: null,
    }
    expect(coverageCheckNodeId(c)).toBe('abc123')
  })

  it('returns null for empty_flow style keys', () => {
    const c: ScriptFlowCoverageCheck = {
      key: 'empty_flow',
      label: 'Пусто',
      passed: false,
      severity: 'critical',
      details: null,
    }
    expect(coverageCheckNodeId(c)).toBe(null)
  })
})

describe('flowDefinitionNodeTitle', () => {
  it('reads title from node data', () => {
    const def = {
      nodes: [{ id: 'n1', data: { title: 'Hello' } }],
    }
    expect(flowDefinitionNodeTitle(def, 'n1')).toBe('Hello')
  })
})
