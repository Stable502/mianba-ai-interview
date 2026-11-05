<template>
  <a-layout style="min-height: 100vh">
    <a-layout-sider
      width="232"
      :style="{ background: '#fff', borderRight: '1px solid var(--border)' }"
      :trigger="null"
      collapsible
      v-model:collapsed="collapsed"
    >
      <div class="sider-inner">
        <div class="logo-row">
          <div class="logo-mark">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M4 6h16v5H4z" fill="#fff" />
              <path d="M4 13h16v5H4z" fill="#fff" />
              <circle cx="12" cy="12" r="2" fill="#fff" />
            </svg>
          </div>
          <div v-if="!collapsed" class="brand-name">面霸 AI</div>
        </div>

        <nav class="nav-group">
          <div
            v-for="item in navItems"
            :key="item.path"
            class="nav-item"
            :class="{ active: isActive(item) }"
            @click="go(item)"
          >
            <span class="ic"><component :is="item.icon" /></span>
            <span v-if="!collapsed">{{ item.label }}</span>
          </div>
        </nav>

        <div class="spacer"></div>

        <div v-if="!collapsed" class="upgrade-card">
          <div class="upgrade-title">升级会员 Pro</div>
          <div class="upgrade-desc">解锁无限次面试与完整报告</div>
          <div class="upgrade-btn" @click="router.push('/membership')">立即升级</div>
        </div>

        <div class="user-info" v-if="!collapsed">
          <div class="avatar">{{ avatarText }}</div>
          <div class="user-name-col">
            <div class="user-name">{{ userStore.user?.nickname || '用户' }}</div>
            <div class="user-plan">
              {{ userStore.user?.plan_name || '免费版' }} · {{ userStore.quotaText }}
            </div>
          </div>
          <a-dropdown>
            <a-button type="text" size="small" style="margin-left: auto">
              <DownOutlined />
            </a-button>
            <template #overlay>
              <a-menu @click="onUserMenu">
                <a-menu-item key="logout">退出登录</a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </div>
    </a-layout-sider>

    <a-layout>
      <a-layout-header class="topbar">
        <div class="topbar-title">{{ route.meta.title || '工作台' }}</div>
        <div class="topbar-right">
          <div class="quota-badge">
            <span class="quota-dot"></span>
            {{ userStore.quotaText }}
          </div>
          <a-dropdown>
            <div class="top-avatar">{{ avatarText }}</div>
            <template #overlay>
              <a-menu @click="onUserMenu">
                <a-menu-item key="logout">退出登录</a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>

      <a-layout-content class="content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  AppstoreOutlined,
  PlusCircleOutlined,
  FileTextOutlined,
  IdcardOutlined,
  CrownOutlined,
  RestOutlined,
  DownOutlined,
} from '@ant-design/icons-vue'
import { useUserStore } from '@/store/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const collapsed = ref(false)

const navItems = [
  { path: '/dashboard', label: '工作台', icon: AppstoreOutlined },
  { path: '/create', label: '新建面试', icon: PlusCircleOutlined },
  { path: '/reports', label: '面试记录', icon: FileTextOutlined },
  { path: '/resume', label: '简历管理', icon: IdcardOutlined },
  { path: '/recycle-bin', label: '回收站', icon: RestOutlined },
  { path: '/membership', label: '会员中心', icon: CrownOutlined },
]

const avatarText = computed(() => {
  const nick = userStore.user?.nickname || '用'
  return nick[0] || '用'
})

function isActive(item) {
  if (item.path === '/reports') return route.path.startsWith('/reports')
  return route.path === item.path
}

function go(item) {
  router.push(item.path)
}

function onUserMenu({ key }) {
  if (key === 'logout') {
    userStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.sider-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.logo-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 24px;
}
.logo-mark {
  width: 28px;
  height: 28px;
  background: var(--brand);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.brand-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
}
.nav-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  color: #6b7280;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.15s;
}
.nav-item:hover {
  background: var(--brand-soft);
}
.nav-item.active {
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 600;
}
.ic {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}
.spacer {
  flex: 1;
}
.upgrade-card {
  margin: 12px;
  padding: 16px;
  background: var(--brand);
  border-radius: 12px;
  color: #fff;
}
.upgrade-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 8px;
}
.upgrade-desc {
  font-size: 12px;
  line-height: 1.6;
  opacity: 0.9;
  margin-bottom: 12px;
}
.upgrade-btn {
  text-align: center;
  background: #fff;
  color: var(--brand);
  border-radius: 8px;
  padding: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-top: 1px solid var(--border-light);
}
.avatar {
  width: 36px;
  height: 36px;
  background: var(--purple);
  border-radius: 18px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 600;
  flex-shrink: 0;
}
.user-name-col {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}
.user-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}
.user-plan {
  font-size: 12px;
  color: #9ca3af;
  white-space: nowrap;
}

.topbar {
  height: 64px;
  background: #fff;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  line-height: 64px;
}
.topbar-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--ink);
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.quota-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--brand-soft);
  border-radius: 20px;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--brand);
}
.quota-dot {
  width: 8px;
  height: 8px;
  background: var(--brand);
  border-radius: 4px;
}
.top-avatar {
  width: 32px;
  height: 32px;
  background: var(--purple);
  border-radius: 16px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.content {
  padding: 32px;
  overflow-y: auto;
}
</style>
