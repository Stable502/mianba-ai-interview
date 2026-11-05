import request from './request'

/** 回收站：被删除的简历与面试记录，保留 7 天后自动清除 */
export const recycleApi = {
  list: () => request.get('/recycle-bin'),
  restore: (itemType, id) => request.post(`/recycle-bin/${itemType}/${id}/restore`),
  purge: (itemType, id) => request.delete(`/recycle-bin/${itemType}/${id}`),
  clear: () => request.delete('/recycle-bin/clear'),
}
