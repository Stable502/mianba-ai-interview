import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/store/user'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        redirect: '/dashboard',
      },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '工作台' },
      },
      {
        path: 'create',
        name: 'create',
        component: () => import('@/views/CreateInterviewView.vue'),
        meta: { title: '新建面试' },
      },
      {
        path: 'reports',
        name: 'reports',
        component: () => import('@/views/ReportListView.vue'),
        meta: { title: '面试记录' },
      },
      {
        path: 'reports/:id',
        name: 'report-detail',
        component: () => import('@/views/ReportDetailView.vue'),
        meta: { title: '诊断报告' },
      },
      {
        path: 'resume',
        name: 'resume',
        component: () => import('@/views/ResumeManageView.vue'),
        meta: { title: '简历管理' },
      },
      {
        path: 'membership',
        name: 'membership',
        component: () => import('@/views/MembershipView.vue'),
        meta: { title: '会员中心' },
      },
      {
        path: 'recycle-bin',
        name: 'recycle-bin',
        component: () => import('@/views/RecycleBinView.vue'),
        meta: { title: '回收站' },
      },
    ],
  },
  {
    path: '/interview/:id',
    name: 'interview',
    component: () => import('@/views/InterviewRoomView.vue'),
    meta: { title: '模拟面试间' },
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  document.title = to.meta.title ? `${to.meta.title} · 面霸 AI` : '面霸 AI'
  const userStore = useUserStore()

  // 登录页直接放行
  if (to.meta.public) return true

  // 没有 token → 跳登录
  if (!userStore.token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 有 token 但还没验证过有效性 → 调 /api/auth/me 验证
  if (!userStore.tokenVerified) {
    const ok = await userStore.verifyToken()
    if (!ok) {
      // token 无效（过期），已在 verifyToken 里清掉 → 跳登录
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }

  return true
})

export default router
