<template>
  <div>
    <div class="page-head">
      <div>
        <div class="page-title">面试记录</div>
        <div class="page-sub">共 {{ reports.length }} 份诊断报告</div>
      </div>
      <a-button type="primary" size="large" @click="router.push('/create')">
        <template #icon><PlusOutlined /></template>
        新建面试
      </a-button>
    </div>

    <div v-if="loading" class="card empty-card">加载中…</div>
    <div v-else-if="!reports.length" class="card empty-card">
      <div class="empty-icon">🗂️</div>
      <div class="empty-title">还没有面试记录</div>
      <div class="empty-desc">完成第一场模拟面试后，诊断报告会出现在这里</div>
      <a-button type="primary" @click="router.push('/create')">开始第一场面试</a-button>
    </div>

    <div v-else class="report-grid">
      <div
        v-for="r in reports"
        :key="r.id"
        class="card report-card"
        @click="router.push(`/reports/${r.id}`)"
      >
        <div class="report-top">
          <div class="report-type">
            <a-tag :color="typeColor(r.interview_type)">{{ typeShort(r.interview_type) }}</a-tag>
            <span class="report-position">{{ r.position_title || r.persona_name || '通用练习' }}</span>
          </div>
          <div class="report-side">
            <a-popconfirm
              title="该场面试的记录、对话与报告将移入回收站，7 天后自动清除，确认？"
              ok-text="移入回收站"
              cancel-text="取消"
              :ok-button-props="{ danger: true }"
              @confirm="removeReport(r)"
            >
              <a-button size="small" type="text" danger class="del-btn" @click.stop>
                <template #icon><DeleteOutlined /></template>
              </a-button>
            </a-popconfirm>
            <div class="report-score" :style="{ color: scoreRate(r.overall_score).color }">
              {{ r.overall_score }}
            </div>
          </div>
        </div>
        <div class="report-score-label" :style="{ color: scoreRate(r.overall_score).color }">
          {{ scoreRate(r.overall_score).label }}
        </div>
        <div class="report-meta">
          <span>{{ r.persona_name || '—' }}</span>
          <span>·</span>
          <span>{{ r.planned_minutes }} 分钟</span>
          <span>·</span>
          <span>{{ formatTime(r.generated_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons-vue'
import dayjs from 'dayjs'
import { reportApi } from '@/api/report'
import { typeShort, typeColor, scoreRate } from '@/utils/format'

const router = useRouter()
const reports = ref([])
const loading = ref(true)

function formatTime(t) {
  return dayjs(t).format('YYYY-MM-DD HH:mm')
}

async function removeReport(r) {
  await reportApi.remove(r.id)
  message.success('已移入回收站，7 天内可在回收站恢复')
  reports.value = await reportApi.list()
}

onMounted(async () => {
  loading.value = true
  try {
    reports.value = await reportApi.list()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.page-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
}
.page-sub {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}
.empty-card {
  padding: 80px 20px;
  text-align: center;
}
.empty-icon {
  font-size: 40px;
  margin-bottom: 12px;
}
.empty-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 6px;
}
.empty-desc {
  font-size: 13px;
  color: #9ca3af;
  margin-bottom: 16px;
}
.report-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.report-card {
  padding: 20px;
  cursor: pointer;
  transition: all 0.15s;
}
.report-card:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}
.report-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 12px;
}
.report-side {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}
.del-btn {
  margin-top: -4px;
  opacity: 0.55;
}
.report-card:hover .del-btn {
  opacity: 1;
}
.report-type {
  display: flex;
  align-items: center;
  gap: 8px;
}
.report-position {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}
.report-score {
  font-size: 32px;
  font-weight: 700;
  line-height: 1;
}
.report-score-label {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 16px;
}
.report-meta {
  display: flex;
  gap: 6px;
  font-size: 12px;
  color: #9ca3af;
}
@media (max-width: 1100px) {
  .report-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
