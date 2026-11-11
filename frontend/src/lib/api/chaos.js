import { api } from './client'

export const chaosApi = {
  status() { return api.get('/api/v1/chaos/status') },
  issues() { return api.get('/api/v1/chaos/issues') },
  issueState(issueNumber) { return api.get(`/api/v1/chaos/issues/${encodeURIComponent(issueNumber)}/state`) },
  fault(mode) { return api.put('/api/v1/chaos/fault', { mode }) },
  run(payload) { return api.post('/api/v1/chaos/run', payload) },
  getRun(runId) { return api.get(`/api/v1/chaos/runs/${encodeURIComponent(runId)}`) },
  approve(transactionId, approver = 'chaos-operator') {
    return api.post(`/api/v1/transactions/${encodeURIComponent(transactionId)}/approve`, { approver })
  },
  retry(transactionId) {
    return api.post(`/api/v1/transactions/${encodeURIComponent(transactionId)}/retry`, {})
  },
  reconcile(transactionId) {
    return api.post(`/api/v1/transactions/${encodeURIComponent(transactionId)}/reconcile`, {})
  },
  reset(issueNumber) { return api.post('/api/v1/chaos/reset', { issue_number: issueNumber }) },
}
