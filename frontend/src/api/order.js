import request from './request'

export const orderApi = {
  /** 创建订购订单（待支付） */
  create: (planCode, channel = 'mock') => request.post('/orders', { plan_code: planCode, channel }),
  /** 支付订单：mock 即时开通；alipay 返回收银台跳转 URL */
  pay: (orderNo, channel = 'mock') => request.post(`/orders/${orderNo}/pay`, { channel }),
  /** 查询订单状态（支付宝订单会同步向支付方查询） */
  status: (orderNo) => request.get(`/orders/${orderNo}`),
  /** 支付渠道配置（是否启用支付宝） */
  payConfig: () => request.get('/orders/pay-config'),
  /** 我的订单列表 */
  list: () => request.get('/orders'),
}
