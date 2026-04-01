/**
 * Build D3 force-graph model from MiroFish graph API payload (nodes/edges).
 * Used by GraphPanel for full and incremental redraws.
 *
 * @param {object} graphData
 * @param {Array<{ name: string, color: string }>} entityTypes
 * @param {number} nodeCap
 * @returns {null | {
 *   graphId: string,
 *   nodes: object[],
 *   edges: object[],
 *   nodeMap: Record<string, object>,
 *   getColor: (type: string) => string,
 *   nodeIdSet: Set<string>,
 *   edgeFpSet: Set<string>,
 *   truncated: boolean
 * }}
 */
export function buildGraphLayout(graphData, entityTypes, nodeCap) {
  if (!graphData) return null

  let nodesData = graphData.nodes || []
  const edgesData = graphData.edges || []
  const graphId = graphData.graph_id || ''

  if (nodesData.length === 0) return null

  let truncated = false
  if (nodesData.length > nodeCap) {
    truncated = true
    nodesData = nodesData.slice(0, nodeCap)
  }

  const colorMap = {}
  entityTypes.forEach((t) => {
    colorMap[t.name] = t.color
  })
  const getColor = (type) => colorMap[type] || '#999'

  const nodeMap = {}
  nodesData.forEach((n) => {
    nodeMap[n.uuid] = n
  })

  const nodes = nodesData.map((n) => ({
    id: n.uuid,
    name: n.name || 'Unnamed',
    type: n.labels?.find((l) => l !== 'Entity') || 'Entity',
    rawData: n
  }))

  const nodeIdSet = new Set(nodes.map((n) => n.id))

  const edgePairCount = {}
  const selfLoopEdges = {}
  const tempEdges = edgesData.filter(
    (e) => nodeIdSet.has(e.source_node_uuid) && nodeIdSet.has(e.target_node_uuid)
  )

  const edgeFpSet = new Set()
  tempEdges.forEach((e) => {
    const fp = `${e.source_node_uuid}|${e.target_node_uuid}|${e.uuid || ''}`
    edgeFpSet.add(fp)
  })

  tempEdges.forEach((e) => {
    if (e.source_node_uuid === e.target_node_uuid) {
      if (!selfLoopEdges[e.source_node_uuid]) {
        selfLoopEdges[e.source_node_uuid] = []
      }
      selfLoopEdges[e.source_node_uuid].push({
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      })
    } else {
      const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
      edgePairCount[pairKey] = (edgePairCount[pairKey] || 0) + 1
    }
  })

  const edgePairIndex = {}
  const processedSelfLoopNodes = new Set()
  const edges = []

  tempEdges.forEach((e) => {
    const isSelfLoop = e.source_node_uuid === e.target_node_uuid

    if (isSelfLoop) {
      if (processedSelfLoopNodes.has(e.source_node_uuid)) {
        return
      }
      processedSelfLoopNodes.add(e.source_node_uuid)

      const allSelfLoops = selfLoopEdges[e.source_node_uuid]
      const nodeName = nodeMap[e.source_node_uuid]?.name || 'Unknown'

      edges.push({
        source: e.source_node_uuid,
        target: e.target_node_uuid,
        type: 'SELF_LOOP',
        name: `Self Relations (${allSelfLoops.length})`,
        curvature: 0,
        isSelfLoop: true,
        rawData: {
          isSelfLoopGroup: true,
          source_name: nodeName,
          target_name: nodeName,
          selfLoopCount: allSelfLoops.length,
          selfLoopEdges: allSelfLoops
        }
      })
      return
    }

    const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
    const totalCount = edgePairCount[pairKey]
    const currentIndex = edgePairIndex[pairKey] || 0
    edgePairIndex[pairKey] = currentIndex + 1

    const isReversed = e.source_node_uuid > e.target_node_uuid

    let curvature = 0
    if (totalCount > 1) {
      const curvatureRange = Math.min(1.2, 0.6 + totalCount * 0.15)
      curvature = ((currentIndex / (totalCount - 1)) - 0.5) * curvatureRange * 2
      if (isReversed) {
        curvature = -curvature
      }
    }

    edges.push({
      source: e.source_node_uuid,
      target: e.target_node_uuid,
      type: e.fact_type || e.name || 'RELATED',
      name: e.name || e.fact_type || 'RELATED',
      curvature,
      isSelfLoop: false,
      pairIndex: currentIndex,
      pairTotal: totalCount,
      rawData: {
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      }
    })
  })

  return {
    graphId,
    nodes,
    edges,
    nodeMap,
    getColor,
    nodeIdSet,
    edgeFpSet,
    truncated
  }
}

/**
 * @param {Set<string>} a
 * @param {Set<string>} b
 */
export function isSubsetSet(a, b) {
  for (const x of a) {
    if (!b.has(x)) return false
  }
  return true
}

/**
 * Compare two Set objects for equality (same size and every element of `a` is in `b`).
 *
 * @param {Set} a
 * @param {Set} b
 * @returns {boolean}
 */
export function setsEqual(a, b) {
  if (!a || !b || a.size !== b.size) return false
  return isSubsetSet(a, b)
}

/**
 * Produce a stable string key for D3 force-link data joins (e.g. `.key(edgeKeyForLayout)`).
 *
 * @param {Object} d Link datum: `source` / `target` may be node ids or objects with `.id`;
 *   `isSelfLoop` selects the self-loop branch; otherwise `pairIndex` disambiguates parallel edges.
 * @returns {string}
 */
export function edgeKeyForLayout(d) {
  const sid = typeof d.source === 'object' ? d.source.id : d.source
  const tid = typeof d.target === 'object' ? d.target.id : d.target
  if (d.isSelfLoop) return `sl:${sid}`
  return `e:${sid}|${tid}|${d.pairIndex ?? 0}`
}
