import { createResourceApi } from './client'
import http from './client'

export const replantingApi = {
  ...createResourceApi('replanting-records'),
  summary: (params) => http.get('/replanting-records/summary', { params }),
  registerReview: (id, payload) => http.patch(`/replanting-records/${id}/review`, payload),
}
