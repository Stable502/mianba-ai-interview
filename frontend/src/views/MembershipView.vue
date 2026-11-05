<template>
  <div class="membership">
    <!-- 当前套餐 -->
    <div class="card current-card">
      <div class="current-left">
        <div class="current-label">当前套餐</div>
        <div class="current-name">{{ userStore.user?.plan_name || '免费版' }}</div>
        <div class="current-quota">{{ userStore.quotaText }}</div>
      </div>
      <div class="current-right">
        <a-tag v-if="userStore.isMember" color="gold">
          <CrownOutlined /> 会员
        </a-tag>
        <a-tag v-else>免费用户</a-tag>
      </div>
    </div>

    <div class="section-title">选择你的计划</div>

    <div class="plan-grid">
      <div
        v-for="p in plans"
        :key="p.id"
        class="card plan-card"
        :class="{ featured: p.code === 'monthly', current: p.code === userStore.user?.plan_code }"
      >
        <div v-if="p.code === 'monthly'" class="plan-badge">最受欢迎</div>
        <div class="plan-name">{{ p.name }}</div>
        <div class="plan-price">
          <span class="price-num">{{ centsToYuan(p.price_cents) }}</span>
          <span class="price-unit">元</span>
          <span v-if="p.period_days > 0" class="price-period">/ {{ periodText(p.period_days) }}</span>
        </div>
        <div class="plan-features">
          <div class="feature-row">
            <span class="feature-dot"></span>
            <span>{{ p.max_interviews_month == null ? '不限次数模拟面试' : `每月 ${p.max_interviews_month} 次面试` }}</span>
          </div>
          <div class="feature-row">
            <span class="feature-dot"></span>
            <span>{{ p.full_report_enabled ? '完整诊断报告' : '精简版报告' }}</span>
          </div>
          <div class="feature-row">
            <span class="feature-dot"></span>
            <span>{{ p.pdf_export_enabled ? '支持 PDF 导出' : '不支持 PDF 导出' }}</span>
          </div>
          <div class="feature-row">
            <span class="feature-dot"></span>
            <span>{{ p.persona_premium ? '解锁全部面试官风格' : '基础面试官风格' }}</span>
          </div>
        </div>
        <a-button
          v-if="p.code !== 'free'"
          type="primary"
          :ghost="p.code !== 'monthly'"
          block
          size="large"
          :disabled="p.code === userStore.user?.plan_code"
          @click="upgrade(p)"
        >
          {{ p.code === userStore.user?.plan_code ? '当前套餐' : '立即开通' }}
        </a-button>
        <div v-else class="free-note">默认开通，无需付费</div>
      </div>
    </div>

    <div class="card note-card">
      <div class="note-title">💡 说明</div>
      <div class="note-text">
        支付为演示环境的模拟收银台（无需真实付款），下单支付后会员权益即时生效：不限次数面试、完整诊断报告、PDF 导出与全部面试官风格。
      </div>
    </div>

    <!-- 我的订单 -->
    <div class="card orders-card" v-if="orders.length">
      <div class="section-title">我的订单</div>
      <div class="order-row order-head">
        <span>订单号</span><span>套餐</span><span>金额</span><span>状态</span><span>时间</span>
      </div>
      <div class="order-row" v-for="o in orders" :key="o.order_no">
        <span class="order-no">{{ o.order_no }}</span>
        <span>{{ o.plan_name }}</span>
        <span>¥{{ centsToYuan(o.amount_cents) }}</span>
        <span :class="['order-status', o.status === 2 ? 'paid' : 'pending']">
          {{ orderStatusText(o.status) }}
        </span>
        <span>{{ formatTime(o.created_at) }}</span>
      </div>
    </div>

    <!-- 模拟收银台 -->
    <a-modal
      v-model:open="checkoutVisible"
      title="确认订购"
      :footer="null"
      :mask-closable="false"
      width="420px"
    >
      <div class="checkout">
        <div class="checkout-plan">
          <div class="checkout-name">{{ checkoutPlan?.name }}</div>
          <div class="checkout-price">¥{{ checkoutPlan ? centsToYuan(checkoutPlan.price_cents) : '' }}</div>
        </div>
        <div class="checkout-desc" v-if="checkoutPlan">
          权益：{{ checkoutPlan.max_interviews_month == null ? '不限次数面试' : `每月 ${checkoutPlan.max_interviews_month} 次面试` }}
          · 有效期 {{ periodText(checkoutPlan.period_days) }}
        </div>
        <div class="channel-list">
          <div
            v-for="c in channels"
            :key="c.value"
            class="channel-item"
            :class="{ active: channel === c.value }"
            @click="channel = c.value"
          >
            <span>{{ c.icon }} {{ c.label }}</span>
            <span class="channel-check">{{ channel === c.value ? '✓' : '' }}</span>
          </div>
        </div>
        <template v-if="!waitPay">
          <a-button type="primary" block size="large" :loading="paying" @click="confirmPay">
            {{ channel === 'alipay' ? '去支付宝支付' : '确认支付（模拟）' }}
          </a-button>
          <div class="checkout-tip">{{ channel === 'alipay' ? '将跳转支付宝沙箱收银台，用沙箱买家账号付款' : '演示环境模拟收银台，不会产生真实扣款' }}</div>
        </template>
        <template v-else>
          <div class="pay-waiting">
            <a-spin size="large" />
            <div class="waiting-text">等待支付完成…</div>
            <div class="waiting-sub">
              已在新窗口打开支付宝收银台，付款成功后本页会自动开通会员
            </div>
          </div>
          <a-button block @click="checkNow">我已完成支付，立即检查</a-button>
          <a-button block type="link" danger @click="cancelWait">取消支付</a-button>
        </template>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { CrownOutlined } from '@ant-design/icons-vue'
import { planApi } from '@/api/report'
import { orderApi } from '@/api/order'
import { useUserStore } from '@/store/user'
import { centsToYuan } from '@/utils/format'

const userStore = useUserStore()
const plans = ref([])
const orders = ref([])
const checkoutVisible = ref(false)
const checkoutPlan = ref(null)
const channel = ref('mock_wechat')
const paying = ref(false)
const waitPay = ref(false)
const alipayEnabled = ref(false)

let pollingTimer = null
let pollingDeadline = 0

const channels = ref([
  { value: 'mock_wechat', label: '微信支付（模拟）', icon: '💬' },
  { value: 'mock_alipay', label: '支付宝（模拟）', icon: '🅰️' },
])

function periodText(days) {
  if (days >= 365) return '年'
  if (days >= 90) return '季度'
  return '月'
}

function orderStatusText(status) {
  return { 1: '待支付', 2: '已支付', 3: '已退款', 4: '已关闭' }[status] || '未知'
}

function formatTime(dt) {
  if (!dt) return '-'
  return String(dt).replace('T', ' ').slice(0, 16)
}

async function upgrade(p) {
  checkoutPlan.value = p
  channel.value = alipayEnabled.value ? 'alipay' : 'mock_wechat'
  waitPay.value = false
  checkoutVisible.value = true
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
  waitPay.value = false
}

async function onPaid(result) {
  stopPolling()
  checkoutVisible.value = false
  message.success(result.message || '会员开通成功')
  await Promise.all([userStore.fetchMe(), loadOrders()])
}

async function checkNow() {
  await pollOnce(checkoutPlan.value && pendingOrderNo.value)
}

let pendingOrderNo = ref(null)

async function pollOnce(orderNo) {
  if (!orderNo) return false
  try {
    const res = await orderApi.status(orderNo)
    if (res.status === 2) {
      await onPaid(res)
      return true
    }
  } catch (e) {
    /* 忽略单次查询失败 */
  }
  return false
}

function startPolling(orderNo) {
  pendingOrderNo.value = orderNo
  waitPay.value = true
  pollingDeadline = Date.now() + 5 * 60 * 1000 // 最长等待 5 分钟
  stopPolling()
  pollingTimer = setInterval(async () => {
    if (Date.now() > pollingDeadline) {
      message.warning('等待超时，如已付款请稍后在"我的订单"查看状态')
      stopPolling()
      checkoutVisible.value = false
      loadOrders()
      return
    }
    await pollOnce(orderNo)
  }, 2500)
}

async function cancelWait() {
  stopPolling()
  checkoutVisible.value = false
  loadOrders()
}

async function confirmPay() {
  if (!checkoutPlan.value || paying.value || waitPay.value) return
  paying.value = true
  try {
    // 1. 创建订单（待支付）
    const order = await orderApi.create(checkoutPlan.value.code, channel.value)
    // 2. 支付
    const result = await orderApi.pay(order.order_no, channel.value)
    if (channel.value === 'alipay' && result.pay_url) {
      // 3. 支付宝：新窗口打开收银台，轮询订单状态等待支付完成
      window.open(result.pay_url, '_blank')
      startPolling(order.order_no)
      return
    }
    // 4. mock 渠道：即时开通
    await onPaid(result)
  } catch (e) {
    // 拦截器已提示
  } finally {
    paying.value = false
  }
}

async function loadOrders() {
  try {
    orders.value = await orderApi.list()
  } catch (e) {
    orders.value = []
  }
}

onMounted(async () => {
  try {
    const [planList, config] = await Promise.all([planApi.list(), orderApi.payConfig()])
    plans.value = planList
    if (config.alipay_enabled) {
      alipayEnabled.value = true
      channels.value.unshift({ value: 'alipay', label: '支付宝（真实沙箱支付）', icon: '🔵' })
      channel.value = 'alipay'
    }
  } catch (e) {
    // 拦截器已提示
  }
  loadOrders()
})
</script>

<style scoped>
.membership {
  max-width: 980px;
  margin: 0 auto;
}
.current-card {
  padding: 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28px;
}
.current-label {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 4px;
}
.current-name {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
}
.current-quota {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}
.section-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 16px;
}
.plan-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.plan-card {
  padding: 24px 20px;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.plan-card.featured {
  border-color: var(--brand);
  box-shadow: 0 8px 24px rgba(59, 91, 255, 0.12);
}
.plan-card.current {
  background: var(--brand-soft);
}
.plan-badge {
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--brand);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 12px;
  border-radius: 12px;
  white-space: nowrap;
}
.plan-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
}
.plan-price {
  display: flex;
  align-items: baseline;
  gap: 2px;
}
.price-num {
  font-size: 36px;
  font-weight: 700;
  color: var(--ink);
}
.price-unit {
  font-size: 14px;
  color: #6b7280;
}
.price-period {
  font-size: 13px;
  color: #9ca3af;
}
.plan-features {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
}
.feature-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: var(--text);
}
.feature-dot {
  width: 6px;
  height: 6px;
  background: var(--brand);
  border-radius: 3px;
  margin-top: 7px;
  flex-shrink: 0;
}
.free-note {
  text-align: center;
  font-size: 13px;
  color: #9ca3af;
  padding: 8px 0;
}
.note-card {
  padding: 20px;
}
.note-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 8px;
}
.note-text {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.8;
}
/* 收银台 */
.checkout {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.checkout-plan {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
.checkout-name {
  font-size: 17px;
  font-weight: 700;
  color: var(--ink);
}
.checkout-price {
  font-size: 26px;
  font-weight: 700;
  color: #e65100;
}
.checkout-desc {
  font-size: 13px;
  color: #6b7280;
  padding: 10px 12px;
  background: #f6f7fb;
  border-radius: 8px;
}
.channel-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.channel-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  color: var(--ink);
  transition: all 0.2s;
}
.channel-item.active {
  border-color: var(--brand);
  background: var(--brand-soft);
}
.channel-check {
  color: var(--brand);
  font-weight: 700;
}
.checkout-tip {
  text-align: center;
  font-size: 12px;
  color: #9ca3af;
}
.pay-waiting {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
}
.pay-qr {
  width: 210px;
  height: 210px;
  object-fit: contain;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 8px;
  background: #fff;
}
.waiting-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
}
.waiting-sub {
  font-size: 12px;
  color: #9ca3af;
  text-align: center;
  line-height: 1.6;
}
/* 我的订单 */
.orders-card {
  padding: 24px;
  margin-bottom: 24px;
}
.order-row {
  display: grid;
  grid-template-columns: 1.6fr 1fr 0.7fr 0.8fr 1.1fr;
  gap: 8px;
  font-size: 13px;
  color: var(--text);
  padding: 10px 0;
  border-bottom: 1px solid #f1f2f6;
}
.order-row:last-child {
  border-bottom: none;
}
.order-head {
  color: #9ca3af;
  font-size: 12px;
}
.order-no {
  font-family: monospace;
}
.order-status.paid {
  color: #16a34a;
}
.order-status.pending {
  color: #d97706;
}
@media (max-width: 1100px) {
  .plan-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
