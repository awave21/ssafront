import { describe, expect, it } from 'vitest'
import { migrateFlowDefinition, serializeFlowDefinition } from '~/utils/scriptFlowNodeRole'

describe('migrateFlowDefinition / serializeFlowDefinition', () => {
  it('migrates string conditions to FlowBranch ids and remaps cond-* edges', () => {
    const base = {
      nodes: [
        {
          id: 'c1',
          type: 'expert',
          position: { x: 0, y: 0 },
          data: {
            node_type: 'condition',
            conditions: ['да', 'нет'],
          },
        },
        { id: 't1', type: 'expert', position: { x: 100, y: 0 }, data: { node_type: 'expertise', title: 'T' } },
      ],
      edges: [
        { id: 'e1', source: 'c1', target: 't1', sourceHandle: 'cond-0' },
        { id: 'e2', source: 'c1', target: 't1', sourceHandle: 'cond-1' },
      ],
    }
    const migrated = migrateFlowDefinition(base)
    const node = (migrated.nodes as { id: string; data: { conditions?: { id: string; label: string }[] } }[]).find(
      x => x.id === 'c1',
    )
    expect(node?.data.conditions?.length).toBe(2)
    expect(node?.data.conditions?.every(c => typeof c.id === 'string' && c.id.length > 0)).toBe(true)
    expect(node?.data.conditions?.map(c => c.label)).toEqual(['да', 'нет'])

    const edges = migrated.edges as { sourceHandle?: string }[]
    const id0 = node!.data.conditions![0]!.id
    const id1 = node!.data.conditions![1]!.id
    expect(edges.find(e => e.sourceHandle?.includes(id0))).toBeTruthy()
    expect(edges.some(e => e.sourceHandle === `branch:${id0}`)).toBe(true)
    expect(edges.some(e => e.sourceHandle === `branch:${id1}`)).toBe(true)

    const serialized = serializeFlowDefinition(migrated)
    const raw = (serialized.nodes as { data: Record<string, unknown> }[])[0]!.data
    expect(raw.branches).toBeUndefined()
  })

  it('infers is_catalog_rule for isolated business_rule', () => {
    const def = {
      nodes: [
        {
          id: 'br1',
          type: 'business_rule',
          position: { x: 0, y: 0 },
          data: { node_type: 'business_rule', title: 'R' },
        },
      ],
      edges: [],
    }
    const migrated = migrateFlowDefinition(def)
    const n = (migrated.nodes as { data: { is_catalog_rule?: boolean } }[])[0]
    expect(n.data.is_catalog_rule).toBe(true)
  })

  it('sets is_catalog_rule false when business_rule has dialogue edge', () => {
    const def = {
      nodes: [
        {
          id: 'br1',
          type: 'business_rule',
          position: { x: 0, y: 0 },
          data: { node_type: 'business_rule' },
        },
        {
          id: 't1',
          type: 'expertise',
          position: { x: 100, y: 0 },
          data: { node_type: 'expertise' },
        },
      ],
      edges: [{ id: 'e1', source: 'br1', target: 't1' }],
    }
    const migrated = migrateFlowDefinition(def)
    const br = (migrated.nodes as { id: string; data: { is_catalog_rule?: boolean } }[]).find(
      x => x.id === 'br1',
    )
    expect(br?.data.is_catalog_rule).toBe(false)
  })
})
