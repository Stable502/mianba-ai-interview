<template>
  <div>
    <!-- 欢迎区 -->
    <div class="welcome-row">
      <div>
        <div class="welcome-title">{{ greeting }}，{{ userStore.user?.nickname || '用户' }}</div>
        <div class="welcome-sub">根据上次面试，今日建议练习：项目深挖话术</div>
      </div>
      <a-button type="primary" size="large" @click="router.push('/create')">
        <template #icon><PlusOutlined /></template>
        新建面试
      </a-button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="card stat-card">
        <div class="stat-label">累计面试次数</div>
        <div class="stat-value">{{ stats.total }} 次</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">平均综合得分</div>
        <div class="stat-value brand">{{ stats.avgScore }} / 5</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">累计练习时长</div>
        <div class="stat-value">{{ stats.totalMinutes }} 分钟</div>
      </div>
      <div class="card stat-card">
        <div class="stat-label">待改进话术点</div>
        <div class="stat-value orange">{{ stats.weaknessCount }} 处</div>
      </div>
    </div>

    <!-- 额度卡片 -->
    <div class="card quota-card">
      <div class="quota-head">
        <div class="quota-title">{{ userStore.user?.is_member ? '会员额度' : '免费额度' }}</div>
        <a-button type="primary" size="small" @click="router.push('/membership')">升级</a-button>
      </div>
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: quotaPercent + '%' }"></div>
      </div>
      <div class="quota-desc">{{ quotaDesc }}</div>
    </div>

    <!-- 最近面试记录 -->
    <div class="card table-card">
      <div class="table-head-row">
        <div class="table-title">最近面试记录</div>
        <a class="view-all" @click="router.push('/reports')">查看全部</a>
      </div>
      <a-table
        :data-source="recentList"
        :columns="columns"
        :pagination="false"
        row-key="id"
        :loading="loading"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'type'">
            <a-tag :color="typeColor(record.interview_type)">{{ typeShort(record.interview_type) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'persona'">
            {{ record.persona_name || '—' }}
          </template>
          <template v-else-if="column.key === 'duration'">
            {{ record.planned_minutes }} 分钟
          </template>
          <template v-else-if="column.key === 'score'">
            <span v-if="record.overall_score != null" :style="{ color: scoreRate(record.overall_score).color, fontWeight: 600 }">
              {{ record.overall_score }} · {{ scoreRate(record.overall_score).label }}
            </span>
            <span v-else class="text-muted">进行中</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a @click="viewReport(record)">查看报告</a>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { PlusOutlined } from '@ant-design/icons-vue'
import { interviewApi } from '@/api/interview'
import { reportApi } from '@/api/report'
import { useUserStore } from '@/store/user'
import { typeShort, typeColor, scoreRate } from '@/utils/format'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const sessions = ref([])
const reportMap = ref({})

const stats = reactive({ total: 0, avgScore: '—', totalMinutes: 0, weaknessCount: 0 })
const recentList = computed(() => sessions.value.slice(0, 5))

const columns = [
  { title: '面试类型', key: 'type' },
  { title: '面试官风格', key: 'persona' },
  { title: '时长', key: 'duration' },
  { title: '得分', key: 'score' },
  { title: '操作', key: 'action', align: 'right' },
]

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '早上好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const quotaPercent = computed(() => {
  const u = userStore.user
  if (!u || u.quota_limit == null) return 0
  return Math.min(Math.round((u.quota_used / u.quota_limit) * 100), 100)
})

const quotaDesc = computed(() => {
  const u = userStore.user
  if (!u) return ''
  if (u.quota_limit == null) return '会员用户 · 无限次面试'
  return `免费用户每月 ${u.quota_limit} 次完整面试 · 已用 ${u.quota_used} 次 · 剩余 ${u.quota_remain} 次`
})

async function viewReport(record) {
  const reportId = reportMap.value[record.id]
  if (reportId) {
    router.push(`/reports/${reportId}`)
    return
  }
  // 已结束但没有报告的会话（历史自然结束）：调用 end 接口补生成（幂等）
  if (record.status !== 2) {
    try {
      const res = await interviewApi.end(record.id)
      if (res?.report_id) {
        // 更新映射，便于下次直接跳转
        reportMap.value[record.id] = res.report_id
        router.push(`/reports/${res.report_id}`)
        return
      }
    } catch (e) {
      // 忽略，走默认跳转
    }
  }
  router.push('/reports')
}

async function load() {
  loading.value = true
  try {
    const [sessionsData, reportsData] = await Promise.all([
      interviewApi.list(),
      reportApi.list(),
    ])
    sessions.value = sessionsData
    reportMap.value = {}
    reportsData.forEach((r) => {
      reportMap.value[r.session_id] = r.id
    })

    // 统计
    stats.total = sessionsData.length
    const scored = sessionsData.filter((s) => s.overall_score != null)
    if (scored.length) {
      const avg = scored.reduce((sum, s) => sum + Number(s.overall_score), 0) / scored.length
      stats.avgScore = avg.toFixed(1)
    } else {
      stats.avgScore = '—'
    }
    stats.totalMinutes = sessionsData.reduce((sum, s) => sum + (s.planned_minutes || 0), 0)
    stats.weaknessCount = reportsData.reduce((sum, r) => sum + (r.weaknesses?.length || 0), 0)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.welcome-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.welcome-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 6px;
}
.welcome-sub {
  font-size: 14px;
  color: #6b7280;
}
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.stat-card {
  padding: 20px;
}
.stat-label {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 6px;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--ink);
}
.stat-value.brand {
  color: var(--brand);
}
.stat-value.orange {
  color: var(--orange);
}
.quota-card {
  padding: 20px;
  margin-bottom: 24px;
}
.quota-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.quota-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
}
.progress-bar {
  background: var(--brand-soft);
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 14px;
}
.progress-fill {
  background: var(--brand);
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}
.quota-desc {
  font-size: 13px;
  color: #6b7280;
}
.table-card {
  padding: 20px;
}
.table-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.table-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
}
.view-all {
  font-size: 13px;
  font-weight: 500;
  color: var(--brand);
}
</style>
