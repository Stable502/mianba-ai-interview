import axios from 'axios'
import { message } from 'ant-design-vue'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 30000,
})

// 请求拦截：携带 token
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：统一处理错误
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail || error.message || '请求失败'
    if (status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      // 如果当前已经在登录页，不要重复弹窗（登录页本身就是处理未登录的）
      const isLoginPage = window.location.pathname === '/login'
      if (!isLoginPage) {
        message.error('登录已过期，请重新登录')
        setTimeout(() => {
          window.location.href = '/login'
        }, 600)
      }
    } else {
      message.error(typeof detail === 'string' ? detail : '请求失败')
    }
    return Promise.reject(error)
  },
)

export default request
