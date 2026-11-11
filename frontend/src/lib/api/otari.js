import { api } from './client'

export const otariApi = {
  budget(options = {}) {
    return api.get('/api/v1/integrations/otari/budget', options)
  },
  usage(options = {}) {
    return api.get('/api/v1/integrations/otari/usage', options)
  },
  series(bucket = 'day', options = {}) {
    return api.get(`/api/v1/integrations/otari/usage/series?bucket=${encodeURIComponent(bucket)}`, options)
  },
  tools(options = {}) {
    return api.get('/api/v1/integrations/otari/tools', options)
  },
}
