import request from './request'

export const resumeApi = {
  list: () => request.get('/resumes'),
  create: (data) => request.post('/resumes', data),
  get: (id) => request.get(`/resumes/${id}`),
  update: (id, data) => request.put(`/resumes/${id}`, data),
  remove: (id) => request.delete(`/resumes/${id}`),
  setDefault: (id) => request.post(`/resumes/${id}/default`),
}
