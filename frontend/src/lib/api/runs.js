import { api } from './client'

export const runApi = {
  start(userRequest, options) {
    return api.post('/api/v1/runs', { user_request: userRequest }, options)
  },
  get(runId, options) {
    return api.get(`/api/v1/runs/${encodeURIComponent(runId)}`, options)
  },
  approve(transactionId, approver, options) {
    return api.post(`/api/v1/transactions/${encodeURIComponent(transactionId)}/approve`, { approver }, options)
  },
  reject(transactionId, approver, options) {
    return api.post(`/api/v1/transactions/${encodeURIComponent(transactionId)}/reject`, { approver }, options)
  },
  execute(transactionId, options) {
    return api.post(`/api/v1/transactions/${encodeURIComponent(transactionId)}/retry`, {}, options)
  },
}
