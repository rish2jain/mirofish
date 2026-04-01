import { describe, expect, it } from 'vitest'
import { buildGraphLayout, edgeKeyForLayout, isSubsetSet, setsEqual } from './graphLayout.js'

describe('graphLayout', () => {
  it('isSubsetSet and setsEqual', () => {
    expect(isSubsetSet(new Set(['a']), new Set(['a', 'b']))).toBe(true)
    expect(isSubsetSet(new Set(['c']), new Set(['a', 'b']))).toBe(false)
    expect(setsEqual(new Set([1, 2]), new Set([2, 1]))).toBe(true)
    expect(setsEqual(new Set([1]), new Set([1, 2]))).toBe(false)
    expect(setsEqual(null, new Set())).toBe(false)
  })

  it('buildGraphLayout returns node and edge sets', () => {
    const entityTypes = [{ name: 'Person', color: '#f00' }]
    const layout = buildGraphLayout(
      {
        graph_id: 'gid',
        nodes: [
          { uuid: 'n1', name: 'A', labels: ['Entity', 'Person'] },
          { uuid: 'n2', name: 'B', labels: ['Entity'] },
        ],
        edges: [
          {
            uuid: 'e1',
            source_node_uuid: 'n1',
            target_node_uuid: 'n2',
            fact_type: 'KNOWS',
            name: 'KNOWS',
          },
        ],
      },
      entityTypes,
      500,
    )
    expect(layout).not.toBeNull()
    expect(layout.graphId).toBe('gid')
    expect(layout.nodeIdSet.has('n1')).toBe(true)
    expect(layout.edgeFpSet.size).toBeGreaterThan(0)
    expect(layout.getColor('Person')).toBe('#f00')
  })

  it('edgeKeyForLayout', () => {
    expect(edgeKeyForLayout({ source: { id: 'a' }, target: { id: 'b' }, pairIndex: 0, isSelfLoop: false })).toBe(
      'e:a|b|0',
    )
    expect(edgeKeyForLayout({ source: 'x', target: 'x', isSelfLoop: true })).toBe('sl:x')
  })
})
