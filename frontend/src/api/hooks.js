import service from './index.js'

export function listWebhooks(headers = {}) {
  return service.get('/api/hooks/webhooks', { headers })
}

export function registerWebhook(body, headers = {}) {
  return service.post('/api/hooks/webhooks', body, { headers })
}

export function deleteWebhook(subId, headers = {}) {
  return service.delete(`/api/hooks/webhooks/${encodeURIComponent(subId)}`, { headers })
}
