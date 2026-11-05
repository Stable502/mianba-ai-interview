import { defineStore } from 'pinia'
import { authApi } from '@/api/auth'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    tokenVerified: false,  // token 是否已验证有效性（防止过期 token 放行到业务页）
  }),
  getters: {
    isLogin: (state) => !!state.token,
    isMember: (state) => !!state.user?.is_member,
    quotaText: (state) => {
      if (!state.user) return ''
      if (state.user.quota_limit == null) return '无限次'
      return `本月剩余 ${state.user.quota_remain ?? 0} 次`
    },
  },
  actions: {
    setToken(token) {
      this.token = token
      this.tokenVerified = true
      localStorage.setItem('token', token)
    },
    setUser(user) {
      this.user = user
      localStorage.setItem('user', JSON.stringify(user))
    },
    async verifyToken() {
      // 验证 token 是否有效；无效则清掉 token。返回 true=有效，false=无效
      if (!this.token) return false
      if (this.tokenVerified) return true
      try {
        const user = await authApi.me()
        this.setUser(user)
        this.tokenVerified = true
        return true
      } catch (e) {
        this.logout()
        return false
      }
    },
    async fetchMe() {
      // 主动拉取当前用户信息（登录成功后、支付成功后调用）
      if (!this.token) return null
      try {
        const user = await authApi.me()
        this.setUser(user)
        this.tokenVerified = true
        return user
      } catch (e) {
        return null
      }
    },
    logout() {
      this.token = ''
      this.user = null
      this.tokenVerified = false
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
  },
})
