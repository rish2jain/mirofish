import service, { requestWithRetry } from './index'

/**
 * Generate ontology (upload documents and simulation requirement)
 * @param {Object} data - Contains files, simulation_requirement, project_name, etc.
 * @returns {Promise}
 */
export function generateOntology(formData) {
  return requestWithRetry(() =>
    service({
      url: '/api/graph/ontology/generate',
      method: 'post',
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  )
}

/**
 * Build graph
 * @param {Object} data - Contains project_id, graph_name, etc.
 * @returns {Promise}
 */
export function buildGraph(data) {
  return requestWithRetry(() =>
    service({
      url: '/api/graph/build',
      method: 'post',
      data
    })
  )
}

/**
 * Query graph build / task status (REST).
 * For live updates without polling, the UI may use EventSource on
 * `GET /api/graph/task/${taskId}/sse` (same JSON shape as this response).
 *
 * @param {string} taskId - Task ID
 * @returns {Promise<{ success: boolean, data?: object, error?: string }>}
 */
export function getTaskStatus(taskId) {
  return service({
    url: `/api/graph/task/${taskId}`,
    method: 'get'
  })
}

/**
 * Get graph data
 * @param {String} graphId - Graph ID
 * @returns {Promise}
 */
export function getGraphData(graphId) {
  return service({
    url: `/api/graph/data/${graphId}`,
    method: 'get'
  })
}

/**
 * Get project information
 * @param {String} projectId - Project ID
 * @returns {Promise}
 */
export function getProject(projectId) {
  return service({
    url: `/api/graph/project/${projectId}`,
    method: 'get'
  })
}

/** Read-only Cypher (Kuzu backend only) */
export function graphCypherQuery(body) {
  return requestWithRetry(() =>
    service({
      url: '/api/graph/query',
      method: 'post',
      data: body
    })
  )
}

export function exportProjectBundle(projectId, headers = {}) {
  return requestWithRetry(() =>
    service({
      url: `/api/graph/project/${projectId}/export-bundle`,
      method: 'get',
      headers
    })
  )
}

export function importProjectBundle(data, headers = {}) {
  return requestWithRetry(() =>
    service({
      url: '/api/graph/project/import-bundle',
      method: 'post',
      data,
      headers
    })
  )
}

export function createGraphSnapshot(projectId, label, headers = {}) {
  return requestWithRetry(() =>
    service({
      url: `/api/graph/project/${projectId}/graph-snapshot`,
      method: 'post',
      data: { label },
      headers
    })
  )
}

export function listGraphSnapshots(projectId, headers = {}) {
  return requestWithRetry(() =>
    service({
      url: `/api/graph/project/${projectId}/graph-snapshots`,
      method: 'get',
      headers
    })
  )
}

export function diffGraphSnapshots(projectId, snapshotA, snapshotB, headers = {}) {
  return requestWithRetry(() =>
    service({
      url: `/api/graph/project/${projectId}/graph-diff`,
      method: 'post',
      data: {
        snapshot_a: snapshotA,
        snapshot_b: snapshotB
      },
      headers
    })
  )
}
