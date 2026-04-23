import { describe, expect, it } from 'vitest'
import type { ScriptNodeData } from '~/types/scriptFlow'
import { connectionViolatesCatalogPolicy } from '~/utils/scriptFlowEdges'

describe('connectionViolatesCatalogPolicy', () => {
  const tactic = (): { data?: ScriptNodeData } => ({
    data: { node_type: 'expertise', title: 't' },
  })

  const catalogIso = (): { data?: ScriptNodeData } => ({
    data: {
      node_type: 'business_rule',
      is_catalog_rule: true,
      entity_id: 'e1',
    },
  })

  const catalogInFlow = (): { data?: ScriptNodeData } => ({
    data: {
      node_type: 'business_rule',
      is_catalog_rule: false,
      entity_id: 'e2',
    },
  })

  it('returns false for normal dialogue nodes', () => {
    expect(connectionViolatesCatalogPolicy(tactic(), tactic())).toBe(false)
  })

  it('blocks connection when source is isolated catalog rule', () => {
    expect(connectionViolatesCatalogPolicy(catalogIso(), tactic())).toBe(true)
  })

  it('blocks connection when target is isolated catalog rule', () => {
    expect(connectionViolatesCatalogPolicy(tactic(), catalogIso())).toBe(true)
  })

  it('allows catalog rule participating in dialogue flow', () => {
    expect(connectionViolatesCatalogPolicy(catalogInFlow(), tactic())).toBe(false)
    expect(connectionViolatesCatalogPolicy(tactic(), catalogInFlow())).toBe(false)
  })
})
