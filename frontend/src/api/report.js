import request from './request'

export const reportApi = {
  list: () => request.get('/reports'),
  get: (id) => request.get(`/reports/${id}`),
  /** 删除面试记录（报告 + 会话 + 题目/消息/评估一并删除） */
  remove: (id) => request.delete(`/reports/${id}`),
}

export const planApi = {
  list: () => request.get('/plans'),
}
