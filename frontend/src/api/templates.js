import apiService from './index.js'

/**
 * List all available simulation templates
 */
export async function listTemplates() {
  const response = await apiService.get('/api/templates/')
  return response.data
}

/**
 * Get a single template by ID
 */
export async function getTemplate(templateId) {
  const response = await apiService.get(`/api/templates/${templateId}`)
  return response.data
}
