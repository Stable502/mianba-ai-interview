import request from './request'

export const authApi = {
  login: (data) => request.post('/auth/login', data),
  register: (data) => request.post('/auth/register', data),
  me: () => request.get('/auth/me'),
  /** 发送邮箱验证码；演示模式（未配置 SMTP）返回 dev_code */
  sendCode: (account, scene = 'register') => request.post('/auth/send-code', { account, scene }),
  /** 游客体验模式：直接创建临时账号 */
  guest: () => request.post('/auth/guest'),
}
