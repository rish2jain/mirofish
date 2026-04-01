import apiService from './index.js'

/**
 * List all available simulation templates
 */
export async function listTemplates() {
  // Interceptor already returns JSON body { success, data }; avoid double `.data`.
  const body = await apiService.get('/api/templates/')
  return body?.data ?? body
}

/**
 * Get a single template by ID
 */
export async function getTemplate(templateId) {
  const id = encodeURIComponent(String(templateId))
  const body = await apiService.get(`/api/templates/${id}`)
  return body?.data ?? body
}

/**
 * Upsert template (requires MIROFISH_ALLOW_TEMPLATE_WRITE or FLASK_DEBUG; Bearer if MIROFISH_API_KEY set)
 */
export async function saveTemplate(templateId, data, headers = {}) {
  const id = encodeURIComponent(String(templateId))
  return apiService.put(`/api/templates/${id}`, data, { headers })
}

export async function createTemplateRecord(data, headers = {}) {
  return apiService.post('/api/templates/', data, { headers })
}
