<template>
  <div class="login-page">
    <!-- 左侧品牌区 -->
    <div class="login-brand">
      <div class="login-logo-row">
        <div class="login-logo-mark">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path d="M4 6h16v5H4z" fill="#3B5BFF" />
            <path d="M4 13h16v5H4z" fill="#3B5BFF" />
            <circle cx="12" cy="12" r="2" fill="#3B5BFF" />
          </svg>
        </div>
        <div class="login-brand-name">面霸 AI</div>
      </div>
      <div class="login-title">练一场足够真实的面试</div>
      <div class="login-sub">基于真实简历 × 目标岗位 JD，拿到一份足够具体的面试诊断</div>
      <div class="login-features">
        <div class="login-feature"><span class="dot"></span>个性化：简历 × JD 定制提问与多轮追问</div>
        <div class="login-feature"><span class="dot"></span>沉浸感：语音实时对话 · 多风格面试官人设</div>
        <div class="login-feature"><span class="dot"></span>可行动：逐题点评 + 话术改进示范</div>
      </div>
      <div class="login-privacy">简历与录音数据加密存储 · 用户可随时删除</div>
    </div>

    <!-- 右侧登录区 -->
    <div class="login-area">
      <div class="login-card">
        <div class="login-heading">{{ mode === 'login' ? '欢迎登录' : '注册账号' }}</div>
        <div class="login-subheading">
          {{ mode === 'login' ? '登录后开启你的第一场模拟面试' : '创建账号，保存你的面试记录与简历' }}
        </div>

        <a-tabs v-model:activeKey="mode" centered @change="onModeChange">
          <a-tab-pane key="login" tab="登录" />
          <a-tab-pane key="register" tab="注册" />
        </a-tabs>

        <a-form :model="form" layout="vertical" @finish="onSubmit">
          <a-form-item
            name="account"
            :rules="[{ required: true, message: mode === 'register' ? '请输入邮箱' : '请输入手机号或邮箱' }]"
          >
            <a-input
              v-model:value="form.account"
              size="large"
              :placeholder="mode === 'register' ? '请输入邮箱' : '请输入手机号或邮箱'"
              allow-clear
            />
          </a-form-item>

          <a-form-item
            v-if="mode === 'register'"
            name="sms_code"
          >
            <a-input-group-compact style="display: flex">
              <a-input
                v-model:value="form.sms_code"
                size="large"
                placeholder="请输入 6 位邮箱验证码"
                :maxlength="6"
                style="flex: 1"
                allow-clear
              />
              <a-button
                size="large"
                type="primary"
                ghost
                class="code-btn"
                :disabled="countdown > 0"
                :loading="sending"
                @click="sendVerificationCode"
              >
                {{ countdown > 0 ? `${countdown}s 后重发` : '获取验证码' }}
              </a-button>
            </a-input-group-compact>
          </a-form-item>

          <a-form-item
            v-if="mode === 'register'"
            name="nickname"
          >
            <a-input
              v-model:value="form.nickname"
              size="large"
              placeholder="昵称（选填）"
              allow-clear
            />
          </a-form-item>

          <a-form-item
            name="password"
            :rules="[{ required: true, min: 6, message: '请输入至少 6 位密码' }]"
          >
            <a-input-password
              v-model:value="form.password"
              size="large"
              placeholder="请输入密码"
            />
          </a-form-item>

          <div class="agree-row">
            <a-checkbox v-model:checked="agreed">我已阅读并同意《用户协议》与《隐私政策》</a-checkbox>
          </div>

          <a-button
            type="primary"
            size="large"
            html-type="submit"
            block
            :loading="loading"
            class="login-btn"
          >
            {{ mode === 'login' ? '登录 / 注册' : '立即注册' }}
          </a-button>
        </a-form>

        <div class="skip-login" @click="skipLogin">跳过登录，直接体验</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { authApi } from '@/api/auth'
import { useUserStore } from '@/store/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const mode = ref('login')
const loading = ref(false)
const sending = ref(false)
const countdown = ref(0)
const agreed = ref(false)
const form = reactive({ account: '', password: '', nickname: '', sms_code: '' })
let countdownTimer = null

const EMAIL_RE = /^[\w.+-]+@[\w-]+(\.[\w-]+)+$/

function onModeChange() {
  form.password = ''
  form.sms_code = ''
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
  countdown.value = 0
}

async function sendVerificationCode() {
  const account = form.account.trim()
  if (!EMAIL_RE.test(account)) {
    message.warning('请输入正确的邮箱地址')
    return
  }
  if (sending.value || countdown.value > 0) return
  sending.value = true
  try {
    const res = await authApi.sendCode(account, 'register')
    if (res.dev_code) {
      // 演示模式：对应通道未配置，直接展示验证码
      message.info({
        content: `演示环境未接入真实通道，验证码：${res.dev_code}（5 分钟内有效）`,
        duration: 10,
      })
    } else {
      message.success('验证码已发送至你的邮箱，请查收（5 分钟内有效）')
    }
    countdown.value = res.resend_after || 60
    countdownTimer = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) clearInterval(countdownTimer)
    }, 1000)
  } catch (e) {
    // 错误已在拦截器提示（已注册/频控/格式错误等）
  } finally {
    sending.value = false
  }
}

async function onSubmit() {
  if (!agreed.value) {
    message.warning('请先阅读并同意用户协议与隐私政策')
    return
  }
  if (mode.value === 'register' && !form.sms_code) {
    message.warning('请先获取并输入验证码')
    return
  }
  loading.value = true
  try {
    const api = mode.value === 'login' ? authApi.login : authApi.register
    const payload = { account: form.account.trim(), password: form.password }
    if (mode.value === 'register') {
      payload.nickname = form.nickname
      payload.sms_code = form.sms_code.trim()
    }
    const res = await api(payload)
    userStore.setToken(res.access_token)
    await userStore.fetchMe()
    message.success(mode.value === 'login' ? '登录成功' : '注册成功')
    router.push(route.query.redirect || '/dashboard')
  } catch (e) {
    // 错误已在拦截器提示
  } finally {
    loading.value = false
  }
}

async function skipLogin() {
  loading.value = true
  try {
    // 游客模式：后端直接创建临时账号（免验证码）
    const res = await authApi.guest()
    userStore.setToken(res.access_token)
    await userStore.fetchMe()
    message.success('已进入体验模式')
    router.push('/dashboard')
  } catch (e) {
    // 忽略
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  height: 100vh;
  background: var(--bg);
}
.login-brand {
  width: 600px;
  height: 100%;
  background: linear-gradient(180deg, #3b5bff 0%, #6e8cff 100%);
  padding: 72px;
  display: flex;
  flex-direction: column;
  color: #fff;
  flex-shrink: 0;
}
.login-logo-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: auto;
}
.login-logo-mark {
  width: 40px;
  height: 40px;
  background: #fff;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-brand-name {
  font-size: 24px;
  font-weight: 700;
}
.login-title {
  font-size: 36px;
  font-weight: 700;
  margin-bottom: 16px;
}
.login-sub {
  font-size: 16px;
  line-height: 28px;
  opacity: 0.85;
  margin-bottom: 40px;
}
.login-features {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 40px;
}
.login-feature {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  font-size: 15px;
  font-weight: 500;
}
.login-feature .dot {
  width: 8px;
  height: 8px;
  background: #fff;
  border-radius: 4px;
  margin-top: 7px;
  flex-shrink: 0;
}
.login-privacy {
  font-size: 13px;
  opacity: 0.6;
  margin-top: auto;
}
.login-area {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
}
.login-card {
  width: 400px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.login-heading {
  font-size: 26px;
  font-weight: 700;
  color: var(--ink);
}
.login-subheading {
  font-size: 14px;
  color: #6b7280;
  margin-bottom: 8px;
}
.agree-row {
  margin-bottom: 12px;
  font-size: 13px;
  color: #6b7280;
}
.login-btn {
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 10px;
}
.code-btn {
  width: 132px;
  flex-shrink: 0;
}
.skip-login {
  text-align: center;
  font-size: 14px;
  font-weight: 500;
  color: var(--brand);
  cursor: pointer;
  margin-top: 4px;
}
.skip-login:hover {
  text-decoration: underline;
}
</style>
