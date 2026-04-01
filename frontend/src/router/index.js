import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Process from '../views/MainView.vue'
import SimulationView from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView from '../views/ReportView.vue'
import InteractionView from '../views/InteractionView.vue'
import ReportCompareView from '../views/ReportCompareView.vue'
import SimulationCompareView from '../views/SimulationCompareView.vue'
import WorkflowToolsView from '../views/WorkflowToolsView.vue'
import TemplateEditorView from '../views/TemplateEditorView.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/process/:projectId',
    name: 'Process',
    component: Process,
    props: true
  },
  {
    path: '/simulation/compare',
    name: 'SimulationCompare',
    component: SimulationCompareView
  },
  {
    path: '/simulation/:simulationId/start',
    name: 'SimulationRun',
    component: SimulationRunView,
    props: true
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: SimulationView,
    props: true
  },
  {
    path: '/report/compare',
    name: 'ReportCompare',
    component: ReportCompareView
  },
  {
    path: '/report/:reportId',
    name: 'Report',
    component: ReportView,
    props: true
  },
  {
    path: '/interaction/:reportId',
    name: 'Interaction',
    component: InteractionView,
    props: true
  },
  {
    path: '/tools',
    name: 'WorkflowTools',
    component: WorkflowToolsView
  },
  {
    path: '/templates/edit',
    name: 'TemplateEditor',
    component: TemplateEditorView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
