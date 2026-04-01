import { defineStore } from 'pinia'

/**
 * Shared workbench context to reduce redundant refetching across steps (extend as needed).
 */
export const useWorkbenchStore = defineStore('workbench', {
  state: () => ({
    projectId: null,
    graphId: null,
    simulationId: null,
    reportId: null,
  }),
  actions: {
    setContext({ projectId, graphId, simulationId, reportId } = {}) {
      if (projectId !== undefined) this.projectId = projectId
      if (graphId !== undefined) this.graphId = graphId
      if (simulationId !== undefined) this.simulationId = simulationId
      if (reportId !== undefined) this.reportId = reportId
    },
    reset() {
      this.projectId = null
      this.graphId = null
      this.simulationId = null
      this.reportId = null
    },
  },
})
