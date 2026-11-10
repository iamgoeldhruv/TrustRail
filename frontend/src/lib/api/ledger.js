import { api } from './client'

export const ledgerApi = {
  transactions(params = {}, options) {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') query.set(key, value)
    })
    return api.get(`/api/v1/ledger/transactions${query.size ? `?${query}` : ''}`, options)
  },
  transaction(transactionId, options) {
    return api.get(`/api/v1/ledger/transactions/${encodeURIComponent(transactionId)}`, options)
  },
  verify(transactionId, options) {
    return api.post(`/api/v1/ledger/transactions/${encodeURIComponent(transactionId)}/verify`, {}, options)
  },
}
