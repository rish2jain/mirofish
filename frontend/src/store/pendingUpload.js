/**
 * Temporary storage for pending file uploads and requirements.
 * Used when launching the engine from the homepage - stores data
 * before navigating to Process page where the API call is made.
 */
import { reactive } from 'vue'

const state = reactive({
  files: [],
  simulationRequirement: '',
  templateId: '',
  isPending: false
})

export function setPendingUpload(files, requirement, templateId = '') {
  state.files = files
  state.simulationRequirement = requirement
  state.templateId = templateId
  state.isPending = true
}

export function getPendingUpload() {
  return {
    files: state.files,
    simulationRequirement: state.simulationRequirement,
    templateId: state.templateId,
    isPending: state.isPending
  }
}

export function clearPendingUpload() {
  state.files = []
  state.simulationRequirement = ''
  state.templateId = ''
  state.isPending = false
}

export default state
