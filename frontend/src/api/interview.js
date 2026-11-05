import request from './request'

export const interviewApi = {
  preview: (data) => request.post('/interviews/preview', data),
  create: (data) => request.post('/interviews', data),
  list: () => request.get('/interviews'),
  get: (id) => request.get(`/interviews/${id}`),
  messages: (id) => request.get(`/interviews/${id}/messages`),
  sendMessage: (id, data) => request.post(`/interviews/${id}/messages`, data),
  end: (id) => request.post(`/interviews/${id}/end`),
}
