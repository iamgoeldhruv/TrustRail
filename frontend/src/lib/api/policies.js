import { api } from './client'

export const policyApi = {
  compile(userRequest, options) {
    return api.post('/api/v1/policies/compile', { user_request: userRequest }, options)
  },
  dryRun(policy, options) {
    return api.post('/api/v1/policies/dryrun', { policy }, options)
  },
  activate(policy, nlText, options) {
    return api.post('/api/v1/policies/activate', { policy, nl_text: nlText }, options)
  },
  active(options) {
    return api.get('/api/v1/policies/active', options)
  },
}
