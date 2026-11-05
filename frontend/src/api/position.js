import request from './request'

export const positionApi = {
  list: () => request.get('/positions'),
  create: (data) => request.post('/positions', data),
  remove: (id) => request.delete(`/positions/${id}`),
}

export const personaApi = {
  list: () => request.get('/personas'),
}
