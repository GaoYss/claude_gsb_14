import { createResourceApi } from './client'
import http from './client'

export const replantingApi = {
  ...createResourceApi('replantings'),
  summary: (params) => http.get('/replantings/summary', { params }),
  review: (id, payload) => http.patch(`/replantings/${id}/review`, payload),
}
