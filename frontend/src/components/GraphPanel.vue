<template>
  <div class="graph-panel">
    <div class="panel-header">
      <span class="panel-title">Graph Relationship Visualization</span>
      <!-- Top Toolbar (Internal Top Right) -->
      <div class="header-tools">
        <button type="button" class="tool-btn" @click="$emit('refresh')" :disabled="loading" title="Refresh Graph" aria-label="Refresh graph">
          <span class="icon-refresh" :class="{ 'spinning': loading }" aria-hidden="true">↻</span>
          <span class="btn-text">Refresh</span>
        </button>
        <button type="button" class="tool-btn" @click="$emit('toggle-maximize')" title="Maximize/Restore" aria-label="Maximize or restore graph panel">
          <span class="icon-maximize" aria-hidden="true">⛶</span>
        </button>
        <input
          v-if="graphData"
          v-model="graphFilterInput"
          type="search"
          class="graph-filter-input"
          placeholder="Filter nodes…"
          aria-label="Filter graph nodes by name or type"
          autocomplete="off"
        />
        <button
          v-if="graphQueryId"
          type="button"
          class="tool-btn"
          title="Read-only Cypher (Kuzu)"
          aria-label="Open Cypher query dialog"
          @click="showQuery = true"
        >
          Query
        </button>
      </div>
    </div>
    
    <div
      v-if="showQuery"
      class="query-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Cypher query"
      tabindex="-1"
      @click.self="showQuery = false"
      @keydown="onQueryKeydown"
    >
      <div class="query-modal">
        <div class="query-modal-head">
          <span>Read-only Cypher</span>
          <button type="button" class="query-close" aria-label="Close" @click="showQuery = false">×</button>
        </div>
        <p class="query-hint"><code>graph_id:</code> {{ graphQueryId }}</p>
        <textarea
          ref="queryTextarea"
          v-model="cypherText"
          class="query-ta"
          rows="6"
          spellcheck="false"
          aria-label="Cypher query"
        />
        <div class="query-actions">
          <button type="button" class="tool-btn primary" :disabled="cypherBusy" @click="runCypher">
            {{ cypherBusy ? 'Running…' : 'Run' }}
          </button>
        </div>
        <pre v-if="cypherError" class="query-err">{{ cypherError }}</pre>
        <pre v-if="cypherOutput" class="query-out">{{ cypherOutput }}</pre>
      </div>
    </div>

    <div class="graph-container" ref="graphContainer">
      <!-- Graph Visualization -->
      <div v-if="graphData" class="graph-view">
        <div v-if="graphTruncationMessage" class="graph-cap-hint" role="status">{{ graphTruncationMessage }}</div>
        <svg ref="graphSvg" class="graph-svg"></svg>
        
        <!-- Building/Simulating Hint -->
        <div v-if="currentPhase === 1 || isSimulating" class="graph-building-hint">
          <div class="memory-icon-wrapper">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="memory-icon">
              <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-4.04z" />
              <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-4.04z" />
            </svg>
          </div>
          {{ isSimulating ? 'GraphRAG long/short-term memory updating in real time' : 'Updating in real time...' }}
        </div>
        
        <!-- Post-simulation Hint -->
        <div v-if="showSimulationFinishedHint" class="graph-building-hint finished-hint">
          <div class="hint-icon-wrapper">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="hint-icon">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="16" x2="12" y2="12"></line>
              <line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
          </div>
          <span class="hint-text">Some content is still being processed. We recommend manually refreshing the graph shortly.</span>
          <button type="button" class="hint-close-btn" @click="dismissFinishedHint" title="Close hint" aria-label="Dismiss simulation finished hint">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        
        <!-- Node/Edge detail panel -->
        <div v-if="selectedItem" class="detail-panel">
          <div class="detail-panel-header">
            <span class="detail-title">{{ selectedItem.type === 'node' ? 'Node Details' : 'Relationship' }}</span>
            <span v-if="selectedItem.type === 'node'" class="detail-type-badge" :style="{ background: selectedItem.color, color: '#fff' }">
              {{ selectedItem.entityType }}
            </span>
            <button
              v-if="selectedItem.type === 'node'"
              type="button"
              class="detail-focus-btn"
              title="Center graph on this node"
              aria-label="Center graph on this node"
              @click="focusSelectedGraphNode"
            >
              Center
            </button>
            <button type="button" class="detail-close" aria-label="Close details" @click="closeDetailPanel">×</button>
          </div>
          
          <!-- Node details -->
          <div v-if="selectedItem.type === 'node'" class="detail-content">
            <div class="detail-row">
              <span class="detail-label">Name:</span>
              <span class="detail-value">{{ selectedItem.data.name }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">UUID:</span>
              <span class="detail-value uuid-text">{{ selectedItem.data.uuid }}</span>
            </div>
            <div class="detail-row" v-if="selectedItem.data.created_at">
              <span class="detail-label">Created:</span>
              <span class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</span>
            </div>
            
            <!-- Properties -->
            <div class="detail-section" v-if="selectedItem.data.attributes && Object.keys(selectedItem.data.attributes).length > 0">
              <div class="section-title">Properties:</div>
              <div class="properties-list">
                <div v-for="(value, key) in selectedItem.data.attributes" :key="key" class="property-item">
                  <span class="property-key">{{ key }}:</span>
                  <span class="property-value">{{ value || 'None' }}</span>
                </div>
              </div>
            </div>
            
            <!-- Summary -->
            <div class="detail-section" v-if="selectedItem.data.summary">
              <div class="section-title">Summary:</div>
              <div class="summary-text">{{ selectedItem.data.summary }}</div>
            </div>
            
            <!-- Labels -->
            <div class="detail-section" v-if="selectedItem.data.labels && selectedItem.data.labels.length > 0">
              <div class="section-title">Labels:</div>
              <div class="labels-list">
                <span v-for="label in selectedItem.data.labels" :key="label" class="label-tag">
                  {{ label }}
                </span>
              </div>
            </div>
          </div>
          
          <!-- Edge details -->
          <div v-else class="detail-content">
            <!-- Self-loop group details -->
            <template v-if="selectedItem.data.isSelfLoopGroup">
              <div class="edge-relation-header self-loop-header">
                {{ selectedItem.data.source_name }} - Self Relations
                <span class="self-loop-count">{{ selectedItem.data.selfLoopCount }} items</span>
              </div>
              
              <div class="self-loop-list">
                <div 
                  v-for="(loop, idx) in selectedItem.data.selfLoopEdges" 
                  :key="loop.uuid || idx" 
                  class="self-loop-item"
                  :class="{ expanded: expandedSelfLoops.has(loop.uuid || idx) }"
                >
                  <div 
                    class="self-loop-item-header"
                    @click="toggleSelfLoop(loop.uuid || idx)"
                  >
                    <span class="self-loop-index">#{{ idx + 1 }}</span>
                    <span class="self-loop-name">{{ loop.name || loop.fact_type || 'RELATED' }}</span>
                    <span class="self-loop-toggle">{{ expandedSelfLoops.has(loop.uuid || idx) ? '−' : '+' }}</span>
                  </div>
                  
                  <div class="self-loop-item-content" v-show="expandedSelfLoops.has(loop.uuid || idx)">
                    <div class="detail-row" v-if="loop.uuid">
                      <span class="detail-label">UUID:</span>
                      <span class="detail-value uuid-text">{{ loop.uuid }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.fact">
                      <span class="detail-label">Fact:</span>
                      <span class="detail-value fact-text">{{ loop.fact }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.fact_type">
                      <span class="detail-label">Type:</span>
                      <span class="detail-value">{{ loop.fact_type }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.created_at">
                      <span class="detail-label">Created:</span>
                      <span class="detail-value">{{ formatDateTime(loop.created_at) }}</span>
                    </div>
                    <div v-if="loop.episodes && loop.episodes.length > 0" class="self-loop-episodes">
                      <span class="detail-label">Episodes:</span>
                      <div class="episodes-list compact">
                        <span v-for="ep in loop.episodes" :key="ep" class="episode-tag small">{{ ep }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            
            <!-- Regular edge details -->
            <template v-else>
              <div class="edge-relation-header">
                {{ selectedItem.data.source_name }} → {{ selectedItem.data.name || 'RELATED_TO' }} → {{ selectedItem.data.target_name }}
              </div>
              
              <div class="detail-row">
                <span class="detail-label">UUID:</span>
                <span class="detail-value uuid-text">{{ selectedItem.data.uuid }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Label:</span>
                <span class="detail-value">{{ selectedItem.data.name || 'RELATED_TO' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Type:</span>
                <span class="detail-value">{{ selectedItem.data.fact_type || 'Unknown' }}</span>
              </div>
              <div class="detail-row" v-if="selectedItem.data.fact">
                <span class="detail-label">Fact:</span>
                <span class="detail-value fact-text">{{ selectedItem.data.fact }}</span>
              </div>
              
              <!-- Episodes -->
              <div class="detail-section" v-if="selectedItem.data.episodes && selectedItem.data.episodes.length > 0">
                <div class="section-title">Episodes:</div>
                <div class="episodes-list">
                  <span v-for="ep in selectedItem.data.episodes" :key="ep" class="episode-tag">
                    {{ ep }}
                  </span>
                </div>
              </div>
              
              <div class="detail-row" v-if="selectedItem.data.created_at">
                <span class="detail-label">Created:</span>
                <span class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</span>
              </div>
              <div class="detail-row" v-if="selectedItem.data.valid_at">
                <span class="detail-label">Valid From:</span>
                <span class="detail-value">{{ formatDateTime(selectedItem.data.valid_at) }}</span>
              </div>
            </template>
          </div>
        </div>
      </div>
      
      <!-- Loading State -->
      <div v-else-if="loading" class="graph-state">
        <div class="loading-spinner"></div>
        <p>Loading graph data...</p>
      </div>

      <!-- Waiting/Empty State -->
      <div v-else class="graph-state">
        <div class="empty-icon">❖</div>
        <p class="empty-text">Waiting for ontology generation...</p>
      </div>
    </div>

    <!-- Bottom legend (Bottom Left) -->
    <div v-if="graphData && entityTypes.length" class="graph-legend">
      <span class="legend-title">Entity Types</span>
      <div class="legend-items">
        <div class="legend-item" v-for="type in entityTypes" :key="type.name">
          <span class="legend-dot" :style="{ background: type.color }"></span>
          <span class="legend-label">{{ type.name }}</span>
        </div>
      </div>
    </div>
    
    <!-- Show edge labels toggle -->
    <div v-if="graphData" class="edge-labels-toggle">
      <label class="toggle-switch">
        <input type="checkbox" v-model="showEdgeLabels" />
        <span class="slider"></span>
      </label>
      <span class="toggle-label">Show Edge Labels</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import * as d3 from 'd3'
import { graphCypherQuery } from '../api/graph'
import { buildGraphLayout, isSubsetSet, setsEqual, edgeKeyForLayout } from '../utils/graphLayout'

const props = defineProps({
  graphData: Object,
  loading: Boolean,
  currentPhase: Number,
  isSimulating: Boolean
})

const emit = defineEmits(['refresh', 'toggle-maximize'])

const graphContainer = ref(null)
const graphSvg = ref(null)
const selectedItem = ref(null)
const showEdgeLabels = ref(true) // show edge labels by default
const expandedSelfLoops = ref(new Set()) // expanded self-loop items
const showSimulationFinishedHint = ref(false) // post-simulation hint
const wasSimulating = ref(false) // track whether was simulating before
const graphTruncationMessage = ref('')
const GRAPH_NODE_CAP = 500

const showQuery = ref(false)
const queryTextarea = ref(null)

const onQueryKeydown = (event) => {
  if (event.key === 'Escape') {
    event.preventDefault()
    showQuery.value = false
  }
}

watch(showQuery, (open) => {
  if (open) {
    nextTick(() => queryTextarea.value?.focus())
  }
})

const cypherText = ref('MATCH (n:Node) RETURN n.id, n.name, n.label LIMIT 25')
const cypherBusy = ref(false)
const cypherError = ref('')
const cypherOutput = ref('')
const graphQueryId = computed(() => props.graphData?.graph_id || null)

const graphFilterInput = ref('')
const graphFilterDebounced = ref('')
let graphFilterDebounceTimer = null

watch(graphFilterInput, () => {
  if (graphFilterDebounceTimer) clearTimeout(graphFilterDebounceTimer)
  graphFilterDebounceTimer = setTimeout(() => {
    graphFilterDebounceTimer = null
    graphFilterDebounced.value = graphFilterInput.value
  }, 175)
})

const edgeKey = edgeKeyForLayout

const nodeMatchesFilter = (d, q) => {
  if (!q) return true
  const name = String(d.name || '').toLowerCase()
  const typ = String(d.type || '').toLowerCase()
  return name.includes(q) || typ.includes(q)
}

const applyGraphNodeFilter = () => {
  if (!graphSvg.value) return
  const q = graphFilterDebounced.value.trim().toLowerCase()
  const svg = d3.select(graphSvg.value)
  svg.selectAll('circle.graph-node').each(function (d) {
    if (!d) return
    const ok = nodeMatchesFilter(d, q)
    d3.select(this).style('opacity', ok ? 1 : 0.12)
  })
  svg.selectAll('text.graph-node-label').each(function (d) {
    if (!d) return
    const ok = nodeMatchesFilter(d, q)
    d3.select(this).style('opacity', ok ? 1 : 0.12)
  })
  const edgeVisible = (d) => {
    if (!q) return true
    const src = typeof d.source === 'object' ? d.source : null
    const tgt = typeof d.target === 'object' ? d.target : null
    if (!src || !tgt) return true
    return nodeMatchesFilter(src, q) && nodeMatchesFilter(tgt, q)
  }
  svg.selectAll('path.graph-link').each(function (d) {
    if (!d) return
    const ok = edgeVisible(d)
    d3.select(this).style('opacity', ok ? 1 : 0.08)
  })
  svg.selectAll('rect.graph-link-label-bg').each(function (d) {
    if (!d) return
    d3.select(this).style('opacity', edgeVisible(d) ? 1 : 0.08)
  })
  svg.selectAll('text.graph-link-label').each(function (d) {
    if (!d) return
    d3.select(this).style('opacity', edgeVisible(d) ? 1 : 0.08)
  })
}

watch(graphFilterDebounced, () => {
  nextTick(() => applyGraphNodeFilter())
})

const runCypher = async () => {
  const q = (cypherText.value || '').trim()
  if (!graphQueryId.value) {
    cypherError.value = 'Load a graph before running a Cypher query.'
    return
  }
  if (!q) {
    cypherError.value = 'Enter a Cypher query to run.'
    return
  }

  cypherBusy.value = true
  cypherError.value = ''
  cypherOutput.value = ''
  try {
    const res = await graphCypherQuery({
      graph_id: graphQueryId.value,
      query: q,
      max_rows: 200
    })
    if (res.success) {
      cypherOutput.value = JSON.stringify(res.data, null, 2)
    } else {
      cypherError.value = res.error || 'Query failed'
    }
  } catch (e) {
    cypherError.value = e.message || String(e)
  } finally {
    cypherBusy.value = false
  }
}

// Dismiss simulation finished hint
const dismissFinishedHint = () => {
  showSimulationFinishedHint.value = false
}

// Watch isSimulating changes, detect simulation end
watch(() => props.isSimulating, (newValue, oldValue) => {
  if (wasSimulating.value && !newValue) {
    // Transitioned from simulating to non-simulating state, show finished hint
    showSimulationFinishedHint.value = true
  }
  wasSimulating.value = newValue
}, { immediate: true })

// Toggle self-loop item expand/collapse state
const toggleSelfLoop = (id) => {
  const newSet = new Set(expandedSelfLoops.value)
  if (newSet.has(id)) {
    newSet.delete(id)
  } else {
    newSet.add(id)
  }
  expandedSelfLoops.value = newSet
}

// Compute entity types for legend
const entityTypes = computed(() => {
  if (!props.graphData?.nodes) return []
  const typeMap = {}
  // Aesthetic color palette
  const colors = ['#FF6B35', '#004E89', '#7B2D8E', '#1A936F', '#C5283D', '#E9724C', '#3498db', '#9b59b6', '#27ae60', '#f39c12']
  
  props.graphData.nodes.forEach(node => {
    const type = node.labels?.find(l => l !== 'Entity') || 'Entity'
    if (!typeMap[type]) {
      typeMap[type] = { name: type, count: 0, color: colors[Object.keys(typeMap).length % colors.length] }
    }
    typeMap[type].count++
  })
  return Object.values(typeMap)
})

// Format time
const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true 
    })
  } catch {
    return dateStr
  }
}

const closeDetailPanel = () => {
  selectedItem.value = null
  expandedSelfLoops.value = new Set() // Reset expand state
}

let currentSimulation = null
let linkLabelsRef = null
let linkLabelBgRef = null
let lastLayoutGraphId = null
let lastNodeIdSet = null
let lastEdgeFpSet = null

const focusSelectedGraphNode = () => {
  if (!selectedItem.value || selectedItem.value.type !== 'node' || !graphSvg.value || !currentSimulation) return
  const uuid = selectedItem.value.data?.uuid
  if (!uuid || !graphContainer.value) return
  const simNode = currentSimulation.nodes().find((n) => n.id === uuid)
  if (simNode == null || simNode.x == null || simNode.y == null) return
  const w = graphContainer.value.clientWidth
  const h = graphContainer.value.clientHeight
  const svg = d3.select(graphSvg.value)
  const z = svg.property('_mfZoom')
  if (!z) return
  const scale = 1.65
  const t = d3.zoomIdentity.translate(w / 2, h / 2).scale(scale).translate(-simNode.x, -simNode.y)
  svg.transition().duration(600).call(z.transform, t)
}

const renderGraph = () => {
  if (!graphSvg.value || !props.graphData) return

  const model = buildGraphLayout(props.graphData, entityTypes.value, GRAPH_NODE_CAP)
  if (!model) {
    graphTruncationMessage.value = ''
    lastLayoutGraphId = null
    lastNodeIdSet = null
    lastEdgeFpSet = null
    return
  }

  graphTruncationMessage.value = model.truncated
    ? `Showing ${GRAPH_NODE_CAP} of ${props.graphData.nodes.length} nodes for performance.`
    : ''

  if (
    lastLayoutGraphId === model.graphId &&
    lastNodeIdSet &&
    lastEdgeFpSet &&
    setsEqual(lastNodeIdSet, model.nodeIdSet) &&
    setsEqual(lastEdgeFpSet, model.edgeFpSet)
  ) {
    return
  }

  const { graphId, nodes, edges, getColor } = model
  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight

  let useIncremental =
    lastLayoutGraphId === graphId &&
    lastNodeIdSet &&
    lastEdgeFpSet &&
    currentSimulation &&
    isSubsetSet(lastNodeIdSet, model.nodeIdSet) &&
    isSubsetSet(lastEdgeFpSet, model.edgeFpSet) &&
    (model.nodeIdSet.size > lastNodeIdSet.size || model.edgeFpSet.size > lastEdgeFpSet.size)

  if (!useIncremental && currentSimulation) {
    currentSimulation.stop()
    currentSimulation = null
  }

  const svg = d3.select(graphSvg.value)
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)

  let rootG = svg.select('g.zoom-root')
  if (rootG.empty()) {
    rootG = svg.append('g').attr('class', 'zoom-root')
    const z = d3.zoom()
      .extent([[0, 0], [width, height]])
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        rootG.attr('transform', event.transform)
      })
    svg.property('_mfZoom', z)
    svg.call(z)
  } else {
    const z = svg.property('_mfZoom')
    if (z) {
      z.extent([[0, 0], [width, height]])
      svg.call(z)
    }
  }

  let g
  if (useIncremental) {
    g = rootG.select('g.chart-layer')
    if (g.empty()) {
      useIncremental = false
    }
  }
  if (!useIncremental) {
    rootG.selectAll('g.chart-layer').remove()
    g = rootG.append('g').attr('class', 'chart-layer')
  }

  if (useIncremental) {
    const pos = new Map(currentSimulation.nodes().map((n) => [n.id, n]))
    nodes.forEach((n) => {
      const p = pos.get(n.id)
      if (p && p.x != null && p.y != null) {
        n.x = p.x
        n.y = p.y
        n.vx = p.vx
        n.vy = p.vy
      } else {
        n.x = width / 2 + (Math.random() - 0.5) * 48
        n.y = height / 2 + (Math.random() - 0.5) * 48
      }
    })
  }

  const linkDistance = (d) => {
    const baseDistance = 150
    const edgeCount = d.pairTotal || 1
    return baseDistance + (edgeCount - 1) * 50
  }

  let simulation
  if (useIncremental) {
    simulation = currentSimulation
    simulation.nodes(nodes)
    simulation.force(
      'link',
      d3.forceLink(edges).id((d) => d.id).distance(linkDistance)
    )
    simulation.force('center', d3.forceCenter(width / 2, height / 2))
    simulation.force('x', d3.forceX(width / 2).strength(0.04))
    simulation.force('y', d3.forceY(height / 2).strength(0.04))
  } else {
    simulation = d3
      .forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id((d) => d.id).distance(linkDistance))
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide(50))
      .force('x', d3.forceX(width / 2).strength(0.04))
      .force('y', d3.forceY(height / 2).strength(0.04))
  }

  currentSimulation = simulation

  let linkGroup
  let nodeGroup
  if (!useIncremental) {
    linkGroup = g.append('g').attr('class', 'links')
    nodeGroup = g.append('g').attr('class', 'nodes')
  } else {
    linkGroup = g.select('g.links')
    nodeGroup = g.select('g.nodes')
  }

  simulation.on('tick', null)

  // Calculate curve path
  const getLinkPath = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y
    
    // Detect self-loop
    if (d.isSelfLoop) {
      // Self-loop: draw an arc from node and back
      const loopRadius = 30
      // Start from right side of node, loop around
      const x1 = sx + 8  // Start offset
      const y1 = sy - 4
      const x2 = sx + 8  // End offset
      const y2 = sy + 4
      // Draw self-loop using arc (sweep-flag=1 clockwise)
      return `M${x1},${y1} A${loopRadius},${loopRadius} 0 1,1 ${x2},${y2}`
    }
    
    if (d.curvature === 0) {
      // Straight line
      return `M${sx},${sy} L${tx},${ty}`
    }
    
    // Calculate curve control point - dynamically adjust based on edge count and distance
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    // Offset perpendicular to link direction, calculated by distance ratio, ensuring visible curves
    // More edges = larger offset ratio
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05 // Base 25%, add 5% per additional edge
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    
    return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`
  }
  
  // Calculate curve midpoint (for label positioning)
  const getLinkMidpoint = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y
    
    // Detect self-loop
    if (d.isSelfLoop) {
      // Self-loop label position: right side of node
      return { x: sx + 70, y: sy }
    }
    
    if (d.curvature === 0) {
      return { x: (sx + tx) / 2, y: (sy + ty) / 2 }
    }
    
    // Quadratic Bezier curve midpoint t=0.5
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    
    // Quadratic Bezier formula B(t) = (1-t)^2*P0 + 2(1-t)t*P1 + t^2*P2, t=0.5
    const midX = 0.25 * sx + 0.5 * cx + 0.25 * tx
    const midY = 0.25 * sy + 0.5 * cy + 0.25 * ty
    
    return { x: midX, y: midY }
  }
  
  const linkPaths = linkGroup
    .selectAll('path.graph-link')
    .data(edges, edgeKey)
    .join((enter) =>
      enter
        .append('path')
        .attr('class', 'graph-link')
        .attr('stroke', '#C0C0C0')
        .attr('stroke-width', 1.5)
        .attr('fill', 'none')
        .style('cursor', 'pointer')
    )
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path.graph-link').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      d3.select(event.target).attr('stroke', '#3498db').attr('stroke-width', 3)

      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })

  const linkLabelBg = linkGroup
    .selectAll('rect.graph-link-label-bg')
    .data(edges, edgeKey)
    .join((enter) =>
      enter
        .append('rect')
        .attr('class', 'graph-link-label-bg')
        .attr('fill', 'rgba(255,255,255,0.95)')
        .attr('rx', 3)
        .attr('ry', 3)
        .style('cursor', 'pointer')
        .style('pointer-events', 'all')
        .style('display', showEdgeLabels.value ? 'block' : 'none')
    )
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path.graph-link').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      linkPaths.filter((l) => l === d).attr('stroke', '#3498db').attr('stroke-width', 3)
      d3.select(event.target).attr('fill', 'rgba(52, 152, 219, 0.1)')

      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })

  const linkLabels = linkGroup
    .selectAll('text.graph-link-label')
    .data(edges, edgeKey)
    .join((enter) =>
      enter
        .append('text')
        .attr('class', 'graph-link-label')
        .text((d) => d.name)
        .attr('font-size', '9px')
        .attr('fill', '#666')
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .style('cursor', 'pointer')
        .style('pointer-events', 'all')
        .style('font-family', 'system-ui, sans-serif')
        .style('display', showEdgeLabels.value ? 'block' : 'none')
    )
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path.graph-link').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      linkPaths.filter((l) => l === d).attr('stroke', '#3498db').attr('stroke-width', 3)
      d3.select(event.target).attr('fill', '#3498db')

      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })
  
  // Save references for external show/hide control
  linkLabelsRef = linkLabels
  linkLabelBgRef = linkLabelBg

  const node = nodeGroup
    .selectAll('circle.graph-node')
    .data(nodes, (d) => d.id)
    .join((enter) =>
      enter
        .append('circle')
        .attr('class', 'graph-node')
        .attr('r', 10)
        .attr('fill', (d) => getColor(d.type))
        .attr('stroke', '#fff')
        .attr('stroke-width', 2.5)
        .style('cursor', 'pointer')
    )
    .call(d3.drag()
      .on('start', (event, d) => {
        // Only record position, don't restart simulation (distinguish click from drag)
        d.fx = d.x
        d.fy = d.y
        d._dragStartX = event.x
        d._dragStartY = event.y
        d._isDragging = false
      })
      .on('drag', (event, d) => {
        // Detect if actual drag has started (moved beyond threshold)
        const dx = event.x - d._dragStartX
        const dy = event.y - d._dragStartY
        const distance = Math.sqrt(dx * dx + dy * dy)
        
        if (!d._isDragging && distance > 3) {
          // First detection of actual drag, restart simulation
          d._isDragging = true
          simulation.alphaTarget(0.3).restart()
        }
        
        if (d._isDragging) {
          d.fx = event.x
          d.fy = event.y
        }
      })
      .on('end', (event, d) => {
        // Only let simulation gradually stop if actual drag occurred
        if (d._isDragging) {
          simulation.alphaTarget(0)
        }
        d.fx = null
        d.fy = null
        d._isDragging = false
      })
    )
    .on('click', (event, d) => {
      event.stopPropagation()
      // Reset all node styles
      node.attr('stroke', '#fff').attr('stroke-width', 2.5)
      linkGroup.selectAll('path.graph-link').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      // Highlight selected node
      d3.select(event.target).attr('stroke', '#E91E63').attr('stroke-width', 4)
      // Highlight edges connected to this node
      linkPaths
        .filter((l) => l.source.id === d.id || l.target.id === d.id)
        .attr('stroke', '#E91E63')
        .attr('stroke-width', 2.5)
      
      selectedItem.value = {
        type: 'node',
        data: d.rawData,
        entityType: d.type,
        color: getColor(d.type)
      }
    })
    .on('mouseenter', (event, d) => {
      if (!selectedItem.value || selectedItem.value.data?.uuid !== d.rawData.uuid) {
        d3.select(event.target).attr('stroke', '#333').attr('stroke-width', 3)
      }
    })
    .on('mouseleave', (event, d) => {
      if (!selectedItem.value || selectedItem.value.data?.uuid !== d.rawData.uuid) {
        d3.select(event.target).attr('stroke', '#fff').attr('stroke-width', 2.5)
      }
    })

  const nodeLabels = nodeGroup
    .selectAll('text.graph-node-label')
    .data(nodes, (d) => d.id)
    .join((enter) =>
      enter
        .append('text')
        .attr('class', 'graph-node-label')
        .text((d) => (d.name.length > 8 ? d.name.substring(0, 8) + '…' : d.name))
        .attr('font-size', '11px')
        .attr('fill', '#333')
        .attr('font-weight', '500')
        .attr('dx', 14)
        .attr('dy', 4)
        .style('pointer-events', 'none')
        .style('font-family', 'system-ui, sans-serif')
    )

  simulation.on('tick', () => {
    // Update curve paths
    linkPaths.attr('d', (d) => getLinkPath(d))
    
    // Update edge label positions (no rotation, horizontal display is clearer)
    linkLabels.each(function(d) {
      const mid = getLinkMidpoint(d)
      d3.select(this)
        .attr('x', mid.x)
        .attr('y', mid.y)
        .attr('transform', '') // Remove rotation, keep horizontal
    })
    
    // Update edge label backgrounds
    linkLabelBg.each(function(d, i) {
      const mid = getLinkMidpoint(d)
      const textEl = linkLabels.nodes()[i]
      const bbox = textEl.getBBox()
      d3.select(this)
        .attr('x', mid.x - bbox.width / 2 - 4)
        .attr('y', mid.y - bbox.height / 2 - 2)
        .attr('width', bbox.width + 8)
        .attr('height', bbox.height + 4)
        .attr('transform', '') // Remove rotation
    })

    node
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)

    nodeLabels
      .attr('x', d => d.x)
      .attr('y', d => d.y)
  })
  
  // Click on blank area to close detail panel
  svg.on('click', () => {
    selectedItem.value = null
    node.attr('stroke', '#fff').attr('stroke-width', 2.5)
    linkGroup.selectAll('path.graph-link').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
    linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
    linkLabels.attr('fill', '#666')
  })

  if (useIncremental) {
    simulation.alpha(0.45).restart()
  }

  lastLayoutGraphId = graphId
  lastNodeIdSet = model.nodeIdSet
  lastEdgeFpSet = model.edgeFpSet

  applyGraphNodeFilter()
}

watch(() => props.graphData, () => {
  nextTick(renderGraph)
}, { deep: true })

// Watch edge label show/hide toggle
watch(showEdgeLabels, (newVal) => {
  if (linkLabelsRef) {
    linkLabelsRef.style('display', newVal ? 'block' : 'none')
  }
  if (linkLabelBgRef) {
    linkLabelBgRef.style('display', newVal ? 'block' : 'none')
  }
})

let resizeDebounceTimer = null
let resizeObserver = null

const scheduleResize = () => {
  if (resizeDebounceTimer) clearTimeout(resizeDebounceTimer)
  resizeDebounceTimer = setTimeout(() => {
    resizeDebounceTimer = null
    nextTick(renderGraph)
  }, 175)
}

const handleResize = () => {
  scheduleResize()
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  if (typeof ResizeObserver !== 'undefined' && graphContainer.value) {
    resizeObserver = new ResizeObserver(() => scheduleResize())
    resizeObserver.observe(graphContainer.value)
  }
})

onUnmounted(() => {
  if (graphFilterDebounceTimer) clearTimeout(graphFilterDebounceTimer)
  graphFilterDebounceTimer = null
  if (resizeDebounceTimer) clearTimeout(resizeDebounceTimer)
  resizeObserver?.disconnect()
  resizeObserver = null
  window.removeEventListener('resize', handleResize)
  if (currentSimulation) {
    currentSimulation.stop()
  }
})
</script>

<style scoped>
.graph-cap-hint {
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 5;
  padding: 6px 12px;
  background: rgba(0, 0, 0, 0.78);
  color: #fff;
  font-size: 11px;
  max-width: 90%;
  text-align: center;
  pointer-events: none;
}

.graph-panel {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #FAFAFA;
  background-image: radial-gradient(#D0D0D0 1.5px, transparent 1.5px);
  background-size: 24px 24px;
  overflow: hidden;
}

.panel-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 16px 20px;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(to bottom, rgba(255,255,255,0.95), rgba(255,255,255,0));
  pointer-events: none;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  pointer-events: auto;
}

.header-tools {
  pointer-events: auto;
  display: flex;
  gap: 10px;
  align-items: center;
}

.graph-filter-input {
  width: 9rem;
  max-width: 28vw;
  height: 32px;
  padding: 0 0.5rem;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-size: 0.8125rem;
  color: #333;
  background: #fff;
}

.graph-filter-input::placeholder {
  color: #999;
}

.tool-btn {
  height: 32px;
  padding: 0 12px;
  border: 1px solid #E0E0E0;
  background: #FFF;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  color: #666;
  transition: all 0.2s;
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  font-size: 13px;
}

.tool-btn:hover {
  background: #F5F5F5;
  color: #000;
  border-color: #CCC;
}

.tool-btn .btn-text {
  font-size: 12px;
}

.icon-refresh.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.graph-container {
  width: 100%;
  height: 100%;
}

.graph-view, .graph-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.graph-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #999;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.2;
}

/* Entity Types Legend - Bottom Left */
.graph-legend {
  position: absolute;
  bottom: 24px;
  left: 24px;
  background: rgba(255,255,255,0.95);
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid #EAEAEA;
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  z-index: 10;
}

.legend-title {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #E91E63;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  max-width: 320px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #555;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-label {
  white-space: nowrap;
}

/* Edge Labels Toggle - Top Right */
.edge-labels-toggle {
  position: absolute;
  top: 60px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: #FFF;
  padding: 8px 14px;
  border-radius: 20px;
  border: 1px solid #E0E0E0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  z-index: 10;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #E0E0E0;
  border-radius: 22px;
  transition: 0.3s;
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  border-radius: 50%;
  transition: 0.3s;
}

input:checked + .slider {
  background-color: #7B2D8E;
}

input:checked + .slider:before {
  transform: translateX(18px);
}

.toggle-label {
  font-size: 12px;
  color: #666;
}

/* Detail Panel - Right Side */
.detail-panel {
  position: absolute;
  top: 60px;
  right: 20px;
  width: 320px;
  max-height: calc(100% - 100px);
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.1);
  overflow: hidden;
  font-family: 'Noto Sans SC', system-ui, sans-serif;
  font-size: 13px;
  z-index: 20;
  display: flex;
  flex-direction: column;
}

.detail-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: #FAFAFA;
  border-bottom: 1px solid #EEE;
  flex-shrink: 0;
}

.detail-title {
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.detail-type-badge {
  padding: 0.25rem 0.625rem;
  border-radius: 0.75rem;
  font-size: 0.6875rem;
  font-weight: 500;
  margin-left: auto;
  margin-right: 0.5rem;
}

.detail-focus-btn {
  margin-right: 0.5rem;
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: #1565c0;
  background: #e3f2fd;
  border: 1px solid #90caf9;
  border-radius: 0.375rem;
  cursor: pointer;
}

.detail-focus-btn:hover {
  background: #bbdefb;
}

.detail-close {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #999;
  line-height: 1;
  padding: 0;
  transition: color 0.2s;
}

.detail-close:hover {
  color: #333;
}

.detail-content {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.detail-row {
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.detail-label {
  color: #888;
  font-size: 12px;
  font-weight: 500;
  min-width: 80px;
}

.detail-value {
  color: #333;
  flex: 1;
  word-break: break-word;
}

.detail-value.uuid-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #666;
}

.detail-value.fact-text {
  line-height: 1.5;
  color: #444;
}

.detail-section {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #F0F0F0;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  margin-bottom: 10px;
}

.properties-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.property-item {
  display: flex;
  gap: 8px;
}

.property-key {
  color: #888;
  font-weight: 500;
  min-width: 90px;
}

.property-value {
  color: #333;
  flex: 1;
}

.summary-text {
  line-height: 1.6;
  color: #444;
  font-size: 12px;
}

.labels-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.label-tag {
  display: inline-block;
  padding: 4px 12px;
  background: #F5F5F5;
  border: 1px solid #E0E0E0;
  border-radius: 16px;
  font-size: 11px;
  color: #555;
}

.episodes-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.episode-tag {
  display: inline-block;
  padding: 6px 10px;
  background: #F8F8F8;
  border: 1px solid #E8E8E8;
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #666;
  word-break: break-all;
}

/* Edge relation header */
.edge-relation-header {
  background: #F8F8F8;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  line-height: 1.5;
  word-break: break-word;
}

/* Building hint */
.graph-building-hint {
  position: absolute;
  bottom: 160px; /* Moved up from 80px */
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(8px);
  color: #fff;
  padding: 10px 20px;
  border-radius: 30px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-weight: 500;
  letter-spacing: 0.5px;
  z-index: 100;
}

.memory-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  animation: breathe 2s ease-in-out infinite;
}

.memory-icon {
  width: 18px;
  height: 18px;
  color: #4CAF50;
}

@keyframes breathe {
  0%, 100% { opacity: 0.7; transform: scale(1); filter: drop-shadow(0 0 2px rgba(76, 175, 80, 0.3)); }
  50% { opacity: 1; transform: scale(1.15); filter: drop-shadow(0 0 8px rgba(76, 175, 80, 0.6)); }
}

/* Post-simulation finished hint styles */
.graph-building-hint.finished-hint {
  background: rgba(0, 0, 0, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.finished-hint .hint-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
}

.finished-hint .hint-icon {
  width: 18px;
  height: 18px;
  color: #FFF;
}

.finished-hint .hint-text {
  flex: 1;
  white-space: nowrap;
}

.hint-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: rgba(255, 255, 255, 0.2);
  border: none;
  border-radius: 50%;
  cursor: pointer;
  color: #FFF;
  transition: all 0.2s;
  margin-left: 8px;
  flex-shrink: 0;
}

.hint-close-btn:hover {
  background: rgba(255, 255, 255, 0.35);
  transform: scale(1.1);
}

/* Loading spinner */
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #E0E0E0;
  border-top-color: #7B2D8E;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

/* Self-loop styles */
.self-loop-header {
  display: flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(135deg, #E8F5E9 0%, #F1F8E9 100%);
  border: 1px solid #C8E6C9;
}

.self-loop-count {
  margin-left: auto;
  font-size: 11px;
  color: #666;
  background: rgba(255,255,255,0.8);
  padding: 2px 8px;
  border-radius: 10px;
}

.self-loop-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.self-loop-item {
  background: #FAFAFA;
  border: 1px solid #EAEAEA;
  border-radius: 8px;
}

.self-loop-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #F5F5F5;
  cursor: pointer;
  transition: background 0.2s;
}

.self-loop-item-header:hover {
  background: #EEEEEE;
}

.self-loop-item.expanded .self-loop-item-header {
  background: #E8E8E8;
}

.self-loop-index {
  font-size: 10px;
  font-weight: 600;
  color: #888;
  background: #E0E0E0;
  padding: 2px 6px;
  border-radius: 4px;
}

.self-loop-name {
  font-size: 12px;
  font-weight: 500;
  color: #333;
  flex: 1;
}

.self-loop-toggle {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #888;
  background: #E0E0E0;
  border-radius: 4px;
  transition: all 0.2s;
}

.self-loop-item.expanded .self-loop-toggle {
  background: #D0D0D0;
  color: #666;
}

.self-loop-item-content {
  padding: 12px;
  border-top: 1px solid #EAEAEA;
}

.self-loop-item-content .detail-row {
  margin-bottom: 8px;
}

.self-loop-item-content .detail-label {
  font-size: 11px;
  min-width: 60px;
}

.self-loop-item-content .detail-value {
  font-size: 12px;
}

.self-loop-episodes {
  margin-top: 8px;
}

.episodes-list.compact {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 4px;
}

.episode-tag.small {
  padding: 3px 6px;
  font-size: 9px;
}

.query-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 2000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 2rem 1rem;
  overflow: auto;
}

.query-modal {
  background: #fff;
  border-radius: 10px;
  max-width: 640px;
  width: 100%;
  padding: 1rem 1.1rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}

.query-modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 700;
  margin-bottom: 0.35rem;
}

.query-close {
  border: none;
  background: transparent;
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  color: #666;
}

.query-hint {
  font-size: 0.75rem;
  color: #666;
  margin: 0 0 0.5rem;
}

.query-ta {
  width: 100%;
  box-sizing: border-box;
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 0.5rem;
}

.query-actions {
  margin-top: 0.5rem;
}

.tool-btn.primary {
  background: #004e89;
  color: #fff;
}

.query-err {
  margin-top: 0.5rem;
  color: #a40000;
  font-size: 0.8rem;
  white-space: pre-wrap;
}

.query-out {
  margin-top: 0.5rem;
  background: #f7f7f7;
  border-radius: 6px;
  padding: 0.5rem;
  font-size: 0.72rem;
  max-height: 240px;
  overflow: auto;
}
</style>
